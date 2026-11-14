"""Schemas for saved profit scenarios."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.calculator import CalculateRequest

Pct = Annotated[Decimal, Field(ge=0, le=100000, max_digits=8, decimal_places=2)]


class ScenarioBase(CalculateRequest):
    name: Annotated[str, Field(min_length=1, max_length=150)]
    asin: Annotated[str, Field(pattern=r"^[A-Za-z0-9]{10}$")] | None = None
    target_roi: Pct | None = None
    target_margin: Pct | None = None


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioUpdate(ScenarioBase):
    """Full replacement (PUT)."""


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asin: str | None
    name: str
    unit_cost: Decimal
    shipping_cost: Decimal
    referral_fee: Decimal
    fba_fulfillment_fee: Decimal
    storage_fee: Decimal
    vat_tax: Decimal
    selling_price: Decimal
    target_roi: Decimal | None
    target_margin: Decimal | None
    net_profit: Decimal | None
    roi: Decimal | None
    margin: Decimal | None
    created_at: datetime
