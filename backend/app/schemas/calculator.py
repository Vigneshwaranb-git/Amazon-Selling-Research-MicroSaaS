"""Schemas for the profit & FBA fee calculator."""

from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]

MAX_SIMULATION_POINTS = 200


class CostInputs(BaseModel):
    """Per-unit cost components (all non-negative)."""

    unit_cost: Money = Decimal("0")
    shipping_cost: Money = Decimal("0")
    referral_fee: Money = Decimal("0")
    fba_fulfillment_fee: Money = Decimal("0")
    storage_fee: Money = Decimal("0")
    vat_tax: Money = Decimal("0")


class CalculateRequest(CostInputs):
    selling_price: Money


class CalculationResult(BaseModel):
    selling_price: Decimal
    total_cost: Decimal
    net_profit: Decimal
    margin_pct: Decimal | None = Field(description="net_profit / selling_price * 100")
    roi_pct: Decimal | None = Field(description="net_profit / (unit_cost + shipping) * 100")
    break_even_price: Decimal


class PriceRange(BaseModel):
    min_price: PositiveMoney
    max_price: PositiveMoney
    step: PositiveMoney

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        if self.max_price < self.min_price:
            raise ValueError("max_price must be >= min_price")
        points = int((self.max_price - self.min_price) / self.step) + 1
        if points > MAX_SIMULATION_POINTS:
            raise ValueError(f"range yields more than {MAX_SIMULATION_POINTS} price points")
        return self


class SimulateRequest(CostInputs):
    prices: Annotated[list[Money], Field(min_length=1, max_length=MAX_SIMULATION_POINTS)] | None = (
        None
    )
    price_range: PriceRange | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.prices is None) == (self.price_range is None):
            raise ValueError("provide exactly one of prices or price_range")
        return self


class SimulateResponse(BaseModel):
    break_even_price: Decimal
    results: list[CalculationResult]
    best_profit_price: Decimal
    best_margin_price: Decimal | None
