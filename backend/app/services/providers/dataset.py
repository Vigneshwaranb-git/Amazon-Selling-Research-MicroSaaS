"""ProductDataProvider backed by the local Amazon Reviews 2023 SQLite file.

Build the file with ``python -m app.data.import_amazon_2023`` (see ``app/data``). The dataset is a
single static snapshot, so this provider is deliberately honest about what it can and cannot say:

* ``bsr`` and ``price`` are real values from the dataset crawl, dated ``data_as_of`` (the end of
  the dataset's coverage, Sep 2023), NOT "now".
* ``monthly_sales_estimate`` is a heuristic, never a measurement: see
  :func:`estimate_monthly_sales_from_bsr`.
* ``saturation_score`` / ``trend_score`` are computed from real fields only (see
  :func:`compute_saturation` / :func:`compute_trend`).
* ``get_bsr_history`` returns the single real snapshot. No series is fabricated, and
  ``supports_live_snapshots`` is False so the snapshot job does not append identical points.
* ``seller_count`` is not in the dataset and is reported as 0 (unknown).
* Reviews are real, with real timestamps and star ratings.

LICENCE: the dataset has no explicit licence (research use; commercial use unresolved). See
``app.data.schema.LICENCE_NOTICE``.
"""

import asyncio
import logging
import math
import sqlite3
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.data import schema
from app.exceptions import AppException
from app.services.providers.base import (
    BSRPoint,
    ProductData,
    ProductDataProvider,
    Review,
)

logger = logging.getLogger(__name__)

# --- BSR -> sales heuristic (an ESTIMATE, not data) ---------------------------------------
# Crude power-law fit by John Mount (Win-Vector, 2014) to Hugh Howey's "50k Report" Kindle
# eBook data: daily units ~= 99,340 / rank^0.93, roughly valid for ranks 200..150,000. It is
# category- and year-specific, so treat results for other categories/ranks as order-of-magnitude.
SALES_DAILY_COEFFICIENT = 99_340.0
SALES_RANK_EXPONENT = 0.93
DAYS_PER_MONTH = 30
# The fit is not valid for ranks better than ~200 (it would claim >1M units/month for rank 2),
# so better ranks are treated as 200. This caps, not extrapolates, the estimate.
SALES_MIN_RANK = 200

# --- saturation score weights (sum = 100) -------------------------------------------------
SAT_W_REVIEWS = 40.0  # lifetime ratings count, log scale (saturates at 10,000)
SAT_W_CROWD = 30.0  # ranked+priced products in the same category, log scale (saturates at 5,000)
SAT_W_RANK = 20.0  # strong (low) best-seller rank means an entrenched incumbent, log scale
SAT_W_QUALITY = 10.0  # high average rating is harder to out-compete

# --- trend score --------------------------------------------------------------------------
TREND_MIN_REVIEWS = 10  # fewer reviews than this across both windows -> neutral 50
TREND_VELOCITY_SPAN = 40.0  # +/-40 points for review velocity going from 0% to +/-100%
TREND_RATING_SCALE = 2.5  # points per star of rating change, capped at +/-10
TREND_RATING_CAP = 10.0

MAX_SEARCH_LIMIT = 200


class DatasetConfigError(AppException):
    """DATA_PROVIDER=dataset but the dataset file is missing, unreadable or incompatible."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "DATA_PROVIDER_NOT_CONFIGURED", 503)


def estimate_monthly_sales_from_bsr(bsr: int) -> int:
    """ESTIMATED monthly unit sales: ``30 * 99340 / max(bsr, 200)**0.93`` (min 1).

    A heuristic, not data: a crude Kindle-eBook fit applied to other categories.
    """
    rank = max(bsr, SALES_MIN_RANK)
    return max(1, round(DAYS_PER_MONTH * SALES_DAILY_COEFFICIENT / (rank**SALES_RANK_EXPONENT)))


def _log_ratio(value: float, saturation_at: float) -> float:
    """log10(1+value)/log10(1+saturation_at), clamped to [0, 1]."""
    if value <= 0:
        return 0.0
    return min(1.0, math.log10(1 + value) / math.log10(1 + saturation_at))


def compute_saturation(review_count: int, rating: float, bsr: int, n_in_category: int) -> int:
    """0-100, higher = more saturated. Built only from real dataset fields.

    ``40*log-scaled ratings count + 30*log-scaled products in category
    + 20*(1 - log10(bsr)/6) + 10*rating/5``.
    """
    reviews = SAT_W_REVIEWS * _log_ratio(review_count, 10_000)
    crowd = SAT_W_CROWD * _log_ratio(n_in_category, 5_000)
    rank = SAT_W_RANK * (1.0 - min(1.0, math.log10(max(bsr, 1)) / 6.0))
    quality = SAT_W_QUALITY * max(0.0, min(rating, 5.0)) / 5.0
    return int(max(0, min(100, round(reviews + crowd + rank + quality))))


def compute_trend(
    reviews_last12: int,
    reviews_prior12: int,
    rating_last12: float | None,
    rating_prior12: float | None,
) -> int:
    """0-100, 50 = flat. Review velocity (last 12 months vs the prior 12 before the dataset end).

    ``50 + 40*(l - p)/max(l, p)`` plus up to +/-10 for the rating change (2.5 points per star)
    when both windows have reviews. Neutral 50 when there are fewer than 10 reviews in both
    windows combined (not enough evidence). Based on real review timestamps.
    """
    if reviews_last12 + reviews_prior12 < TREND_MIN_REVIEWS:
        return 50
    top = max(reviews_last12, reviews_prior12)
    score = 50.0 + TREND_VELOCITY_SPAN * (reviews_last12 - reviews_prior12) / top
    if rating_last12 is not None and rating_prior12 is not None:
        delta = (rating_last12 - rating_prior12) * TREND_RATING_SCALE
        score += max(-TREND_RATING_CAP, min(TREND_RATING_CAP, delta))
    return int(max(0, min(100, round(score))))


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class DatasetProductDataProvider(ProductDataProvider):
    """Read-only access to the imported dataset. Safe to share across threads/requests.

    Every query opens its own short-lived read-only connection (sqlite3 connections must not be
    shared between threads) and runs in ``asyncio.to_thread`` so the event loop is never blocked.
    """

    supports_live_snapshots = False

    def __init__(self, path: str | Path) -> None:
        self.path = schema.resolve_dataset_path(path)
        self._uri = self.path.resolve().as_uri() + "?mode=ro"
        self.info = self._load_info()
        self.data_as_of = self._parse_as_of(self.info.get("data_as_of", ""))
        self._category_counts: dict[str, int] = {
            row["category"]: row["n_products"]
            for row in self._query("SELECT category, n_products FROM category_stats")
        }

    # ------------------------------------------------------------------ setup / validation
    def _fail(self, reason: str) -> DatasetConfigError:
        return DatasetConfigError(
            f"DATA_PROVIDER=dataset but the dataset file '{self.path}' {reason}. "
            f"Build it with: cd backend && {schema.import_command()} "
            "(or set DATA_PROVIDER=mock)."
        )

    def _load_info(self) -> dict[str, str]:
        if not self.path.is_file():
            raise self._fail("does not exist")
        try:
            rows = self._query("SELECT key, value FROM meta")
            count = self._query("SELECT COUNT(*) AS n FROM products")[0]["n"]
        except sqlite3.Error as exc:
            raise self._fail(f"is not a valid dataset file ({exc})") from exc
        info = {r["key"]: r["value"] for r in rows}
        if info.get("schema_version") != schema.SCHEMA_VERSION:
            raise self._fail("has an incompatible schema version")
        if count < 1:
            raise self._fail("contains no products")
        return info

    @staticmethod
    def _parse_as_of(value: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return date.fromisoformat(schema.DATASET_AS_OF)

    # ------------------------------------------------------------------ sync internals
    def _query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        conn = sqlite3.connect(self._uri, uri=True, timeout=10)
        try:
            conn.row_factory = sqlite3.Row
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def _to_product(self, row: sqlite3.Row) -> ProductData:
        bsr = int(row["bsr"])
        rating = float(row["rating"])
        review_count = int(row["review_count"])
        n_in_category = self._category_counts.get(row["category"], 1)
        return ProductData(
            asin=row["asin"],
            title=row["title"],
            brand=row["brand"],
            category=row["category"],
            price=Decimal(str(round(row["price"], 2))),
            bsr=bsr,
            rating=rating,
            review_count=review_count,
            monthly_sales_estimate=estimate_monthly_sales_from_bsr(bsr),
            seller_count=0,  # not in the dataset: unknown, never fabricated
            image_url=row["image_url"],
            saturation_score=compute_saturation(review_count, rating, bsr, n_in_category),
            trend_score=compute_trend(
                int(row["reviews_last12"]),
                int(row["reviews_prior12"]),
                row["rating_last12"],
                row["rating_prior12"],
            ),
            data_as_of=self.data_as_of,
        )

    def _get_product_sync(self, asin: str) -> ProductData | None:
        rows = self._query("SELECT * FROM products WHERE asin = ?", (asin,))
        return self._to_product(rows[0]) if rows else None

    def _search_sync(self, keyword: str, category: str | None, limit: int) -> list[ProductData]:
        conds: list[str] = []
        params: list[Any] = []
        for term in keyword.split()[:8]:
            like = f"%{_escape_like(term)}%"
            conds.append("(title LIKE ? ESCAPE '\\' OR brand LIKE ? ESCAPE '\\')")
            params += [like, like]
        if category:
            conds.append("category = ? COLLATE NOCASE")
            params.append(category)
        where = f"WHERE {' AND '.join(conds)}" if conds else ""
        limit = max(1, min(limit, MAX_SEARCH_LIMIT))
        rows = self._query(
            f"SELECT * FROM products {where} ORDER BY bsr, asin LIMIT ?", [*params, limit]
        )
        return [self._to_product(r) for r in rows]

    def _reviews_sync(self, asin: str, limit: int) -> list[Review]:
        rows = self._query(
            "SELECT id, rating, title, body, ts FROM reviews WHERE asin = ? "
            "ORDER BY ts DESC, id LIMIT ?",
            (asin, max(0, limit)),
        )
        return [
            Review(
                id=r["id"],
                rating=int(r["rating"]),
                title=r["title"],
                body=r["body"],
                reviewed_at=datetime.fromtimestamp(int(r["ts"]), UTC).date(),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------ ProductDataProvider
    async def get_product(self, asin: str) -> ProductData | None:
        return await asyncio.to_thread(self._get_product_sync, asin)

    async def search_products(
        self, keyword: str, category: str | None = None, limit: int = 20
    ) -> list[ProductData]:
        return await asyncio.to_thread(self._search_sync, keyword, category, limit)

    async def get_bsr_history(self, asin: str, days: int = 30) -> list[BSRPoint]:
        """The ONE real snapshot, dated with the dataset date. ``days`` is ignored: no series."""
        product = await self.get_product(asin)
        if product is None:
            return []
        return [
            BSRPoint(
                day=self.data_as_of,
                bsr=product.bsr,
                price=product.price,
                estimated_sales=product.monthly_sales_estimate,
            )
        ]

    async def get_reviews(self, asin: str, limit: int = 50) -> list[Review]:
        return await asyncio.to_thread(self._reviews_sync, asin, limit)

    async def seed_asins(self, limit: int) -> list[str] | None:
        rows = await asyncio.to_thread(
            self._query, "SELECT asin FROM products ORDER BY bsr, asin LIMIT ?", (limit,)
        )
        return [r["asin"] for r in rows]

    # ------------------------------------------------------------------ metadata for the API
    def data_source_notes(self) -> list[str]:
        as_of = self.data_as_of.isoformat()
        notes = [
            f"BSR and price are a single snapshot from {as_of}, not live data.",
            "BSR is the rank in the product's own Amazon category as recorded in the dataset "
            "(mostly the imported category), not a site-wide rank.",
            "Sales figures are estimates (heuristic from BSR), not measured sales.",
            "Saturation and trend scores are computed from review counts, ratings and review "
            "dates in the dataset.",
            "Seller counts are not available in this dataset.",
            "Dataset is for research/demo use; see licence (no explicit licence; commercial use "
            "unresolved). Not affiliated with Amazon.",
        ]
        if self.info.get("reviews_truncated") == "1":
            notes.append("Review activity is partial: the reviews file was cut off at import.")
        return notes
