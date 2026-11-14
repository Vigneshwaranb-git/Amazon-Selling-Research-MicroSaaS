"""Gap-filling tests: billing service branches, auth edge cases, cross-user authorization."""

import asyncio
import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import jwt as jwt_utils
from app.config import settings
from app.exceptions import AppException, UnauthorizedError, register_exception_handlers
from app.models.refresh_token import RefreshToken
from app.models.subscription import Subscription
from app.models.user import User
from app.services import auth_service, billing_service

AUTH = settings.API_V1_PREFIX + "/auth"
API = settings.API_V1_PREFIX
PW = "S3curePass!"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def _jwt(claims: dict[str, Any], key: str | None = None) -> str:
    return str(pyjwt.encode(claims, key or settings.SECRET_KEY, algorithm=settings.ALGORITHM))


def _future(**kw: float) -> datetime:
    return datetime.now(UTC) + timedelta(**kw)


# ---------------------------------------------------------------- billing svc
def test_product_id_unconfigured_business(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DODO_PRODUCT_ID_BUSINESS", "")
    with pytest.raises(AppException) as ei:
        billing_service._product_id("business")
    assert ei.value.status_code == 503
    monkeypatch.setattr(settings, "DODO_PRODUCT_ID_BUSINESS", "pb")
    assert billing_service._product_id("business") == "pb"


class _Client:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.kw: dict[str, Any] = {}

    async def create_checkout(self, **kw: Any) -> dict[str, Any]:
        self.kw = kw
        return self.data


def test_create_checkout_url_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DODO_PRODUCT_ID_PRO", "prod_pro")
    user = User(id=7, email="u@x.co", full_name="U")
    c = _Client({"checkout_url": "https://alt"})
    assert run(billing_service.create_checkout(c, user, "pro")) == "https://alt"
    assert c.kw["metadata"] == {"user_id": "7", "plan": "pro"}
    assert c.kw["return_url"].endswith("/settings/billing")
    for bad in ({}, {"checkout_url": ""}, {"checkout_url": 5}, {"checkout_url": None}):
        with pytest.raises(AppException) as ei:
            run(billing_service.create_checkout(_Client(bad), user, "pro"))
        assert ei.value.status_code == 502


def test_parse_dt_and_dict_helpers() -> None:
    assert billing_service._parse_dt(None) is None
    assert billing_service._parse_dt(123) is None
    assert billing_service._parse_dt("not a date") is None
    naive = billing_service._parse_dt("2030-01-01T00:00:00")
    assert naive is not None and naive.tzinfo is UTC
    assert billing_service._parse_dt("2030-01-01T00:00:00Z") == datetime(2030, 1, 1, tzinfo=UTC)
    assert billing_service._dict([1]) == {}
    assert billing_service._dict({"a": 1}) == {"a": 1}


@pytest.fixture()
def bdb(db_session: Session) -> Session:
    db_session.add_all([User(id=1, email="a@x.co"), User(id=2, email="b@x.co")])
    db_session.commit()
    return db_session


def _ev(db: Session, payload: Any) -> bool:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return bool(billing_service.process_webhook(db, body))


def test_process_webhook_malformed_inputs(bdb: Session) -> None:
    assert _ev(bdb, b"not json") is False
    assert _ev(bdb, [1, 2]) is False
    assert _ev(bdb, {"type": "subscription.active"}) is False
    assert _ev(bdb, {"type": "subscription.active", "data": {}}) is False
    assert _ev(bdb, {"type": "subscription.active", "data": "str"}) is False
    assert _ev(bdb, {"type": None, "data": {"a": 1}}) is False
    for meta in ({}, {"user_id": "abc"}, {"user_id": None}, {"user_id": "999"}):
        assert _ev(bdb, {"type": "subscription.active", "data": {"metadata": meta}}) is False
    assert bdb.query(Subscription).count() == 0


@pytest.mark.parametrize(
    ("event", "status"),
    [
        ("subscription.renewed", "active"),
        ("subscription.on_hold", "past_due"),
        ("subscription.past_due", "past_due"),
        ("subscription.paused", "paused"),
        ("subscription.unpaused", "active"),
        ("subscription.cancelled", "cancelled"),
        ("subscription.expired", "expired"),
    ],
)
def test_process_webhook_status_mapping(bdb: Session, event: str, status: str) -> None:
    data = {"subscription_id": "s1", "metadata": {"user_id": "1", "plan": "business"}}
    assert _ev(bdb, {"type": event, "data": data}) is True
    sub = billing_service.get_subscription(bdb, 1)
    assert sub is not None and sub.status == status and sub.plan == "business"


def test_process_webhook_lookup_by_sub_id_and_plan_handling(bdb: Session) -> None:
    base = {"subscription_id": "s1", "metadata": {"user_id": "1", "plan": "pro"}}
    _ev(bdb, {"type": "subscription.active", "data": base})
    assert _ev(bdb, {"type": "subscription.on_hold", "data": {"subscription_id": "s1"}}) is True
    assert bdb.query(Subscription).count() == 1
    sub = billing_service.get_subscription(bdb, 1)
    assert sub is not None and (sub.status, sub.plan) == ("past_due", "pro")
    _ev(
        bdb,
        {
            "type": "subscription.active",
            "data": {"subscription_id": "s1", "metadata": {"plan": "enterprise"}},
        },
    )
    bdb.refresh(sub)
    assert sub.plan == "pro"


def test_process_webhook_reuses_existing_user_subscription(bdb: Session) -> None:
    _ev(bdb, {"type": "subscription.active", "data": {"metadata": {"user_id": "1"}, "x": 1}})
    _ev(
        bdb,
        {
            "type": "subscription.renewed",
            "data": {"subscription_id": "new", "metadata": {"user_id": "1", "plan": "pro"}},
        },
    )
    assert bdb.query(Subscription).count() == 1
    sub = billing_service.get_subscription(bdb, 1)
    assert sub is not None and sub.dodo_subscription_id == "new"


def test_process_webhook_period_end_and_customer(bdb: Session) -> None:
    data = {
        "subscription_id": "s9",
        "customer": {"customer_id": "cus_9"},
        "metadata": {"user_id": "2", "plan": "pro"},
        "next_billing_date": "2031-05-05T10:00:00+00:00",
    }
    _ev(bdb, {"type": "subscription.active", "data": data})
    sub = billing_service.get_subscription(bdb, 2)
    assert sub is not None and sub.dodo_customer_id == "cus_9"
    assert sub.current_period_end is not None and sub.current_period_end.year == 2031
    data2 = {"subscription_id": "s9", "next_billing_date": "garbage", "customer": "x"}
    _ev(bdb, {"type": "subscription.renewed", "data": data2})
    bdb.refresh(sub)
    assert sub.current_period_end is not None and sub.current_period_end.year == 2031


def test_get_subscription_returns_latest(bdb: Session) -> None:
    assert billing_service.get_subscription(bdb, 1) is None
    bdb.add(Subscription(user_id=1, plan="pro", status="expired"))
    bdb.commit()
    bdb.add(Subscription(user_id=1, plan="business", status="active"))
    bdb.commit()
    latest = billing_service.get_subscription(bdb, 1)
    assert latest is not None and latest.plan == "business"
    assert billing_service.get_subscription(bdb, 2) is None


def test_webhook_sub_id_stays_bound_to_original_user(bdb: Session) -> None:
    _ev(
        bdb,
        {
            "type": "subscription.active",
            "data": {"subscription_id": "s1", "metadata": {"user_id": "1", "plan": "pro"}},
        },
    )
    _ev(
        bdb,
        {
            "type": "subscription.cancelled",
            "data": {"subscription_id": "s1", "metadata": {"user_id": "2"}},
        },
    )
    assert billing_service.get_subscription(bdb, 2) is None
    sub = billing_service.get_subscription(bdb, 1)
    assert sub is not None and sub.status == "cancelled"


# ------------------------------------------------------------------- auth edge
def _reg(client: TestClient, email: str = "s@example.com") -> dict[str, Any]:
    r = client.post(f"{AUTH}/register", json={"email": email, "password": PW, "full_name": "S"})
    assert r.status_code == 201
    return _login(client, email)


def _login(client: TestClient, email: str = "s@example.com") -> dict[str, Any]:
    r = client.post(f"{AUTH}/login", data={"username": email, "password": PW})
    return dict(r.json())


def _refresh(client: TestClient, token: str) -> Any:
    return client.post(f"{AUTH}/refresh", json={"refresh_token": token})


def test_reuse_revokes_all_sessions_across_devices(client: TestClient, db_session: Session) -> None:
    device1 = _reg(client)
    device2 = _login(client)
    rotated = _refresh(client, device1["refresh_token"]).json()
    assert _refresh(client, device1["refresh_token"]).status_code == 401  # replay
    assert _refresh(client, device2["refresh_token"]).status_code == 401  # untouched device dead
    assert _refresh(client, rotated["refresh_token"]).status_code == 401
    assert db_session.query(RefreshToken).filter_by(revoked=False).count() == 0


def test_reuse_does_not_affect_other_users(client: TestClient) -> None:
    a = _reg(client, "a@example.com")
    b = _reg(client, "b@example.com")
    _refresh(client, a["refresh_token"])
    assert _refresh(client, a["refresh_token"]).status_code == 401
    assert _refresh(client, b["refresh_token"]).status_code == 200


def test_refresh_validly_signed_but_unknown_token(client: TestClient) -> None:
    _reg(client)
    assert _refresh(client, jwt_utils.create_refresh_token(1)).status_code == 401


def test_refresh_row_user_mismatch_rejected(client: TestClient, db_session: Session) -> None:
    t = _reg(client)
    _reg(client, "other@example.com")
    row = db_session.query(RefreshToken).filter_by(user_id=1).one()
    row.user_id = 2
    db_session.commit()
    assert _refresh(client, t["refresh_token"]).status_code == 401


def test_refresh_expired_row_rejected(client: TestClient, db_session: Session) -> None:
    t = _reg(client)
    row = db_session.query(RefreshToken).one()
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    resp = _refresh(client, t["refresh_token"])
    assert resp.status_code == 401 and "expired" in resp.json()["error"]["message"].lower()


def test_refresh_expired_jwt_and_wrong_key(client: TestClient) -> None:
    _reg(client)
    expired = _jwt({"sub": "1", "type": "refresh", "exp": datetime.now(UTC) - timedelta(minutes=1)})
    assert _refresh(client, expired).status_code == 401
    forged = _jwt({"sub": "1", "type": "refresh", "exp": _future(days=1)}, key="wrong-key")
    assert _refresh(client, forged).status_code == 401


def test_refresh_for_deactivated_user_rejected(client: TestClient, db_session: Session) -> None:
    t = _reg(client)
    db_session.query(User).one().is_active = False
    db_session.commit()
    assert _refresh(client, t["refresh_token"]).status_code == 401


def test_logout_with_garbage_token_is_ok(client: TestClient) -> None:
    assert client.post(f"{AUTH}/logout", json={"refresh_token": "junk"}).status_code == 200


def test_me_rejects_bad_bearers(client: TestClient) -> None:
    t = _reg(client)
    me = f"{AUTH}/me"

    def get(tok: str) -> int:
        return client.get(me, headers={"Authorization": f"Bearer {tok}"}).status_code

    assert get(t["refresh_token"]) == 401  # wrong token type
    assert get(_jwt({"sub": "1", "type": "access", "exp": _future(minutes=-1)})) == 401
    assert get(jwt_utils.create_access_token(4242)) == 401  # user does not exist
    assert get(_jwt({"sub": "abc", "type": "access", "exp": _future(minutes=5)})) == 401
    assert client.get(me).status_code == 401
    assert get(t["access_token"]) == 200


def test_decode_token_rejects_alg_none() -> None:
    def b64(d: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    forged = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': '1', 'type': 'access'})}."
    assert jwt_utils.decode_token(forged, "access") is None


def test_reset_rejects_expired_and_wrong_fingerprint(
    client: TestClient, db_session: Session
) -> None:
    _reg(client)
    user = db_session.query(User).one()
    expired = _jwt(
        {
            "sub": str(user.id),
            "type": "reset",
            "fp": jwt_utils.password_fingerprint(user.hashed_password),
            "exp": _future(minutes=-1),
        }
    )
    url = f"{AUTH}/reset-password"
    resp = client.post(url, json={"token": expired, "new_password": "NewPass123"})
    assert resp.status_code == 401
    bad_fp = jwt_utils.create_reset_token(user.id, "some-other-hash")
    assert client.post(url, json={"token": bad_fp, "new_password": "NewPass123"}).status_code == 401
    assert _login(client).get("access_token")  # password unchanged


def test_reset_two_tokens_only_first_wins(client: TestClient, db_session: Session) -> None:
    _reg(client)
    user = db_session.query(User).one()
    t1 = jwt_utils.create_reset_token(user.id, user.hashed_password)
    t2 = jwt_utils.create_reset_token(user.id, user.hashed_password)
    url = f"{AUTH}/reset-password"
    assert client.post(url, json={"token": t1, "new_password": "NewPass123"}).status_code == 200
    assert client.post(url, json={"token": t2, "new_password": "Other12345"}).status_code == 401


def test_reset_for_inactive_or_missing_user(client: TestClient, db_session: Session) -> None:
    _reg(client)
    user = db_session.query(User).one()
    tok = jwt_utils.create_reset_token(user.id, user.hashed_password)
    user.is_active = False
    db_session.commit()
    url = f"{AUTH}/reset-password"
    assert client.post(url, json={"token": tok, "new_password": "NewPass123"}).status_code == 401
    ghost = jwt_utils.create_reset_token(999, "h")
    assert client.post(url, json={"token": ghost, "new_password": "NewPass123"}).status_code == 401


def test_reset_short_password_422(client: TestClient, db_session: Session) -> None:
    _reg(client)
    user = db_session.query(User).one()
    tok = jwt_utils.create_reset_token(user.id, user.hashed_password)
    r = client.post(f"{AUTH}/reset-password", json={"token": tok, "new_password": "x"})
    assert r.status_code == 422


def test_forgot_password_logging(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    u = User(email="i@x.co", hashed_password="h", is_active=False)
    db_session.add(u)
    db_session.commit()
    with caplog.at_level("DEBUG"):
        auth_service.send_password_reset(db_session, "i@x.co")
        auth_service.send_password_reset(db_session, "nobody@x.co")
    assert "reset" not in caplog.text.lower()
    u.is_active = True
    db_session.commit()
    monkeypatch.setattr(settings, "DEBUG", False)
    with caplog.at_level("DEBUG"):
        auth_service.send_password_reset(db_session, "i@x.co")
    assert "reset-password?token" not in caplog.text
    monkeypatch.setattr(settings, "DEBUG", True)
    with caplog.at_level("DEBUG"):
        auth_service.send_password_reset(db_session, "i@x.co")
    assert "reset-password?token" in caplog.text


def test_google_user_paths(db_session: Session) -> None:
    db_session.add(User(email="g@x.co", is_active=False))
    db_session.commit()
    with pytest.raises(UnauthorizedError):
        auth_service.get_or_create_google_user(db_session, "g@x.co", "G")
    u = auth_service.get_or_create_google_user(db_session, "new@x.co", "New")
    assert u.is_verified and u.oauth_provider == "google" and u.hashed_password is None


def test_google_only_account_cannot_password_login(client: TestClient, db_session: Session) -> None:
    auth_service.get_or_create_google_user(db_session, "g2@x.co", "G")
    r = client.post(f"{AUTH}/login", data={"username": "g2@x.co", "password": "anything123"})
    assert r.status_code == 401


def test_revoke_all_only_touches_own_tokens(db_session: Session) -> None:
    for uid in (1, 2):
        db_session.add(User(id=uid, email=f"{uid}@x.co", hashed_password="h"))
    db_session.commit()
    u1, u2 = db_session.get(User, 1), db_session.get(User, 2)
    assert u1 is not None and u2 is not None
    auth_service.issue_tokens(db_session, u1)
    auth_service.issue_tokens(db_session, u2)
    auth_service.revoke_all_user_tokens(db_session, 1)
    assert db_session.query(RefreshToken).filter_by(user_id=1, revoked=False).count() == 0
    assert db_session.query(RefreshToken).filter_by(user_id=2, revoked=False).count() == 1


# ------------------------------------------------------------------- app-level
def test_unhandled_exception_returns_generic_500() -> None:
    small = FastAPI()
    register_exception_handlers(small)

    @small.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret detail")

    with TestClient(small, raise_server_exceptions=False) as c:
        r = c.get("/boom")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret detail" not in r.text


# ------------------------------------------------------------------- authz
SC = {
    "name": "W",
    "asin": "B012345678",
    "unit_cost": "10",
    "shipping_cost": "1",
    "referral_fee": "3",
    "fba_fulfillment_fee": "4",
    "storage_fee": "0.5",
    "vat_tax": "0.5",
    "selling_price": "30",
    "target_roi": "50",
    "target_margin": "20",
}


def _h(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_scenarios_and_lists_isolation_with_real_jwt(client: TestClient) -> None:
    ha = _h(_reg(client, "alice@example.com"))
    hb = _h(_reg(client, "bob@example.com"))
    sid = client.post(f"{API}/scenarios", json=SC, headers=ha).json()["id"]
    lid = client.post(f"{API}/tracking-lists", json={"name": "L"}, headers=ha).json()["id"]
    client.post(f"{API}/tracking-lists/{lid}/products", json={"asin": "B012345678"}, headers=ha)

    assert client.get(f"{API}/scenarios", headers=hb).json() == []
    assert client.get(f"{API}/scenarios/{sid}", headers=hb).status_code == 404
    assert client.put(f"{API}/scenarios/{sid}", json=SC, headers=hb).status_code == 404
    assert client.delete(f"{API}/scenarios/{sid}", headers=hb).status_code == 404
    assert client.get(f"{API}/tracking-lists", headers=hb).json() == []
    assert client.get(f"{API}/tracking-lists/{lid}", headers=hb).status_code == 404
    put = client.put(f"{API}/tracking-lists/{lid}", json={"name": "x"}, headers=hb)
    assert put.status_code == 404
    assert client.delete(f"{API}/tracking-lists/{lid}", headers=hb).status_code == 404
    rm = client.delete(f"{API}/tracking-lists/{lid}/products/B012345678", headers=hb)
    assert rm.status_code == 404
    add = client.post(
        f"{API}/tracking-lists/{lid}/products", json={"asin": "B000000001"}, headers=hb
    )
    assert add.status_code == 404

    assert client.get(f"{API}/scenarios/{sid}", headers=ha).json()["name"] == "W"
    detail = client.get(f"{API}/tracking-lists/{lid}", headers=ha).json()
    assert detail["name"] == "L" and detail["product_count"] == 1


def test_protected_routes_require_auth(client: TestClient) -> None:
    for method, path in (
        ("get", "/scenarios"),
        ("get", "/tracking-lists"),
        ("get", "/billing/subscription"),
        ("post", "/billing/checkout"),
    ):
        assert getattr(client, method)(f"{API}{path}").status_code == 401


def test_subscription_endpoint_isolated_per_user(client: TestClient, db_session: Session) -> None:
    ha = _h(_reg(client, "alice@example.com"))
    hb = _h(_reg(client, "bob@example.com"))
    db_session.add(Subscription(user_id=1, plan="pro", status="active"))
    db_session.commit()
    assert client.get(f"{API}/billing/subscription", headers=ha).json()["plan"] == "pro"
    assert client.get(f"{API}/billing/subscription", headers=hb).json()["plan"] == "free"


def test_updated_and_plan_changed_use_payload_status(bdb: Session) -> None:
    base = {"subscription_id": "s1", "metadata": {"user_id": "1", "plan": "pro"}}
    _ev(bdb, {"type": "subscription.active", "data": base})
    changed = {"subscription_id": "s1", "status": "on_hold", "metadata": {"plan": "business"}}
    assert _ev(bdb, {"type": "subscription.plan_changed", "data": changed}) is True
    sub = billing_service.get_subscription(bdb, 1)
    assert sub is not None and (sub.status, sub.plan) == ("past_due", "business")
    unknown = {"subscription_id": "s1", "status": "weird"}
    assert _ev(bdb, {"type": "subscription.updated", "data": unknown}) is False
    assert _ev(bdb, {"type": "subscription.failed", "data": base}) is False
