"""Pure profit / FBA fee calculations. Decimal math only; no I/O."""

from collections.abc import Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal

from app.schemas.calculator import (
    CalculateRequest,
    CalculationResult,
    CostInputs,
    PriceRange,
    SimulateRequest,
    SimulateResponse,
)

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def quantize(value: Decimal) -> Decimal:
    """Round half-up to cents."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def total_cost(costs: CostInputs) -> Decimal:
    return (
        costs.unit_cost
        + costs.shipping_cost
        + costs.referral_fee
        + costs.fba_fulfillment_fee
        + costs.storage_fee
        + costs.vat_tax
    )


def calculate_net_profit(selling_price: Decimal, costs: CostInputs) -> Decimal:
    return selling_price - total_cost(costs)


def calculate_margin_pct(net_profit: Decimal, selling_price: Decimal) -> Decimal | None:
    """Margin percent, or None when selling price is zero."""
    if selling_price == 0:
        return None
    return quantize(net_profit / selling_price * HUNDRED)


def calculate_roi_pct(net_profit: Decimal, costs: CostInputs) -> Decimal | None:
    """ROI percent on (unit_cost + shipping), or None when that base is zero."""
    investment = costs.unit_cost + costs.shipping_cost
    if investment == 0:
        return None
    return quantize(net_profit / investment * HUNDRED)


def calculate_break_even_price(costs: CostInputs) -> Decimal:
    """Selling price at which net profit is exactly zero."""
    return quantize(total_cost(costs))


def calculate(request: CalculateRequest) -> CalculationResult:
    price = request.selling_price
    net = calculate_net_profit(price, request)
    return CalculationResult(
        selling_price=quantize(price),
        total_cost=quantize(total_cost(request)),
        net_profit=quantize(net),
        margin_pct=calculate_margin_pct(net, price),
        roi_pct=calculate_roi_pct(net, request),
        break_even_price=calculate_break_even_price(request),
    )


def expand_price_range(price_range: PriceRange) -> list[Decimal]:
    prices: list[Decimal] = []
    current = price_range.min_price
    while current <= price_range.max_price:
        prices.append(current)
        current += price_range.step
    return prices


def _calculate_for_prices(costs: CostInputs, prices: Iterable[Decimal]) -> list[CalculationResult]:
    base = costs.model_dump()
    return [calculate(CalculateRequest(**base, selling_price=p)) for p in prices]


def _best_margin_price(results: Sequence[CalculationResult]) -> Decimal | None:
    with_margin = [r for r in results if r.margin_pct is not None]
    if not with_margin:
        return None
    return max(with_margin, key=lambda r: r.margin_pct or Decimal(0)).selling_price


def simulate(request: SimulateRequest) -> SimulateResponse:
    if request.price_range is not None:
        prices = expand_price_range(request.price_range)
    else:
        prices = list(request.prices or [])
    costs = CostInputs(**request.model_dump(exclude={"prices", "price_range"}))
    results = _calculate_for_prices(costs, prices)
    best_profit = max(results, key=lambda r: r.net_profit)
    return SimulateResponse(
        break_even_price=calculate_break_even_price(costs),
        results=results,
        best_profit_price=best_profit.selling_price,
        best_margin_price=_best_margin_price(results),
    )
