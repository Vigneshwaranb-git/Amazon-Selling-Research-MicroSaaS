"""Snapshot job: capture BSR snapshots via ProductDataProvider (append-only)."""

import logging
from datetime import UTC, datetime, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bsr_snapshot import BsrSnapshot
from app.models.product import Product
from app.services.providers.base import ProductData, ProductDataProvider
from app.services.trend_scorer import (
    estimate_monthly_sales,
    saturation_score,
    trend_score,
)

logger = logging.getLogger(__name__)

HISTORY_BACKFILL_DAYS = 30
TREND_WINDOW = 60


def apply_product_data(product: Product, data: ProductData) -> None:
    """Copy provider data onto the product row (current state, mutable)."""
    product.title = data.title
    product.category = data.category
    product.image_url = data.image_url or None
    product.bsr = data.bsr
    product.price = data.price
    product.rating = Decimal(str(data.rating))
    product.review_count = data.review_count
    product.estimated_monthly_sales = data.monthly_sales_estimate
    product.estimated_monthly_revenue = (data.price * data.monthly_sales_estimate).quantize(
        Decimal("0.01")
    )
    product.saturation_score = saturation_score(
        data.review_count, data.rating, data.seller_count, data.bsr
    )


def recompute_trend(db: Session, product: Product) -> None:
    rows = list(
        db.execute(
            select(BsrSnapshot.bsr, BsrSnapshot.estimated_sales)
            .where(BsrSnapshot.product_id == product.id)
            .order_by(BsrSnapshot.captured_at.desc(), BsrSnapshot.id.desc())
            .limit(TREND_WINDOW)
        ).all()
    )
    rows.reverse()
    product.trend_score = trend_score(
        [r[0] for r in rows if r[0] is not None],
        [r[1] for r in rows if r[1] is not None],
    )


def append_snapshot(db: Session, product: Product) -> None:
    """Append one snapshot of the product's current state. Never updates old rows."""
    db.add(
        BsrSnapshot(
            product_id=product.id,
            bsr=product.bsr,
            price=product.price,
            estimated_sales=product.estimated_monthly_sales,
            rating=product.rating,
            review_count=product.review_count,
            captured_at=datetime.now(UTC),
        )
    )


async def backfill_history(db: Session, product: Product, provider: ProductDataProvider) -> int:
    """Insert provider history for a newly created product."""
    points = await provider.get_bsr_history(product.asin, days=HISTORY_BACKFILL_DAYS)
    for p in points:
        db.add(
            BsrSnapshot(
                product_id=product.id,
                bsr=p.bsr,
                price=p.price,
                estimated_sales=estimate_monthly_sales(p.bsr),
                rating=product.rating,
                review_count=product.review_count,
                captured_at=datetime.combine(p.day, time.min, tzinfo=UTC),
            )
        )
    return len(points)


async def upsert_product(db: Session, provider: ProductDataProvider, asin: str) -> Product | None:
    """Create or refresh a product from the provider; backfill history on first sight."""
    data = await provider.get_product(asin)
    if data is None:
        return None
    product = db.execute(select(Product).where(Product.asin == asin)).scalar_one_or_none()
    created = product is None
    if product is None:
        product = Product(asin=asin, title=data.title)
        db.add(product)
    apply_product_data(product, data)
    db.flush()
    if created:
        await backfill_history(db, product, provider)
    append_snapshot(db, product)
    db.flush()
    recompute_trend(db, product)
    db.commit()
    db.refresh(product)
    return product


async def run_snapshot_job(
    db: Session, provider: ProductDataProvider, asins: list[str] | None = None
) -> int:
    """Capture a new snapshot for every product (or the given ASINs).

    Returns the number of products refreshed. A failure for one ASIN is logged
    and does not stop the job.
    """
    stmt = select(Product.asin)
    if asins is not None:
        stmt = stmt.where(Product.asin.in_(asins))
    targets = list(db.execute(stmt).scalars())
    refreshed = 0
    for asin in targets:
        try:
            if await upsert_product(db, provider, asin) is not None:
                refreshed += 1
        except Exception:
            db.rollback()
            logger.exception("Snapshot failed for %s", asin)
    logger.info("Snapshot job refreshed %d/%d products", refreshed, len(targets))
    return refreshed
