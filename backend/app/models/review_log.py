"""ReviewLog model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.product import Product


class ReviewLog(Base):
    __tablename__ = "review_logs"
    __table_args__ = (
        UniqueConstraint("product_id", "review_id", name="uq_review_logs_product_review"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_logs_rating"),
        CheckConstraint(
            "sentiment_label IS NULL OR sentiment_label IN ('positive', 'neutral', 'negative')",
            name="ck_review_logs_sentiment_label",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    review_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rating: Mapped[int] = mapped_column(nullable=False)
    review_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    sentiment_label: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pain_points: Mapped[Any | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    product: Mapped[Product] = relationship(back_populates="reviews")
