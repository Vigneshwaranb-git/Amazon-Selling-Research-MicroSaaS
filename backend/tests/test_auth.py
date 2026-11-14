"""Tests for the auth module."""

from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import jwt as jwt_utils
from app.auth import oauth
from app.config import settings
from app.dependencies import get_current_admin
from app.main import app
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.rate_limit import limiter
from app.services import auth_service
from tests._auth_helpers import cookie_token, refresh, register_verified, session
from tests._auth_helpers import login as _login_raw
from tests._auth_helpers import logout as _logout

PREFIX = settings.API_V1_PREFIX + "/auth"
EMAIL = "seller@example.com"
PASSWORD = "S3curePass!"


def _register(client: TestClient, email: str = EMAIL) -> dict[str, Any]:
    return register_verified(client, email, PASSWORD)


def _login(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> Any:
    return _login_raw(client, email, password)


def _auth(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_register_and_duplicate(client: TestClient, db_session: Session) -> None:
    resp = client.post(
        f"{PREFIX}/register", json={"email": "Seller@Example.com", "password": PASSWORD}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == EMAIL and body["is_verified"] is False
    assert "hashed_password" not in body
    user = db_session.query(User).one()
    assert user.hashed_password != PASSWORD
    assert user.hashed_password and user.hashed_password.startswith("$2")
    assert (
        client.post(f"{PREFIX}/register", json={"email": EMAIL, "password": PASSWORD}).status_code
        == 409
    )


def test_register_validation(client: TestClient) -> None:
    assert (
        client.post(f"{PREFIX}/register", json={"email": "bad", "password": PASSWORD}).status_code
        == 422
    )
    assert (
        client.post(f"{PREFIX}/register", json={"email": EMAIL, "password": "short"}).status_code
        == 422
    )


def test_login_success_and_failure(client: TestClient) -> None:
    _register(client)
    ok = _login(client)
    assert ok.status_code == 200
    assert ok.json()["token_type"] == "bearer"
    assert _login(client, password="wrong-password").status_code == 401
    assert _login(client, email="nobody@example.com").status_code == 401


def test_me_get_put(client: TestClient) -> None:
    _register(client)
    tokens = session(client, EMAIL)
    me = client.get(f"{PREFIX}/me", headers=_auth(tokens))
    assert me.status_code == 200 and me.json()["email"] == EMAIL
    upd = client.put(f"{PREFIX}/me", json={"full_name": "New Name"}, headers=_auth(tokens))
    assert upd.json()["full_name"] == "New Name"
    pw = client.put(
        f"{PREFIX}/me",
        json={"current_password": PASSWORD, "password": "BrandNewPass1"},
        headers=_auth(tokens),
    )
    assert pw.status_code == 200
    assert "tokens" not in pw.json() and "refresh_token" not in pw.text
    assert cookie_token(pw)
    assert _login(client, password="BrandNewPass1").status_code == 200
    assert _login(client).status_code == 401


def test_me_requires_valid_access_token(client: TestClient) -> None:
    assert client.get(f"{PREFIX}/me").status_code == 401
    assert client.get(f"{PREFIX}/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    _register(client)
    tokens = session(client, EMAIL)
    # refresh token must not work as an access token
    bad = {"Authorization": f"Bearer {tokens['refresh_token']}"}
    assert client.get(f"{PREFIX}/me", headers=bad).status_code == 401


def test_inactive_user_rejected(client: TestClient, db_session: Session) -> None:
    _register(client)
    tokens = session(client, EMAIL)
    user = db_session.query(User).one()
    user.is_active = False
    db_session.commit()
    assert client.get(f"{PREFIX}/me", headers=_auth(tokens)).status_code == 401
    assert _login(client).status_code == 401


def test_refresh_rotation_and_reuse_detection(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_service, "ROTATION_GRACE_SECONDS", 0)
    _register(client)
    first = session(client, EMAIL)
    resp = refresh(client, first["refresh_token"])
    assert resp.status_code == 200
    assert set(resp.json()) == {"access_token", "token_type"}
    second = cookie_token(resp)
    assert second and second != first["refresh_token"]
    # raw tokens are not stored
    stored = {t.token for t in db_session.query(RefreshToken).all()}
    assert first["refresh_token"] not in stored
    # old token reuse (outside the grace window) -> 401 and whole family revoked
    assert refresh(client, first["refresh_token"]).status_code == 401
    assert refresh(client, second).status_code == 401


def test_refresh_rejects_garbage_and_access_token(client: TestClient) -> None:
    _register(client)
    tokens = session(client, EMAIL)
    assert refresh(client, "nope").status_code == 401
    assert refresh(client, tokens["access_token"]).status_code == 401


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    _register(client)
    tokens = session(client, EMAIL)
    out = _logout(client, tokens["refresh_token"])
    assert out.status_code == 200
    assert refresh(client, tokens["refresh_token"]).status_code == 401
    # logout is idempotent, also without any cookie
    assert _logout(client, tokens["refresh_token"]).status_code == 200
    assert _logout(client, None).status_code == 200


def test_password_reset_flow(client: TestClient, db_session: Session) -> None:
    _register(client)
    tokens = session(client, EMAIL)
    # unknown email gives the same response
    unknown = client.post(f"{PREFIX}/forgot-password", json={"email": "ghost@example.com"})
    known = client.post(f"{PREFIX}/forgot-password", json={"email": EMAIL})
    assert unknown.status_code == known.status_code == 200
    assert unknown.json() == known.json()

    user = db_session.query(User).one()
    token = jwt_utils.create_reset_token(user.id, user.hashed_password)
    resp = client.post(
        f"{PREFIX}/reset-password", json={"token": token, "new_password": "ResetPass123"}
    )
    assert resp.status_code == 200
    assert _login(client, password="ResetPass123").status_code == 200
    assert _login(client).status_code == 401
    # existing sessions revoked, token single-use
    assert refresh(client, tokens["refresh_token"]).status_code == 401
    again = client.post(
        f"{PREFIX}/reset-password", json={"token": token, "new_password": "AnotherPass123"}
    )
    assert again.status_code == 401


def test_reset_password_rejects_wrong_token_type(client: TestClient) -> None:
    _register(client)
    tokens = session(client, EMAIL)
    resp = client.post(
        f"{PREFIX}/reset-password",
        json={"token": tokens["access_token"], "new_password": "ResetPass123"},
    )
    assert resp.status_code == 401


def test_password_helpers() -> None:
    hashed = jwt_utils.hash_password(PASSWORD)
    assert jwt_utils.verify_password(PASSWORD, hashed)
    assert not jwt_utils.verify_password("other", hashed)
    assert not jwt_utils.verify_password(PASSWORD, None)
    assert not jwt_utils.verify_password(PASSWORD, "not-a-hash")


def test_expired_token_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
    token = jwt_utils.create_access_token(1)
    assert jwt_utils.decode_token(token, jwt_utils.ACCESS) is None


def test_admin_dependency(client: TestClient, db_session: Session) -> None:
    probe = FastAPI()

    @probe.get("/probe")
    async def _probe(user: User = Depends(get_current_admin)) -> dict[str, int]:
        return {"id": user.id}

    from app.database import get_db
    from app.exceptions import register_exception_handlers

    register_exception_handlers(probe)
    probe.dependency_overrides[get_db] = app.dependency_overrides[get_db]
    pc = TestClient(probe)
    _register(client)
    tokens = session(client, EMAIL)
    assert pc.get("/probe", headers=_auth(tokens)).status_code == 403
    user = db_session.query(User).one()
    user.is_admin = True
    db_session.commit()
    assert pc.get("/probe", headers=_auth(tokens)).status_code == 200


def test_google_start_not_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    resp = client.get(f"{PREFIX}/google", follow_redirects=False)
    assert resp.status_code == 503


def test_google_flow(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "csecret")
    start = client.get(f"{PREFIX}/google", follow_redirects=False)
    assert start.status_code in (302, 307)
    query = parse_qs(urlparse(start.headers["location"]).query)
    state = query["state"][0]
    assert query["client_id"] == ["cid"]

    async def fake_profile(code: str) -> dict[str, Any]:
        return {"email": "G@Example.com", "name": "G User", "email_verified": True}

    monkeypatch.setattr(oauth, "fetch_google_profile", fake_profile)

    bad = client.get(f"{PREFIX}/google/callback", params={"code": "x", "state": "forged"})
    assert bad.status_code == 401

    ok = client.get(
        f"{PREFIX}/google/callback", params={"code": "x", "state": state}, follow_redirects=False
    )
    assert ok.status_code in (302, 307)
    assert ok.headers["location"] == f"{settings.FRONTEND_URL}/auth/callback"
    assert cookie_token(ok)
    user = db_session.query(User).one()
    assert user.email == "g@example.com"
    assert user.oauth_provider == "google" and user.is_verified


def test_state_cannot_be_an_access_token() -> None:
    assert not oauth.verify_state(jwt_utils.create_access_token(1))
    assert oauth.verify_state(oauth.create_state())


def test_rate_limit_enforced(client: TestClient) -> None:
    limiter.enabled = True
    limiter.reset()
    codes = [
        client.post(f"{PREFIX}/forgot-password", json={"email": EMAIL}).status_code
        for _ in range(7)
    ]
    assert codes[:5] == [200] * 5
    assert 429 in codes[5:]


def test_service_get_or_create_existing_user(db_session: Session) -> None:
    user = User(email="a@example.com", hashed_password=None)
    db_session.add(user)
    db_session.commit()
    linked = auth_service.get_or_create_google_user(db_session, "a@example.com", "A")
    assert linked.id == user.id and linked.oauth_provider == "google"


def test_password_change_requires_current_password(client: TestClient) -> None:
    _register(client)
    tokens = session(client, EMAIL)
    h = _auth(tokens)
    missing = client.put(f"{PREFIX}/me", json={"password": "BrandNewPass1"}, headers=h)
    assert missing.status_code == 422
    wrong = client.put(
        f"{PREFIX}/me",
        json={"current_password": "wrong-password", "password": "BrandNewPass1"},
        headers=h,
    )
    assert wrong.status_code == 401
    assert _login(client).status_code == 200  # password unchanged


def test_password_change_revokes_refresh_tokens(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_service, "ROTATION_GRACE_SECONDS", 0)
    _register(client)
    old = session(client, EMAIL)
    other = session(client, EMAIL)  # a second session
    resp = client.put(
        f"{PREFIX}/me",
        json={"current_password": PASSWORD, "password": "BrandNewPass1"},
        headers=_auth(old),
    )
    assert resp.status_code == 200
    new_refresh = cookie_token(resp)
    assert new_refresh
    # the session that changed the password keeps working via the fresh cookie
    assert refresh(client, new_refresh).status_code == 200
    # old sessions are revoked (checked last: reuse of a revoked token revokes everything)
    for stale in (old, other):
        assert refresh(client, stale["refresh_token"]).status_code == 401
