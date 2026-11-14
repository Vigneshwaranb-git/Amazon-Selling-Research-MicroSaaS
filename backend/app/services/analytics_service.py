"""Analytics aggregates, scoped to one user. All work is done in aggregate SQL."""

import datetime as dt
from typing import Any

from sqlalchemy import Date, Float, case, cast, func, select
from sqlalchemy.orm import Session

from app.models.bsr_snapshot import BsrSnapshot
from app.models.cost_model import CostModel
from app.models.product import Product
from app.models.tracking_list import TrackedProduct, TrackingList
from app.schemas.analytics import (
    AnalyticsOverview,
    AnalyticsTotals,
    BsrPoint,
    TopMover,
    TrendDistribution,
)

RISING_MIN = 60
DECLINING_MAX = 40
MAX_MOVERS = 5


def _tracked_product_ids(user_id: int) -> Any:
    return (
        select(TrackedProduct.product_id)
        .join(TrackingList, TrackingList.id == TrackedProduct.tracking_list_id)
        .where(TrackingList.user_id == user_id)
        .distinct()
    )


def get_overview(db: Session, user_id: int, days: int) -> AnalyticsOverview:
    pids = _tracked_product_ids(user_id).scalar_subquery()

    lists = db.scalar(select(func.count(TrackingList.id)).where(TrackingList.user_id == user_id))
    tracked = db.scalar(select(func.count()).select_from(_tracked_product_ids(user_id).subquery()))
    scen_count, avg_margin = db.execute(
        select(func.count(CostModel.id), func.avg(CostModel.margin)).where(
            CostModel.user_id == user_id
        )
    ).one()

    t = db.execute(
        select(
            func.count(Product.id).filter(Product.trend_score >= RISING_MIN),
            func.count(Product.id).filter(Product.trend_score <= DECLINING_MAX),
            func.count(Product.id).filter(
                Product.trend_score > DECLINING_MAX, Product.trend_score < RISING_MIN
            ),
        ).where(Product.id.in_(pids))
    ).one()

    # Latest N distinct snapshot dates (history is not anchored to "now").
    day = func.date(BsrSnapshot.captured_at, type_=Date).label("day")
    rows = db.execute(
        select(day, func.avg(BsrSnapshot.bsr))
        .where(BsrSnapshot.product_id.in_(pids), BsrSnapshot.bsr.is_not(None))
        .group_by(day)
        .order_by(day.desc())
        .limit(days)
    ).all()
    series = [BsrPoint(date=_as_date(d), avg_bsr=round(float(a), 2)) for d, a in reversed(rows)]

    movers = _top_movers(db, pids, _as_date(rows[-1][0])) if rows else []

    return AnalyticsOverview(
        totals=AnalyticsTotals(
            tracking_lists=lists or 0, tracked_products=tracked or 0, scenarios=scen_count or 0
        ),
        avg_scenario_margin=round(float(avg_margin), 2) if avg_margin is not None else None,
        trend_distribution=TrendDistribution(rising=t[0], declining=t[1], stable=t[2]),
        bsr_series=series,
        top_movers=movers,
    )


def _as_date(value: Any) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


def _top_movers(db: Session, pids: Any, start_day: dt.date) -> list[TopMover]:
    """Largest |BSR change| between each product's first and last snapshot in the window."""
    ranked = (
        select(
            BsrSnapshot.product_id.label("pid"),
            BsrSnapshot.bsr.label("bsr"),
            func.row_number()
            .over(
                partition_by=BsrSnapshot.product_id,
                order_by=(BsrSnapshot.captured_at.asc(), BsrSnapshot.id.asc()),
            )
            .label("rn_asc"),
            func.row_number()
            .over(
                partition_by=BsrSnapshot.product_id,
                order_by=(BsrSnapshot.captured_at.desc(), BsrSnapshot.id.desc()),
            )
            .label("rn_desc"),
        )
        .where(
            BsrSnapshot.product_id.in_(pids),
            BsrSnapshot.bsr.is_not(None),
            func.date(BsrSnapshot.captured_at, type_=Date) >= start_day,
        )
        .subquery()
    )
    first = func.max(case((ranked.c.rn_asc == 1, ranked.c.bsr))).label("first_bsr")
    last = func.max(case((ranked.c.rn_desc == 1, ranked.c.bsr))).label("last_bsr")
    per_product = (
        select(ranked.c.pid, first, last).group_by(ranked.c.pid).having(func.count() > 1).subquery()
    )
    pct = (
        (cast(per_product.c.last_bsr, Float) - per_product.c.first_bsr)
        * 100.0
        / per_product.c.first_bsr
    )
    out = db.execute(
        select(Product.asin, Product.title, pct.label("pct"))
        .join(per_product, per_product.c.pid == Product.id)
        .where(per_product.c.first_bsr > 0, per_product.c.last_bsr != per_product.c.first_bsr)
        .order_by(func.abs(pct).desc(), Product.asin)
        .limit(MAX_MOVERS)
    ).all()
    return [TopMover(asin=a, title=ti, bsr_change_pct=round(float(p), 2)) for a, ti, p in out]
