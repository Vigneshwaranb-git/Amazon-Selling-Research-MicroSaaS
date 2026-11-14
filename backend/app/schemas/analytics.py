"""Pydantic schemas for the analytics module."""

import datetime as dt

from pydantic import BaseModel


class AnalyticsTotals(BaseModel):
    tracking_lists: int
    tracked_products: int
    scenarios: int


class TrendDistribution(BaseModel):
    rising: int = 0
    stable: int = 0
    declining: int = 0


class BsrPoint(BaseModel):
    date: dt.date
    avg_bsr: float


class TopMover(BaseModel):
    asin: str
    title: str
    # Percent change in BSR first -> last snapshot. Negative = rank improved (lower BSR).
    bsr_change_pct: float


class AnalyticsOverview(BaseModel):
    totals: AnalyticsTotals
    avg_scenario_margin: float | None
    trend_distribution: TrendDistribution
    bsr_series: list[BsrPoint]
    top_movers: list[TopMover]
