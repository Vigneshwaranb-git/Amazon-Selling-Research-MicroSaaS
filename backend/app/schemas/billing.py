"""Billing schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

PlanName = Literal["pro", "business"]


class CheckoutRequest(BaseModel):
    plan: PlanName


class CheckoutResponse(BaseModel):
    checkout_url: str


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan: str
    status: str
    current_period_end: datetime | None = None


class WebhookAck(BaseModel):
    received: bool = True
    processed: bool
