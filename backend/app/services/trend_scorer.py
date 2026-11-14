"""Pure scoring functions for saturation and trend (0-100) and margin estimates."""

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import Numeric, cast, func

REFERRAL_FEE_RATE = Decimal("0.15")
ASSUMED_COGS_RATE = Decimal("0.30")
ASSUMED_FBA_FEE = Decimal("3.50")


def clamp(value: float, low: int = 0, high: int = 100) -> int:
    return int(max(low, min(high, round(value))))


def estimate_margin_pct(price: Decimal | None) -> float | None:
    """Rough margin %: price minus referral, assumed COGS and flat FBA fee."""
    if price is None or price <= 0:
        return None
    net = price * (1 - REFERRAL_FEE_RATE - ASSUMED_COGS_RATE) - ASSUMED_FBA_FEE
    return round(float(net / price * 100), 2)


def margin_pct_sql(price_col: Any) -> Any:
    """SQL twin of estimate_margin_pct (NULL when price is NULL or <= 0)."""
    keep = float(1 - REFERRAL_FEE_RATE - ASSUMED_COGS_RATE)
    safe_price = cast(func.nullif(price_col, 0), Numeric(14, 4))
    return (keep - float(ASSUMED_FBA_FEE) / safe_price) * 100


def estimate_monthly_sales(bsr: int | None) -> int | None:
    """Power-law BSR -> monthly unit sales approximation."""
    if bsr is None or bsr <= 0:
        return None
    return max(1, int(1_500_000 * (bsr**-0.75)))


def saturation_score(
    review_count: int | None,
    rating: float | None,
    seller_count: int | None = None,
    bsr: int | None = None,
) -> int:
    """Higher = more saturated/competitive. Blends reviews, sellers, rank."""
    reviews = min(review_count or 0, 10_000) / 10_000 * 40
    sellers = min(seller_count, 30) / 30 * 40 if seller_count is not None else 20.0
    rank = 0.0
    if bsr is not None and bsr > 0:
        rank = max(0.0, 1 - min(bsr, 100_000) / 100_000) * 15
    quality = ((rating or 0) / 5) * 5
    return clamp(reviews + sellers + rank + quality)


def trend_score(bsr_series: Sequence[int], sales_series: Sequence[int] | None = None) -> int:
    """0-100, 50 = flat. Falling BSR (improving rank) and rising sales score higher.

    Series are ordered oldest -> newest. Fewer than 2 points -> neutral 50.
    """
    values = [b for b in bsr_series if b and b > 0]
    if len(values) < 2:
        return 50
    half = max(1, len(values) // 2)
    early = sum(values[:half]) / half
    late = sum(values[-half:]) / half
    # relative improvement: positive when BSR falls (rank improves)
    rank_change = (early - late) / max(early, late)
    score = 50 + rank_change * 50
    if sales_series:
        sales = [s for s in sales_series if s and s > 0]
        if len(sales) >= 2:
            h = max(1, len(sales) // 2)
            s_early = sum(sales[:h]) / h
            s_late = sum(sales[-h:]) / h
            sales_change = (s_late - s_early) / max(s_early, s_late)
            score = score * 0.6 + (50 + sales_change * 50) * 0.4
    return clamp(score)
