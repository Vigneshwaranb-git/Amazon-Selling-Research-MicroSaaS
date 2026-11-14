"""Tests for tracking list CRUD, ASIN add/remove and per-user authorization."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.main import app
from app.models.user import User

BASE = "/api/v1/tracking-lists"
ASIN = "B012345678"


class Ctx:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self._users: dict[int, User] = {}

    def as_user(self, user_id: int) -> TestClient:
        user = self._users[user_id]
        app.dependency_overrides[get_current_user] = lambda: user
        return self.client


@pytest.fixture
def ctx(client: TestClient, db_session: Session) -> Iterator[Ctx]:
    c = Ctx(client)
    for uid, email in ((1, "a@example.com"), (2, "b@example.com")):
        u = User(id=uid, email=email)
        db_session.add(u)
        c._users[uid] = u
    db_session.commit()
    c.as_user(1)
    yield c
    app.dependency_overrides.pop(get_current_user, None)


def test_requires_auth(client: TestClient) -> None:
    assert client.get(BASE).status_code == 401


def test_crud(ctx: Ctx) -> None:
    c = ctx.client
    r = c.post(BASE, json={"name": "  Winners "})
    assert r.status_code == 201
    lid = r.json()["id"]
    assert r.json()["name"] == "Winners"

    assert c.post(BASE, json={"name": "winners"}).status_code == 409
    assert c.post(BASE, json={"name": "   "}).status_code == 422
    assert c.post(BASE, json={"name": "x" * 101}).status_code == 422

    assert [x["name"] for x in c.get(BASE).json()] == ["Winners"]

    r = c.put(f"{BASE}/{lid}", json={"name": "Renamed"})
    assert r.status_code == 200 and r.json()["name"] == "Renamed"
    assert c.put(f"{BASE}/9999", json={"name": "z"}).status_code == 404

    assert c.delete(f"{BASE}/{lid}").status_code == 204
    assert c.delete(f"{BASE}/{lid}").status_code == 404
    assert c.get(BASE).json() == []


def test_add_remove_product(ctx: Ctx) -> None:
    c = ctx.client
    lid = c.post(BASE, json={"name": "L"}).json()["id"]

    r = c.post(f"{BASE}/{lid}/products", json={"asin": ASIN})
    assert r.status_code == 201
    assert r.json()["product_count"] == 1
    assert r.json()["products"][0]["asin"] == ASIN

    assert c.post(f"{BASE}/{lid}/products", json={"asin": ASIN}).status_code == 409
    assert c.get(BASE).json()[0]["product_count"] == 1
    assert c.get(f"{BASE}/{lid}").json()["products"][0]["asin"] == ASIN

    assert c.delete(f"{BASE}/{lid}/products/{ASIN}").status_code == 204
    assert c.delete(f"{BASE}/{lid}/products/{ASIN}").status_code == 404
    assert c.get(f"{BASE}/{lid}").json()["product_count"] == 0


@pytest.mark.parametrize("asin", ["b012345678", "SHORT", "B0123456789", "B01234567-", ""])
def test_add_invalid_asin(ctx: Ctx, asin: str) -> None:
    lid = ctx.client.post(BASE, json={"name": "L"}).json()["id"]
    assert ctx.client.post(f"{BASE}/{lid}/products", json={"asin": asin}).status_code == 422
    assert ctx.client.delete(f"{BASE}/{lid}/products/{asin or 'x'}").status_code in (404, 422)
    assert ctx.client.delete(f"{BASE}/{lid}/products/bad").status_code == 422


def test_other_users_lists_are_404(ctx: Ctx) -> None:
    lid = ctx.client.post(BASE, json={"name": "Private"}).json()["id"]
    ctx.client.post(f"{BASE}/{lid}/products", json={"asin": ASIN})

    other = ctx.as_user(2)
    assert other.get(BASE).json() == []
    assert other.get(f"{BASE}/{lid}").status_code == 404
    assert other.put(f"{BASE}/{lid}", json={"name": "hax"}).status_code == 404
    assert other.delete(f"{BASE}/{lid}").status_code == 404
    assert other.post(f"{BASE}/{lid}/products", json={"asin": "B000000001"}).status_code == 404
    assert other.delete(f"{BASE}/{lid}/products/{ASIN}").status_code == 404

    # same name is allowed for a different user
    assert other.post(BASE, json={"name": "Private"}).status_code == 201

    owner = ctx.as_user(1)
    assert owner.get(f"{BASE}/{lid}").json()["name"] == "Private"
    assert owner.get(f"{BASE}/{lid}").json()["product_count"] == 1
