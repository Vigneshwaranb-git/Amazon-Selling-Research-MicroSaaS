"""Review storage, filtering, analysis orchestration and aggregation."""

import json
import logging
from collections import Counter
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.product import Product
from app.models.review_log import ReviewLog
from app.models.review_summary import ReviewSummary
from app.schemas.review import PainPointOut, ReviewSummaryOut
from app.services import product_service
from app.services.providers.base import LLMProvider, ProductDataProvider
from app.services.sentiment_service import analyze_reviews

logger = logging.getLogger(__name__)

REVIEW_FETCH_LIMIT = 50
EXAMPLE_CHARS = 200


def _to_datetime(day: date | None) -> datetime | None:
    return None if day is None else datetime.combine(day, time.min, tzinfo=UTC)


def get_product_or_404(db: Session, asin: str) -> Product:
    product = db.execute(select(Product).where(Product.asin == asin)).scalar_one_or_none()
    if product is None:
        raise NotFoundError("Product")
    return product


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_reviews(
    db: Session,
    product: Product,
    rating: int | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[ReviewLog], int]:
    conds: list[Any] = [ReviewLog.product_id == product.id]
    if rating is not None:
        conds.append(ReviewLog.rating == rating)
    if keyword:
        conds.append(ReviewLog.review_text.ilike(f"%{escape_like(keyword)}%", escape="\\"))
    total = db.execute(select(func.count(ReviewLog.id)).where(*conds)).scalar_one()
    rows = (
        db.execute(
            select(ReviewLog)
            .where(*conds)
            .order_by(ReviewLog.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def _load(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    return [str(x) for x in data] if isinstance(data, list) else []


def to_summary_out(asin: str, summary: ReviewSummary) -> ReviewSummaryOut:
    return ReviewSummaryOut(
        asin=asin,
        pros=_load(summary.pros),
        cons=_load(summary.cons),
        opportunities=_load(summary.opportunities),
        generated_at=summary.generated_at,
    )


def get_summary(db: Session, product: Product) -> ReviewSummary:
    summary = (
        db.execute(
            select(ReviewSummary)
            .where(ReviewSummary.product_id == product.id)
            .order_by(ReviewSummary.generated_at.desc(), ReviewSummary.id.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if summary is None:
        raise NotFoundError("Review summary")
    return summary


async def analyze_product(
    db: Session,
    data_provider: ProductDataProvider,
    llm: LLMProvider,
    asin: str,
) -> tuple[int, ReviewSummary, Product]:
    product = await product_service.get_or_fetch_product(db, data_provider, asin)
    fetched = await data_provider.get_reviews(asin, limit=REVIEW_FETCH_LIMIT)
    analysis = await analyze_reviews(llm, fetched)

    existing = {
        r.review_id: r
        for r in db.execute(select(ReviewLog).where(ReviewLog.product_id == product.id))
        .scalars()
        .all()
    }
    for review in analysis.reviews:
        result = analysis.per_review[review.id]
        row = existing.get(review.id)
        if row is None:
            row = ReviewLog(product_id=product.id, review_id=review.id, rating=review.rating)
            db.add(row)
            existing[review.id] = row
        row.rating = review.rating
        row.review_text = review.body
        if review.reviewed_at is not None:
            row.reviewed_at = _to_datetime(review.reviewed_at)
        row.sentiment_score = Decimal(str(round(result.score, 4)))
        row.sentiment_label = result.label
        row.pain_points = list(result.pain_points)

    summary = (
        db.execute(select(ReviewSummary).where(ReviewSummary.product_id == product.id))
        .scalars()
        .first()
    )
    if summary is None:
        summary = ReviewSummary(product_id=product.id)
        db.add(summary)
    insights = analysis.insights
    summary.pros = json.dumps(insights.pros)
    summary.cons = json.dumps(insights.cons)
    summary.opportunities = json.dumps(insights.opportunities)
    summary.generated_at = datetime.now(UTC)
    db.commit()
    db.refresh(summary)
    return len(analysis.per_review), summary, product


def pain_point_stats(db: Session, product: Product) -> list[PainPointOut]:
    rows = (
        db.execute(
            select(ReviewLog)
            .where(ReviewLog.product_id == product.id, ReviewLog.pain_points.is_not(None))
            .order_by(ReviewLog.id.asc())
        )
        .scalars()
        .all()
    )
    counts: Counter[str] = Counter()
    examples: dict[str, str] = {}
    for row in rows:
        for label in row.pain_points or []:
            counts[label] += 1
            examples.setdefault(label, (row.review_text or "")[:EXAMPLE_CHARS])
    total = sum(counts.values())
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        PainPointOut(
            label=label,
            count=count,
            share_pct=round(count * 100 / total, 1),
            example=examples[label],
        )
        for label, count in ranked
    ]
