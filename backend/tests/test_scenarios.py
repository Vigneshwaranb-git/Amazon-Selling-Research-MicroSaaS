"""Tests for saved scenario CRUD and ownership scoping."""

from collections.abc import Iterator
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (register all tables)
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models.base import Base
from app.models.user import User

BASE = "/api/v1/scenarios"
PAYLOAD = {
    "name": "Widget",
    "asin": "B012345678",
    "unit_cost": "10.00",
    "shipping_cost": "2.00",
    "referral_fee": "3.00",
    "fba_fulfillment_fee": "4.00",
    "storage_fee": "0.50",
    "vat_tax": "0.50",
    "selling_price": "30.00",
    "target_roi": "50",
    "target_margin": "20",
}


class Ctx:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.user_id = 1


@pytest.fixture
def ctx() -> Iterator[Ctx]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as s:
        s.add_all(
            [
                User(id=1, email="a@example.com"),
                User(id=2, email="b@example.com"),
            ]
        )
        s.commit()

    def _db() -> Iterator[Session]:
        with factory() as session:
            yield session

    with TestClient(app) as client:
        c = Ctx(client)
        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=c.user_id)
        yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    engine.dispose()


def test_create_computes_and_persists(ctx: Ctx) -> None:
    res = ctx.client.post(BASE, json=PAYLOAD)
    assert res.status_code == 201
    body = res.json()
    assert Decimal(body["net_profit"]) == Decimal("10.00")
    assert Decimal(body["margin"]) == Decimal("33.33")
    assert Decimal(body["roi"]) == Decimal("83.33")
    got = ctx.client.get(f"{BASE}/{body['id']}")
    assert got.status_code == 200
    assert got.json()["name"] == "Widget"


def test_list_only_own(ctx: Ctx) -> None:
    ctx.client.post(BASE, json=PAYLOAD)
    ctx.user_id = 2
    ctx.client.post(BASE, json={**PAYLOAD, "name": "Other"})
    names = [s["name"] for s in ctx.client.get(BASE).json()]
    assert names == ["Other"]
    ctx.user_id = 1
    names = [s["name"] for s in ctx.client.get(BASE).json()]
    assert names == ["Widget"]


def test_other_user_gets_404(ctx: Ctx) -> None:
    sid = ctx.client.post(BASE, json=PAYLOAD).json()["id"]
    ctx.user_id = 2
    assert ctx.client.get(f"{BASE}/{sid}").status_code == 404
    assert ctx.client.put(f"{BASE}/{sid}", json=PAYLOAD).status_code == 404
    assert ctx.client.delete(f"{BASE}/{sid}").status_code == 404
    ctx.user_id = 1
    assert ctx.client.get(f"{BASE}/{sid}").status_code == 200


def test_update_recomputes(ctx: Ctx) -> None:
    sid = ctx.client.post(BASE, json=PAYLOAD).json()["id"]
    res = ctx.client.put(f"{BASE}/{sid}", json={**PAYLOAD, "selling_price": "40.00", "name": "New"})
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "New"
    assert Decimal(body["net_profit"]) == Decimal("20.00")
    assert Decimal(body["margin"]) == Decimal("50.00")


def test_delete(ctx: Ctx) -> None:
    sid = ctx.client.post(BASE, json=PAYLOAD).json()["id"]
    assert ctx.client.delete(f"{BASE}/{sid}").status_code == 204
    assert ctx.client.get(f"{BASE}/{sid}").status_code == 404


def test_zero_price_saved_with_null_margin(ctx: Ctx) -> None:
    res = ctx.client.post(BASE, json={**PAYLOAD, "selling_price": "0"})
    assert res.status_code == 201
    assert res.json()["margin"] is None


@pytest.mark.parametrize(
    "patch",
    [
        {"unit_cost": "-1"},
        {"selling_price": "-5"},
        {"vat_tax": "-0.01"},
        {"name": ""},
        {"asin": "bad"},
        {"target_roi": "-1"},
    ],
)
def test_invalid_payload_422(ctx: Ctx, patch: dict[str, str]) -> None:
    assert ctx.client.post(BASE, json={**PAYLOAD, **patch}).status_code == 422


def test_missing_scenario_404(ctx: Ctx) -> None:
    assert ctx.client.get(f"{BASE}/9999").status_code == 404


def test_requires_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as c:
        assert c.get(BASE).status_code == 401
