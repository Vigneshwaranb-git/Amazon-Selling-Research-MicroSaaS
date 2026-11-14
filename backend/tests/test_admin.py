"""Tests for the admin module and ADMIN_EMAILS bootstrap."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models.cost_model import CostModel
from app.models.product import Product
from app.models.refresh_token import RefreshToken
from app.models.subscription import Subscription
from app.models.tracking_list import TrackedProduct, TrackingList
from app.models.user import User
from app.services import auth_service
from tests._auth_helpers import refresh as refresh_call
from tests._auth_helpers import register_verified

BASE = "/api/v1/admin"
PASSWORD = "password123"


def _mk(db: Session, email: str, **kw: object) -> User:
    u = User(email=email, hashed_password="x", **kw)  # type: ignore[arg-type]
    db.add(u)
    db.commit()
    return u


def _auth(db: Session, user: User) -> dict[str, str]:
    tokens = auth_service.issue_tokens(db, user)
    return {"Authorization": f"Bearer {tokens.access_token}"}


@pytest.fixture
def admin(db_session: Session) -> User:
    return _mk(db_session, "admin@example.com", is_admin=True)


def test_requires_auth_and_admin(client: TestClient, db_session: Session) -> None:
    assert client.get(f"{BASE}/users").status_code == 401
    normal = _mk(db_session, "u@example.com")
    h = _auth(db_session, normal)
    assert client.get(f"{BASE}/users", headers=h).status_code == 403
    assert client.get(f"{BASE}/stats", headers=h).status_code == 403
    r = client.put(f"{BASE}/users/{normal.id}", json={"is_admin": True}, headers=h)
    assert r.status_code == 403
    db_session.refresh(normal)
    assert normal.is_admin is False


def test_list_users_plan_and_no_password(
    client: TestClient, db_session: Session, admin: User
) -> None:
    pro = _mk(db_session, "pro@example.com")
    _mk(db_session, "free@example.com")
    db_session.add_all(
        [
            Subscription(user_id=pro.id, plan="business", status="canceled"),
            Subscription(user_id=pro.id, plan="pro", status="active"),
        ]
    )
    db_session.commit()
    r = client.get(f"{BASE}/users", headers=_auth(db_session, admin))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3 and body["page"] == 1 and body["page_size"] == 20
    assert "hashed_password" not in r.text
    plans = {i["email"]: i["plan"] for i in body["items"]}
    assert plans == {
        "admin@example.com": "free",
        "pro@example.com": "pro",
        "free@example.com": "free",
    }


def test_pagination_and_limits(client: TestClient, db_session: Session, admin: User) -> None:
    for i in range(5):
        _mk(db_session, f"p{i}@example.com")
    h = _auth(db_session, admin)
    r = client.get(f"{BASE}/users", params={"page": 2, "page_size": 4}, headers=h)
    assert r.json()["total"] == 6 and len(r.json()["items"]) == 2
    assert client.get(f"{BASE}/users", params={"page_size": 101}, headers=h).status_code == 422
    assert client.get(f"{BASE}/users", params={"page": 0}, headers=h).status_code == 422


def test_search_escapes_wildcards(client: TestClient, db_session: Session, admin: User) -> None:
    _mk(db_session, "a_b@example.com")
    _mk(db_session, "axb@example.com", full_name="100% Legit")
    h = _auth(db_session, admin)

    def emails(q: str) -> set[str]:
        r = client.get(f"{BASE}/users", params={"search": q}, headers=h)
        assert r.status_code == 200
        return {i["email"] for i in r.json()["items"]}

    assert emails("a_b") == {"a_b@example.com"}  # '_' is literal, not a wildcard
    assert emails("%") == {"axb@example.com"}  # only the literal percent in the name
    assert emails("ADMIN") == {"admin@example.com"}  # case-insensitive
    assert emails("\\") == set()


def test_update_user_and_404(client: TestClient, db_session: Session, admin: User) -> None:
    other = _mk(db_session, "o@example.com")
    h = _auth(db_session, admin)
    r = client.put(f"{BASE}/users/{other.id}", json={"is_admin": True}, headers=h)
    assert r.status_code == 200
    assert r.json()["is_admin"] is True and r.json()["is_active"] is True
    assert client.put(f"{BASE}/users/9999", json={"is_active": False}, headers=h).status_code == 404


def test_admin_cannot_lock_self_out(client: TestClient, db_session: Session, admin: User) -> None:
    h = _auth(db_session, admin)
    url = f"{BASE}/users/{admin.id}"
    assert client.put(url, json={"is_active": False}, headers=h).status_code == 400
    assert client.put(url, json={"is_admin": False}, headers=h).status_code == 400
    db_session.refresh(admin)
    assert admin.is_active and admin.is_admin
    assert client.put(url, json={"is_active": True}, headers=h).status_code == 200


def test_deactivation_revokes_tokens(client: TestClient, db_session: Session, admin: User) -> None:
    victim = _mk(db_session, "v@example.com")
    tokens = auth_service.issue_tokens(db_session, victim)
    auth_service.issue_tokens(db_session, victim)
    r = client.put(
        f"{BASE}/users/{victim.id}", json={"is_active": False}, headers=_auth(db_session, admin)
    )
    assert r.status_code == 200 and r.json()["is_active"] is False
    rows = db_session.scalars(select(RefreshToken).where(RefreshToken.user_id == victim.id)).all()
    assert rows and all(t.revoked for t in rows)
    assert refresh_call(client, tokens.refresh_token).status_code == 401
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens.access_token}"})
    assert me.status_code == 401


def test_stats(client: TestClient, db_session: Session, admin: User) -> None:
    now = datetime.now(UTC)
    old = _mk(db_session, "old@example.com", is_active=False)
    old.created_at = now - timedelta(days=60)
    mid = _mk(db_session, "mid@example.com")
    mid.created_at = now - timedelta(days=15)
    biz = _mk(db_session, "biz@example.com")
    db_session.add_all(
        [
            Subscription(user_id=mid.id, plan="pro", status="active"),
            Subscription(user_id=biz.id, plan="business", status="past_due"),
            Subscription(user_id=old.id, plan="pro", status="canceled"),
        ]
    )
    prod = Product(asin="B000000001", title="T")
    tl = TrackingList(user_id=admin.id, name="L")
    db_session.add_all([prod, tl])
    db_session.commit()
    db_session.add(TrackedProduct(tracking_list_id=tl.id, product_id=prod.id))
    db_session.add(CostModel(user_id=admin.id, name="s", selling_price=10))
    db_session.commit()

    r = client.get(f"{BASE}/stats", headers=_auth(db_session, admin))
    assert r.status_code == 200
    assert r.json() == {
        "total_users": 4,
        "active_users": 3,
        "new_users_7d": 2,
        "new_users_30d": 3,
        "admins": 1,
        "subscriptions_by_plan": {"free": 2, "pro": 1, "business": 1},
        "active_subscriptions": 2,
        "tracked_products": 1,
        "tracking_lists": 1,
        "scenarios": 1,
    }


def test_admin_emails_bootstrap(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ["boss@example.com", "g@example.com"])
    r = client.post(
        "/api/v1/auth/register", json={"email": "Boss@Example.com", "password": PASSWORD}
    )
    assert r.status_code == 201 and r.json()["is_admin"] is True
    # admin emails still have to verify like anyone else
    assert r.json()["is_verified"] is False
    denied = client.post(
        "/api/v1/auth/login", data={"username": "boss@example.com", "password": PASSWORD}
    )
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
    r = client.post("/api/v1/auth/register", json={"email": "x@example.com", "password": PASSWORD})
    assert r.json()["is_admin"] is False
    assert r.json()["is_verified"] is False
    assert auth_service.get_or_create_google_user(db_session, "G@example.com", None).is_admin

    # login promotes an existing user once their email is listed
    late = register_verified(client, "late@example.com", PASSWORD)
    assert late["is_admin"] is False
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ["late@example.com"])
    r = client.post(
        "/api/v1/auth/login", data={"username": "late@example.com", "password": PASSWORD}
    )
    assert r.status_code == 200
    u = db_session.scalar(select(User).where(User.email == "late@example.com"))
    assert u is not None
    db_session.refresh(u)
    assert u.is_admin is True


def test_admin_emails_parsing() -> None:
    base = {"DATABASE_URL": "sqlite://", "SECRET_KEY": "k" * 32}
    csv = Settings(**base, ADMIN_EMAILS=" A@x.com, b@x.com ,")  # type: ignore[arg-type]
    assert csv.ADMIN_EMAILS == ["a@x.com", "b@x.com"]
    js = Settings(**base, ADMIN_EMAILS='["C@x.com"]')  # type: ignore[arg-type]
    assert js.ADMIN_EMAILS == ["c@x.com"]
    assert Settings(**base).ADMIN_EMAILS == []  # type: ignore[arg-type]
