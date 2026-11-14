"""CostModel (saved profit scenario) model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User

_MONEY = Numeric(12, 2)
_PCT = Numeric(8, 2)


class CostModel(Base):
    __tablename__ = "cost_models"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    asin: Mapped[str | None] = mapped_column(String(10), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(_MONEY, nullable=False, default=Decimal(0))
    shipping_cost: Mapped[Decimal] = mapped_column(_MONEY, nullable=False, default=Decimal(0))
    referral_fee: Mapped[Decimal] = mapped_column(_MONEY, nullable=False, default=Decimal(0))
    fba_fulfillment_fee: Mapped[Decimal] = mapped_column(_MONEY, nullable=False, default=Decimal(0))
    storage_fee: Mapped[Decimal] = mapped_column(_MONEY, nullable=False, default=Decimal(0))
    vat_tax: Mapped[Decimal] = mapped_column(_MONEY, nullable=False, default=Decimal(0))
    selling_price: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    target_roi: Mapped[Decimal | None] = mapped_column(_PCT, nullable=True)
    target_margin: Mapped[Decimal | None] = mapped_column(_PCT, nullable=True)
    net_profit: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    roi: Mapped[Decimal | None] = mapped_column(_PCT, nullable=True)
    margin: Mapped[Decimal | None] = mapped_column(_PCT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="cost_models")
