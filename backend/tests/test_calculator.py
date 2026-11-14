"""Tests for the profit calculator service and endpoints."""

from collections.abc import Iterator
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.dependencies import get_current_user
from app.main import app
from app.schemas.calculator import CalculateRequest, CostInputs, SimulateRequest
from app.services import calculator_service as calc

D = Decimal


def make(**kw: object) -> CalculateRequest:
    return CalculateRequest(**kw)  # type: ignore[arg-type]


FULL = {
    "unit_cost": "10.00",
    "shipping_cost": "2.00",
    "referral_fee": "3.00",
    "fba_fulfillment_fee": "4.00",
    "storage_fee": "0.50",
    "vat_tax": "0.50",
    "selling_price": "30.00",
}


def test_known_values() -> None:
    r = calc.calculate(make(**FULL))
    assert r.total_cost == D("20.00")
    assert r.net_profit == D("10.00")
    assert r.margin_pct == D("33.33")
    assert r.roi_pct == D("83.33")  # 10 / 12
    assert r.break_even_price == D("20.00")


def test_negative_profit() -> None:
    r = calc.calculate(make(unit_cost="20", selling_price="15"))
    assert r.net_profit == D("-5.00")
    assert r.margin_pct == D("-33.33")
    assert r.roi_pct == D("-25.00")


def test_rounding_half_up() -> None:
    # margin = 1/8 * 100 = 12.5 exactly; roi 0.005/... check half-up on cents
    assert calc.quantize(D("0.005")) == D("0.01")
    assert calc.quantize(D("2.675")) == D("2.68")
    r = make(unit_cost="1", selling_price="1.01")
    out = calc.calculate(r)
    assert out.margin_pct == D("0.99")  # 0.01/1.01*100 = 0.990099
    assert out.roi_pct == D("1.00")


def test_zero_price_guard() -> None:
    r = calc.calculate(make(unit_cost="5", selling_price="0"))
    assert r.margin_pct is None
    assert r.net_profit == D("-5.00")
    assert r.roi_pct == D("-100.00")


def test_zero_investment_roi_guard() -> None:
    r = calc.calculate(make(referral_fee="3", selling_price="10"))
    assert r.roi_pct is None
    assert r.net_profit == D("7.00")


def test_all_zero() -> None:
    r = calc.calculate(make(selling_price="0"))
    assert r.margin_pct is None and r.roi_pct is None
    assert r.net_profit == D("0.00")


def test_results_are_decimal_not_float() -> None:
    r = calc.calculate(make(**FULL))
    for v in (r.total_cost, r.net_profit, r.margin_pct, r.roi_pct, r.break_even_price):
        assert isinstance(v, Decimal)


def test_break_even_gives_zero_profit() -> None:
    costs = CostInputs(unit_cost=D("7.13"), referral_fee=D("1.07"), vat_tax=D("0.33"))
    be = calc.calculate_break_even_price(costs)
    r = calc.calculate(CalculateRequest(**costs.model_dump(), selling_price=be))
    assert r.net_profit == D("0.00")


@pytest.mark.parametrize("field", list(CostInputs.model_fields) + ["selling_price"])
def test_negative_inputs_rejected(field: str) -> None:
    data = {**FULL, field: "-0.01"}
    with pytest.raises(ValidationError):
        CalculateRequest(**data)  # type: ignore[arg-type]


def test_simulate_list_and_best() -> None:
    req = SimulateRequest(
        unit_cost=D("10"), referral_fee=D("2"), prices=[D("10"), D("20"), D("15")]
    )
    out = calc.simulate(req)
    assert out.break_even_price == D("12.00")
    assert [r.net_profit for r in out.results] == [D("-2.00"), D("8.00"), D("3.00")]
    assert out.best_profit_price == D("20.00")
    assert out.best_margin_price == D("20.00")


def test_simulate_range() -> None:
    req = SimulateRequest.model_validate(
        {
            "unit_cost": "10",
            "price_range": {"min_price": "10", "max_price": "11", "step": "0.25"},
        }
    )
    out = calc.simulate(req)
    assert [r.selling_price for r in out.results] == [
        D("10.00"),
        D("10.25"),
        D("10.50"),
        D("10.75"),
        D("11.00"),
    ]


def test_simulate_requires_exactly_one_source() -> None:
    with pytest.raises(ValidationError):
        SimulateRequest()
    with pytest.raises(ValidationError):
        SimulateRequest.model_validate(
            {"prices": ["1"], "price_range": {"min_price": "1", "max_price": "2", "step": "1"}}
        )


def test_simulate_range_validation() -> None:
    for pr in (
        {"min_price": "5", "max_price": "1", "step": "1"},
        {"min_price": "1", "max_price": "2", "step": "0"},
        {"min_price": "1", "max_price": "1000", "step": "0.01"},
    ):
        with pytest.raises(ValidationError):
            SimulateRequest.model_validate({"price_range": pr})


# ---- endpoints ----


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user, None)


def test_calculate_endpoint(client: TestClient) -> None:
    res = client.post("/api/v1/calculator/calculate", json=FULL)
    assert res.status_code == 200
    body = res.json()
    assert D(body["net_profit"]) == D("10.00")
    assert D(body["margin_pct"]) == D("33.33")


def test_calculate_endpoint_zero_price(client: TestClient) -> None:
    res = client.post("/api/v1/calculator/calculate", json={"selling_price": "0"})
    assert res.status_code == 200
    assert res.json()["margin_pct"] is None


def test_calculate_endpoint_negative_422(client: TestClient) -> None:
    res = client.post("/api/v1/calculator/calculate", json={**FULL, "unit_cost": "-1"})
    assert res.status_code == 422


def test_simulate_endpoint(client: TestClient) -> None:
    res = client.post(
        "/api/v1/calculator/simulate",
        json={"unit_cost": "10", "prices": ["15", "20"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["results"]) == 2
    assert D(body["break_even_price"]) == D("10.00")


def test_simulate_endpoint_bad_422(client: TestClient) -> None:
    res = client.post("/api/v1/calculator/simulate", json={"unit_cost": "10"})
    assert res.status_code == 422


def test_calculator_requires_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as c:
        res = c.post("/api/v1/calculator/calculate", json=FULL)
    assert res.status_code == 401
