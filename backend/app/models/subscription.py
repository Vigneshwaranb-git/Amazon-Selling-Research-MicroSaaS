"""Subscription model (Dodo Payments)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    plan: Mapped[str] = mapped_column(
        String(50), nullable=False, default="free", server_default="free"
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="inactive", server_default="inactive"
    )
    dodo_customer_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    dodo_subscription_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # timestamp of the newest webhook event applied; older events are ignored
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="subscriptions")
