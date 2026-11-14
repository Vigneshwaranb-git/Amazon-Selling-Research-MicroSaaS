"""Product schemas."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

ASIN_PATTERN = r"^[A-Z0-9]{10}$"
ASIN_RE = re.compile(ASIN_PATTERN)

Asin = Annotated[str, Field(pattern=ASIN_PATTERN, min_length=10, max_length=10)]


class ProductBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asin: str
    title: str
    category: str | None = None
    image_url: str | None = None
    bsr: int | None = None
    estimated_monthly_sales: int | None = None
    estimated_monthly_revenue: Decimal | None = None
    price: Decimal | None = None
    rating: Decimal | None = None
    review_count: int | None = None
    saturation_score: int | None = None
    trend_score: int | None = None
    estimated_margin_pct: float | None = None
    updated_at: datetime | None = None


class ProductOut(ProductBase):
    pass


class ProductDetail(ProductBase):
    snapshot_count: int = 0


class ProductListResponse(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bsr: int | None = None
    price: Decimal | None = None
    estimated_sales: int | None = None
    rating: Decimal | None = None
    review_count: int | None = None
    captured_at: datetime


class ProductHistoryResponse(BaseModel):
    asin: str
    snapshots: list[SnapshotOut]
