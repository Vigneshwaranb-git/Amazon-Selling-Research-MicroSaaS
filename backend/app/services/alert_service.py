"""BSR change alerts: one digest email per user per run, deduped per snapshot."""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.alert_state import AlertState
from app.models.bsr_snapshot import BsrSnapshot
from app.models.product import Product
from app.models.tracking_list import TrackedProduct, TrackingList
from app.models.user import User
from app.services.email_service import EmailService
from app.services.email_templates import BsrAlertItem, bsr_alert_email

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Change:
    product_id: int
    snapshot_id: int
    item: BsrAlertItem


def _detect_change(db: Session, product: Product, threshold_pct: float) -> _Change | None:
    snaps = list(
        db.scalars(
            select(BsrSnapshot)
            .where(BsrSnapshot.product_id == product.id)
            .order_by(BsrSnapshot.captured_at.desc(), BsrSnapshot.id.desc())
            .limit(2)
        )
    )
    if len(snaps) < 2:
        return None
    latest, previous = snaps
    if latest.bsr is None or previous.bsr is None or previous.bsr <= 0:
        return None
    pct = abs(latest.bsr - previous.bsr) / previous.bsr * 100
    if pct < threshold_pct:
        return None
    return _Change(
        product_id=product.id,
        snapshot_id=latest.id,
        item=BsrAlertItem(
            asin=product.asin,
            title=product.title,
            old_bsr=previous.bsr,
            new_bsr=latest.bsr,
            change_pct=pct,
        ),
    )


def run_bsr_alerts(db: Session, email_service: EmailService) -> int:
    """Send one digest per opted-in user. Returns the number of digests sent."""
    threshold = settings.ALERT_BSR_CHANGE_PCT
    users = db.scalars(
        select(User).where(User.is_active.is_(True), User.notify_bsr_alerts.is_(True))
    ).all()
    sent = 0
    for user in users:
        try:
            products = db.scalars(
                select(Product)
                .join(TrackedProduct, TrackedProduct.product_id == Product.id)
                .join(TrackingList, TrackingList.id == TrackedProduct.tracking_list_id)
                .where(TrackingList.user_id == user.id)
                .distinct()
            ).all()
            states = {
                s.product_id: s
                for s in db.scalars(select(AlertState).where(AlertState.user_id == user.id))
            }
            changes: list[_Change] = []
            for product in products:
                change = _detect_change(db, product, threshold)
                if change is None:
                    continue
                state = states.get(product.id)
                if state is not None and state.last_snapshot_id == change.snapshot_id:
                    continue  # already alerted for this snapshot
                changes.append(change)
            if not changes:
                continue
            changes.sort(key=lambda c: c.item.change_pct, reverse=True)
            email_service.send(bsr_alert_email(user.email, [c.item for c in changes], threshold))
            for c in changes:
                existing = states.get(c.product_id)
                if existing is None:
                    db.add(
                        AlertState(
                            user_id=user.id,
                            product_id=c.product_id,
                            last_snapshot_id=c.snapshot_id,
                        )
                    )
                else:
                    existing.last_snapshot_id = c.snapshot_id
            db.commit()
            sent += 1
        except Exception:
            db.rollback()
            logger.exception("BSR alert failed for user_id=%s", user.id)
    logger.info("BSR alerts: %d digest(s) sent to %d eligible user(s)", sent, len(users))
    return sent
