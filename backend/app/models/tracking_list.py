"""TrackingList and TrackedProduct models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class TrackingList(Base):
    __tablename__ = "tracking_lists"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="tracking_lists")
    tracked_products: Mapped[list[TrackedProduct]] = relationship(
        back_populates="tracking_list", cascade="all, delete-orphan"
    )


class TrackedProduct(Base):
    __tablename__ = "tracked_products"
    __table_args__ = (
        UniqueConstraint("tracking_list_id", "product_id", name="uq_tracked_products_list_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tracking_list_id: Mapped[int] = mapped_column(
        ForeignKey("tracking_lists.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tracking_list: Mapped[TrackingList] = relationship(back_populates="tracked_products")
    product: Mapped[Product] = relationship(back_populates="tracked_in")
