"""Product query, seeding and export logic."""

import csv
import io
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.bsr_snapshot import BsrSnapshot
from app.models.product import Product
from app.services.providers.base import ProductDataProvider
from app.services.snapshot_job import upsert_product
from app.services.trend_scorer import estimate_margin_pct, margin_pct_sql

logger = logging.getLogger(__name__)

SEED_KEYWORDS = ["kitchen organizer", "yoga mat", "dog toy", "board game", "water bottle"]
SEED_PER_KEYWORD = 6
EXPORT_MAX_ROWS = 5000

SORT_COLUMNS: dict[str, Any] = {
    "bsr": Product.bsr,
    "sales": Product.estimated_monthly_sales,
    "revenue": Product.estimated_monthly_revenue,
    "price": Product.price,
    "trend": Product.trend_score,
    "saturation": Product.saturation_score,
}


@dataclass
class ProductFilters:
    category: str | None = None
    min_margin: float | None = None
    max_saturation: int | None = None
    min_trend: int | None = None
    search: str | None = None
    sort_by: str = "bsr"
    sort_dir: str = "asc"


def attach_margin(product: Product) -> Product:
    """Set the transient estimated_margin_pct attribute used by response schemas."""
    product.estimated_margin_pct = estimate_margin_pct(product.price)  # type: ignore[attr-defined]
    return product


async def seed_products(db: Session, provider: ProductDataProvider) -> int:
    count = 0
    for kw in SEED_KEYWORDS:
        for item in await provider.search_products(kw, limit=SEED_PER_KEYWORD):
            if await upsert_product(db, provider, item.asin) is not None:
                count += 1
    logger.info("Seeded %d products", count)
    return count


async def ensure_seeded(db: Session, provider: ProductDataProvider) -> None:
    if db.execute(select(func.count(Product.id))).scalar_one() == 0:
        await seed_products(db, provider)


def _apply_filters(stmt: Select[Any], f: ProductFilters) -> Select[Any]:
    if f.category:
        stmt = stmt.where(Product.category == f.category)
    if f.min_margin is not None:
        stmt = stmt.where(margin_pct_sql(Product.price) >= f.min_margin)
    if f.max_saturation is not None:
        stmt = stmt.where(Product.saturation_score <= f.max_saturation)
    if f.min_trend is not None:
        stmt = stmt.where(Product.trend_score >= f.min_trend)
    if f.search:
        escaped = f.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(Product.title.ilike(f"%{escaped}%", escape="\\"))
    return stmt


def _ordered(stmt: Select[Any], f: ProductFilters) -> Select[Any]:
    col = SORT_COLUMNS.get(f.sort_by, Product.bsr)
    order = col.desc().nulls_last() if f.sort_dir == "desc" else col.asc().nulls_last()
    return stmt.order_by(order, Product.id)


def list_products(
    db: Session, f: ProductFilters, page: int, page_size: int
) -> tuple[list[Product], int]:
    base = _apply_filters(select(Product), f)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    rows = (
        db.execute(_ordered(base, f).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return [attach_margin(p) for p in rows], total


def list_for_export(db: Session, f: ProductFilters) -> list[Product]:
    stmt = _ordered(_apply_filters(select(Product), f), f).limit(EXPORT_MAX_ROWS)
    return list(db.execute(stmt).scalars().all())


def get_product(db: Session, asin: str) -> Product:
    product = db.execute(select(Product).where(Product.asin == asin)).scalar_one_or_none()
    if product is None:
        raise NotFoundError("Product")
    return attach_margin(product)


async def get_or_fetch_product(db: Session, provider: ProductDataProvider, asin: str) -> Product:
    """Return a stored product or pull it from the provider; 404 if unknown."""
    product = db.execute(select(Product).where(Product.asin == asin)).scalar_one_or_none()
    if product is None:
        product = await upsert_product(db, provider, asin)
    if product is None:
        raise NotFoundError("Product")
    return attach_margin(product)


def snapshot_count(db: Session, product: Product) -> int:
    return db.execute(
        select(func.count(BsrSnapshot.id)).where(BsrSnapshot.product_id == product.id)
    ).scalar_one()


def get_history(db: Session, product: Product, limit: int) -> list[BsrSnapshot]:
    """Latest `limit` snapshots, returned oldest -> newest."""
    rows = (
        db.execute(
            select(BsrSnapshot)
            .where(BsrSnapshot.product_id == product.id)
            .order_by(BsrSnapshot.captured_at.desc(), BsrSnapshot.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return list(reversed(rows))


def _csv_safe(value: object) -> str:
    """Neutralise spreadsheet formula injection."""
    text = "" if value is None else str(value)
    if text and text[0] in "=+-@\t\r":
        return "'" + text
    return text


def products_to_csv(products: list[Product]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "asin",
            "title",
            "category",
            "bsr",
            "price",
            "rating",
            "review_count",
            "estimated_monthly_sales",
            "estimated_monthly_revenue",
            "estimated_margin_pct",
            "saturation_score",
            "trend_score",
        ]
    )
    for p in products:
        writer.writerow(
            [
                _csv_safe(v)
                for v in (
                    p.asin,
                    p.title,
                    p.category,
                    p.bsr,
                    p.price,
                    p.rating,
                    p.review_count,
                    p.estimated_monthly_sales,
                    p.estimated_monthly_revenue,
                    estimate_margin_pct(p.price),
                    p.saturation_score,
                    p.trend_score,
                )
            ]
        )
    return buf.getvalue()
