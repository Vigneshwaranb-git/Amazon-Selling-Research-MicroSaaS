"""Tests for GET /analytics/overview."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.bsr_snapshot import BsrSnapshot
from app.models.cost_model import CostModel
from app.models.product import Product
from app.models.tracking_list import TrackedProduct, TrackingList
from app.models.user import User
from app.services import auth_service

URL = "/api/v1/analytics/overview"
D0 = datetime(2025, 1, 1, 12, tzinfo=UTC)


def _user(db: Session, email: str) -> tuple[User, dict[str, str]]:
    u = User(email=email, hashed_password="x")
    db.add(u)
    db.commit()
    t = auth_service.issue_tokens(db, u)
    return u, {"Authorization": f"Bearer {t.access_token}"}


def _product(db: Session, asin: str, trend: int | None, series: list[int]) -> Product:
    p = Product(asin=asin, title=f"Title {asin}", trend_score=trend)
    db.add(p)
    db.commit()
    for i, bsr in enumerate(series):
        db.add(BsrSnapshot(product_id=p.id, bsr=bsr, captured_at=D0 + timedelta(days=i)))
    db.commit()
    return p


def _track(db: Session, user: User, products: list[Product]) -> None:
    tl = TrackingList(user_id=user.id, name="L")
    db.add(tl)
    db.commit()
    for p in products:
        db.add(TrackedProduct(tracking_list_id=tl.id, product_id=p.id))
    db.commit()


def test_requires_auth(client: TestClient) -> None:
    assert client.get(URL).status_code == 401


def test_empty_state(client: TestClient, db_session: Session) -> None:
    _, h = _user(db_session, "e@example.com")
    r = client.get(URL, headers=h)
    assert r.status_code == 200
    assert r.json() == {
        "totals": {"tracking_lists": 0, "tracked_products": 0, "scenarios": 0},
        "avg_scenario_margin": None,
        "trend_distribution": {"rising": 0, "stable": 0, "declining": 0},
        "bsr_series": [],
        "top_movers": [],
    }


def test_days_validation(client: TestClient, db_session: Session) -> None:
    _, h = _user(db_session, "d@example.com")
    assert client.get(URL, params={"days": 6}, headers=h).status_code == 422
    assert client.get(URL, params={"days": 366}, headers=h).status_code == 422
    assert client.get(URL, params={"days": 7}, headers=h).status_code == 200


def test_overview_values_and_isolation(client: TestClient, db_session: Session) -> None:
    a, ha = _user(db_session, "a@example.com")
    b, hb = _user(db_session, "b@example.com")
    up = _product(db_session, "B000000001", 80, [100, 80, 50])  # improves 50%
    down = _product(db_session, "B000000002", 20, [100, 120, 150])  # worsens 50%
    flat = _product(db_session, "B000000003", 50, [10, 10, 10])
    none = _product(db_session, "B000000004", None, [])
    other = _product(db_session, "B000000005", 90, [500, 500, 500])
    _track(db_session, a, [up, down, flat, none])
    _track(db_session, b, [other])
    db_session.add_all(
        [
            CostModel(user_id=a.id, name="s1", selling_price=10, margin=20),
            CostModel(user_id=a.id, name="s2", selling_price=10, margin=30),
            CostModel(user_id=b.id, name="s3", selling_price=10, margin=99),
        ]
    )
    db_session.commit()

    body = client.get(URL, headers=ha).json()
    assert body["totals"] == {"tracking_lists": 1, "tracked_products": 4, "scenarios": 2}
    assert body["avg_scenario_margin"] == 25.0
    assert body["trend_distribution"] == {"rising": 1, "stable": 1, "declining": 1}
    assert [p["date"] for p in body["bsr_series"]] == ["2025-01-01", "2025-01-02", "2025-01-03"]
    assert [p["avg_bsr"] for p in body["bsr_series"]] == [70.0, 70.0, 70.0]
    movers = body["top_movers"]
    assert [m["asin"] for m in movers] == ["B000000001", "B000000002"]
    assert movers[0]["bsr_change_pct"] == -50.0 and movers[1]["bsr_change_pct"] == 50.0

    other_body = client.get(URL, headers=hb).json()
    assert other_body["totals"]["tracked_products"] == 1
    assert other_body["avg_scenario_margin"] == 99.0
    assert other_body["trend_distribution"]["rising"] == 1
    assert other_body["top_movers"] == []
    assert [p["avg_bsr"] for p in other_body["bsr_series"]] == [500.0] * 3


def test_window_takes_latest_n_dates(client: TestClient, db_session: Session) -> None:
    a, ha = _user(db_session, "w@example.com")
    p = _product(db_session, "B000000009", 50, list(range(1000, 1010)))  # 10 daily points
    _track(db_session, a, [p])
    body = client.get(URL, params={"days": 7}, headers=ha).json()
    assert len(body["bsr_series"]) == 7
    assert body["bsr_series"][0]["date"] == "2025-01-04"
    assert body["bsr_series"][-1]["date"] == "2025-01-10"
    # mover uses first/last inside the window: 1003 -> 1009
    assert body["top_movers"][0]["bsr_change_pct"] == round((1009 - 1003) * 100 / 1003, 2)
