"""Product model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.bsr_snapshot import BsrSnapshot
    from app.models.review_log import ReviewLog
    from app.models.review_summary import ReviewSummary
    from app.models.tracking_list import TrackedProduct


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "saturation_score IS NULL OR (saturation_score >= 0 AND saturation_score <= 100)",
            name="ck_products_saturation_score",
        ),
        CheckConstraint(
            "trend_score IS NULL OR (trend_score >= 0 AND trend_score <= 100)",
            name="ck_products_trend_score",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asin: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    bsr: Mapped[int | None] = mapped_column(index=True, nullable=True)
    estimated_monthly_sales: Mapped[int | None] = mapped_column(nullable=True)
    estimated_monthly_revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    review_count: Mapped[int | None] = mapped_column(nullable=True)
    saturation_score: Mapped[int | None] = mapped_column(nullable=True)
    trend_score: Mapped[int | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    snapshots: Mapped[list[BsrSnapshot]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    tracked_in: Mapped[list[TrackedProduct]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[ReviewLog]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    review_summaries: Mapped[list[ReviewSummary]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
