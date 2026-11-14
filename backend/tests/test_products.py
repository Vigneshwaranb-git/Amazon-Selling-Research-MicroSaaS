"""Tests for product endpoints, trend scorer and snapshot job."""

import asyncio
from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.main import app
from app.models.bsr_snapshot import BsrSnapshot
from app.models.product import Product
from app.models.user import User
from app.services.providers.mock import MockProductDataProvider
from app.services.snapshot_job import run_snapshot_job
from app.services.trend_scorer import (
    estimate_margin_pct,
    saturation_score,
    trend_score,
)

BASE = "/api/v1/products"


@pytest.fixture
def user(db_session: Session) -> Iterator[User]:
    u = User(id=1, email="a@example.com")
    db_session.add(u)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: u
    yield u
    app.dependency_overrides.pop(get_current_user, None)


def test_requires_auth(client: TestClient) -> None:
    assert client.get(BASE).status_code == 401


def test_list_seeds_and_paginates(client: TestClient, user: User) -> None:
    r = client.get(BASE, params={"page_size": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 30
    assert len(body["items"]) == 5
    assert body["page"] == 1
    bsrs = [i["bsr"] for i in body["items"]]
    assert bsrs == sorted(bsrs)
    page2 = client.get(BASE, params={"page_size": 5, "page": 2}).json()
    assert {i["asin"] for i in page2["items"]}.isdisjoint({i["asin"] for i in body["items"]})
    assert client.get(BASE, params={"page_size": 101}).status_code == 422


def test_filters(client: TestClient, user: User) -> None:
    all_items = client.get(BASE, params={"page_size": 100}).json()["items"]
    cat = all_items[0]["category"]
    r = client.get(BASE, params={"category": cat, "page_size": 100}).json()
    assert r["items"] and all(i["category"] == cat for i in r["items"])

    r = client.get(BASE, params={"max_saturation": 50, "page_size": 100}).json()
    assert all(i["saturation_score"] <= 50 for i in r["items"])

    r = client.get(BASE, params={"min_trend": 50, "page_size": 100}).json()
    assert all(i["trend_score"] >= 50 for i in r["items"])

    r = client.get(BASE, params={"min_margin": 40, "page_size": 100}).json()
    assert r["total"] < len(all_items)
    assert all(i["estimated_margin_pct"] >= 40 for i in r["items"])

    r = client.get(BASE, params={"sort_by": "price", "sort_dir": "desc", "page_size": 100}).json()
    prices = [Decimal(i["price"]) for i in r["items"]]
    assert prices == sorted(prices, reverse=True)

    assert client.get(BASE, params={"sort_by": "nope"}).status_code == 422
    assert client.get(BASE, params={"max_saturation": 101}).status_code == 422


def test_detail_and_history(client: TestClient, user: User, db_session: Session) -> None:
    r = client.get(f"{BASE}/B012345678")
    assert r.status_code == 200
    body = r.json()
    assert body["asin"] == "B012345678"
    assert body["snapshot_count"] == 31
    assert 0 <= body["trend_score"] <= 100

    h = client.get(f"{BASE}/B012345678/history", params={"limit": 10}).json()
    assert h["asin"] == "B012345678"
    assert len(h["snapshots"]) == 10
    times = [s["captured_at"] for s in h["snapshots"]]
    assert times == sorted(times)


@pytest.mark.parametrize("asin", ["b012345678", "B01234567", "B0123456789", "B01234567!"])
def test_invalid_asin_rejected(client: TestClient, user: User, asin: str) -> None:
    assert client.get(f"{BASE}/{asin}").status_code in (404, 422)
    if len(asin) in (9, 11) or asin.islower() or "!" in asin:
        assert client.get(f"{BASE}/{asin}").status_code == 422


def test_unknown_asin_404(client: TestClient, user: User) -> None:
    class _NoneProvider(MockProductDataProvider):
        async def get_product(self, asin: str) -> None:  # type: ignore[override]
            return None

    from app.services.providers import get_product_data_provider

    app.dependency_overrides[get_product_data_provider] = lambda: _NoneProvider()
    try:
        r = client.get(f"{BASE}/B0ZZZZZZZZ")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.pop(get_product_data_provider, None)


def test_export_csv(client: TestClient, user: User, db_session: Session) -> None:
    client.get(BASE)  # seed
    p = db_session.execute(select(Product).limit(1)).scalar_one()
    p.title = "=HYPERLINK(evil)"
    db_session.commit()
    r = client.get(f"{BASE}/export", params={"max_saturation": 100})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("asin,title,category")
    assert len(lines) == 31
    assert "'=HYPERLINK(evil)" in r.text


def test_snapshot_job_is_append_only(client: TestClient, user: User, db_session: Session) -> None:
    client.get(f"{BASE}/B012345678")
    before = db_session.execute(select(func.count(BsrSnapshot.id))).scalar_one()
    old = db_session.execute(select(BsrSnapshot).order_by(BsrSnapshot.id).limit(1)).scalar_one()
    old_bsr, old_id = old.bsr, old.id
    refreshed = asyncio.run(run_snapshot_job(db_session, MockProductDataProvider()))
    assert refreshed == 1
    after = db_session.execute(select(func.count(BsrSnapshot.id))).scalar_one()
    assert after == before + 1
    again = db_session.get(BsrSnapshot, old_id)
    assert again is not None and again.bsr == old_bsr


def test_trend_scorer() -> None:
    assert trend_score([]) == 50
    assert trend_score([1000]) == 50
    assert trend_score([1000, 1000, 1000, 1000]) == 50
    assert trend_score([2000, 1800, 1000, 800]) > 50  # rank improving
    assert trend_score([800, 1000, 1800, 2000]) < 50  # rank worsening
    assert trend_score([100, 100, 100, 100], [10, 10, 40, 40]) > 50
    assert 0 <= trend_score([1, 1_000_000]) <= 100
    low = saturation_score(10, 4.0, 1, 90_000)
    high = saturation_score(9000, 4.8, 30, 100)
    assert 0 <= low < high <= 100
    assert estimate_margin_pct(None) is None
    assert estimate_margin_pct(Decimal("0")) is None
    assert estimate_margin_pct(Decimal("50")) == 48.0
