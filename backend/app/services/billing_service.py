"""Billing business logic. Subscription state changes ONLY via verified webhooks."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import AppException
from app.models.processed_webhook import ProcessedWebhook
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.billing import PlanName
from app.services.dodo_client import DodoClient, DodoError

logger = logging.getLogger(__name__)

# event type -> resulting subscription status. Event names verified against
# https://docs.dodopayments.com/developer-resources/webhooks/intents/subscription
EVENT_STATUS: dict[str, str] = {
    "subscription.active": "active",
    "subscription.renewed": "active",
    "subscription.unpaused": "active",
    "subscription.past_due": "past_due",  # renewal failed, grace period open
    "subscription.on_hold": "past_due",
    "subscription.paused": "paused",
    "subscription.cancelled": "cancelled",
    "subscription.expired": "expired",
}
# Events that do not imply a status themselves; status comes from ``data.status``.
# (``subscription.failed`` = creation failed during mandate setup, so it is NOT mapped
# to past_due; it is ignored. ``subscription.update_payment_method`` is ignored.)
PAYLOAD_STATUS_EVENTS = {"subscription.updated", "subscription.plan_changed"}
PAYLOAD_STATUS: dict[str, str] = {
    "active": "active",
    "on_hold": "past_due",
    "past_due": "past_due",
    "paused": "paused",
    "cancelled": "cancelled",
    "expired": "expired",
}
_LIVE_STATUSES = ("active", "past_due", "paused")


def _product_id(plan: PlanName) -> str:
    pid = {"pro": settings.DODO_PRODUCT_ID_PRO, "business": settings.DODO_PRODUCT_ID_BUSINESS}[plan]
    if not pid:
        raise AppException("Plan is not configured", "PLAN_NOT_CONFIGURED", 503)
    return pid


def get_subscription(db: Session, user_id: int) -> Subscription | None:
    """The user's currently relevant subscription (live ones first, else newest)."""
    subs = db.execute(
        select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.id.desc())
    ).scalars()
    newest: Subscription | None = None
    for sub in subs:
        if sub.status in _LIVE_STATUSES:
            return sub
        newest = newest or sub
    return newest


async def create_checkout(client: DodoClient, user: User, plan: PlanName) -> str:
    """Create a hosted checkout session; does NOT change subscription state."""
    try:
        data = await client.create_checkout(
            product_id=_product_id(plan),
            email=user.email,
            name=user.full_name,
            return_url=f"{settings.FRONTEND_URL}/settings/billing",
            metadata={"user_id": str(user.id), "plan": plan},
            billing_country=settings.DODO_DEFAULT_BILLING_COUNTRY,
        )
    except DodoError as exc:
        raise AppException("Payment provider unavailable", "PAYMENT_PROVIDER_ERROR", 502) from exc
    url = data.get("checkout_url")
    if not isinstance(url, str) or not url:
        raise AppException(
            "Payment provider returned no checkout URL", "PAYMENT_PROVIDER_ERROR", 502
        )
    return url


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def process_webhook(db: Session, body: bytes, webhook_id: str | None = None) -> bool:
    """Apply a VERIFIED webhook payload. Returns True if state was applied.

    Replays (same ``webhook_id``) and out-of-order events (event ``timestamp`` older
    than the newest applied one for that subscription) are acknowledged but ignored.
    """
    try:
        event = json.loads(body)
    except ValueError:
        return False
    event = _dict(event)
    data = _dict(event.get("data"))
    etype = str(event.get("type"))
    status = EVENT_STATUS.get(etype)
    if status is None and etype in PAYLOAD_STATUS_EVENTS:
        status = PAYLOAD_STATUS.get(str(data.get("status")))
    if status is None or not data:
        return False

    if (
        webhook_id
        and db.execute(
            select(ProcessedWebhook.id).where(ProcessedWebhook.webhook_id == webhook_id)
        ).first()
    ):
        return False

    sub_id = data.get("subscription_id")
    has_sub_id = isinstance(sub_id, str) and bool(sub_id)
    metadata = _dict(data.get("metadata"))
    customer = _dict(data.get("customer"))

    sub: Subscription | None = None
    if has_sub_id:
        sub = db.execute(
            select(Subscription).where(Subscription.dodo_subscription_id == sub_id)
        ).scalar_one_or_none()
    if sub is None:
        try:
            user_id = int(metadata.get("user_id", ""))
        except (TypeError, ValueError):
            logger.warning("Webhook without resolvable user")
            return False
        if db.get(User, user_id) is None:
            return False
        # A new Dodo subscription id gets its own row, except that a row not yet bound
        # to any Dodo id is adopted. Without an id, update the relevant row.
        sub = get_subscription(db, user_id)
        if sub is not None and has_sub_id and sub.dodo_subscription_id is not None:
            sub = None
        if sub is None:
            sub = Subscription(user_id=user_id)
            db.add(sub)

    event_ts = _parse_dt(event.get("timestamp"))
    stale = (
        event_ts is not None
        and sub.last_event_at is not None
        and event_ts < _as_utc(sub.last_event_at)
    )
    if not stale:
        plan = metadata.get("plan")
        if plan in ("pro", "business"):
            sub.plan = plan
        sub.status = status
        if has_sub_id:
            sub.dodo_subscription_id = sub_id
        cust_id = customer.get("customer_id")
        if isinstance(cust_id, str) and cust_id:
            sub.dodo_customer_id = cust_id
        period_end = _parse_dt(data.get("next_billing_date"))
        if period_end:
            sub.current_period_end = period_end
        if event_ts:
            sub.last_event_at = event_ts
    if webhook_id:
        db.add(ProcessedWebhook(webhook_id=webhook_id))
    try:
        db.commit()
    except IntegrityError:  # concurrent delivery of the same webhook id / sub id
        db.rollback()
        return False
    return not stale
