"""Email verification (H1) and refresh-token cookie (H2) behaviour."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.auth import jwt as jwt_utils
from app.auth import oauth
from app.config import Settings, settings
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.rate_limit import limiter
from app.services import auth_service
from tests._auth_helpers import (
    AUTH,
    CSRF,
    PW,
    cookie_token,
    login,
    logout,
    refresh,
    register_and_login,
    register_verified,
    session,
    set_cookie_header,
)
from tests._mail import mail  # noqa: F401

EMAIL = "new@example.com"


def _register(client: TestClient, email: str = EMAIL) -> dict[str, Any]:
    r = client.post(f"{AUTH}/register", json={"email": email, "password": PW, "full_name": "N"})
    assert r.status_code == 201, r.text
    return dict(r.json())


def _verify_token_from_mail(box: Any) -> str:
    link = re.search(r"https?://\S+", box.outbox[-1].text)
    assert link is not None
    url = urlparse(link.group(0))
    assert url.path == "/verify-email"
    return parse_qs(url.query)["token"][0]


# ------------------------------------------------------------- H1: verification
def test_register_unverified_and_emails_link(client: TestClient, mail: Any) -> None:  # noqa: F811
    body = _register(client)
    assert body["is_verified"] is False
    assert len(mail.outbox) == 1
    assert mail.outbox[0].text.count(f"{settings.FRONTEND_URL}/verify-email?token=") == 1
    payload = jwt_utils.decode_token(_verify_token_from_mail(mail), jwt_utils.EMAIL_VERIFY)
    assert payload is not None
    assert payload["sub"] == str(body["id"]) and payload["email"] == EMAIL
    assert payload["exp"] - payload["iat"] == 24 * 3600


def test_login_blocked_until_verified(client: TestClient, mail: Any) -> None:  # noqa: F811
    _register(client)
    blocked = login(client, EMAIL)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
    assert set_cookie_header(blocked) is None
    v = client.post(f"{AUTH}/verify-email", json={"token": _verify_token_from_mail(mail)})
    assert v.status_code == 200 and v.json()["message"]
    assert login(client, EMAIL).status_code == 200


def test_wrong_password_checked_before_verification_state(client: TestClient) -> None:
    _register(client)
    wrong = login(client, EMAIL, "wrong-password-1")
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "UNAUTHORIZED"
    assert login(client, "ghost@example.com").status_code == 401


def test_verify_email_idempotent(client: TestClient, db_session: Session) -> None:
    user = _register(client)
    token = jwt_utils.create_email_verify_token(user["id"], EMAIL)
    for _ in range(2):
        assert client.post(f"{AUTH}/verify-email", json={"token": token}).status_code == 200
    assert db_session.query(User).one().is_verified is True


def test_verify_email_rejects_bad_tokens(client: TestClient, db_session: Session) -> None:
    uid = _register(client)["id"]

    def verify(token: str) -> Any:
        return client.post(f"{AUTH}/verify-email", json={"token": token})

    def signed(key: str, exp: datetime) -> str:
        claims = {"sub": str(uid), "email": EMAIL, "type": "email_verify", "exp": exp}
        return str(pyjwt.encode(claims, key, algorithm="HS256"))

    now = datetime.now(UTC)
    cases = {
        "garbage": "nope",
        "other-email": jwt_utils.create_email_verify_token(uid, "other@example.com"),
        "no-user": jwt_utils.create_email_verify_token(9999, EMAIL),
        "access": jwt_utils.create_access_token(uid),
        "refresh": jwt_utils.create_refresh_token(uid),
        "reset": jwt_utils.create_reset_token(uid, None),
        "expired": signed(settings.SECRET_KEY, now - timedelta(seconds=1)),
        "forged": signed("wrong-key-wrong-key-wrong-key-wrong", now + timedelta(hours=1)),
    }
    for name, tok in cases.items():
        r = verify(tok)
        assert r.status_code == 400, name
        assert r.json()["error"]["code"] == "INVALID_TOKEN", name
    assert db_session.query(User).one().is_verified is False
    # inactive accounts cannot be verified either
    db_session.query(User).one().is_active = False
    db_session.commit()
    assert verify(jwt_utils.create_email_verify_token(uid, EMAIL)).status_code == 400


def test_verify_token_not_usable_elsewhere(client: TestClient) -> None:
    user = _register(client)
    token = jwt_utils.create_email_verify_token(user["id"], EMAIL)
    assert client.get(f"{AUTH}/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert refresh(client, token).status_code == 401
    r = client.post(f"{AUTH}/reset-password", json={"token": token, "new_password": "NewPass1234"})
    assert r.status_code == 401
    assert jwt_utils.decode_token(token, jwt_utils.ACCESS) is None
    assert jwt_utils.decode_token(token, jwt_utils.RESET) is None
    assert jwt_utils.decode_token(jwt_utils.create_access_token(1), jwt_utils.EMAIL_VERIFY) is None


def test_resend_verification_uniform(client: TestClient, mail: Any) -> None:  # noqa: F811
    _register(client)
    register_verified(client, "done@example.com")
    mail.backend.outbox.clear()
    bodies = []
    for email in (EMAIL, "done@example.com", "ghost@example.com"):
        r = client.post(f"{AUTH}/resend-verification", json={"email": email})
        assert r.status_code == 200
        bodies.append(r.json())
    assert bodies[0] == bodies[1] == bodies[2]
    assert [m.to for m in mail.outbox] == [EMAIL]  # only the unverified account
    assert client.post(f"{AUTH}/resend-verification", json={"email": "bad"}).status_code == 422


def test_resend_skips_inactive_and_google_only(
    client: TestClient,
    db_session: Session,
    mail: Any,  # noqa: F811
) -> None:
    db_session.add(User(email="off@example.com", hashed_password="h", is_active=False))
    db_session.add(User(email="goog@example.com", hashed_password=None, is_verified=False))
    db_session.commit()
    for email in ("off@example.com", "goog@example.com"):
        assert client.post(f"{AUTH}/resend-verification", json={"email": email}).status_code == 200
    assert mail.outbox == []


def test_resend_rate_limited(client: TestClient) -> None:
    limiter.enabled = True
    limiter.reset()
    codes = [
        client.post(f"{AUTH}/resend-verification", json={"email": EMAIL}).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [200] * 3 and 429 in codes[3:]


def test_password_reset_verifies_account(client: TestClient, db_session: Session) -> None:
    user = _register(client)
    row = db_session.query(User).one()
    token = jwt_utils.create_reset_token(user["id"], row.hashed_password)
    r = client.post(f"{AUTH}/reset-password", json={"token": token, "new_password": "NewPass1234"})
    assert r.status_code == 200
    db_session.refresh(row)
    assert row.is_verified is True
    assert login(client, EMAIL, "NewPass1234").status_code == 200


def test_google_takes_over_unverified_password_account(
    client: TestClient, db_session: Session
) -> None:
    # an attacker pre-registered the victim's address and holds a session
    _register(client, "victim@example.com")
    victim = db_session.query(User).filter_by(email="victim@example.com").one()
    stale = auth_service.issue_tokens(db_session, victim)
    linked = auth_service.get_or_create_google_user(db_session, "victim@example.com", "Victim")
    assert linked.id == victim.id
    assert linked.hashed_password is None and linked.is_verified and linked.oauth_provider
    assert login(client, "victim@example.com").status_code == 401  # attacker password is dead
    assert refresh(client, stale.refresh_token).status_code == 401  # and so are its sessions
    assert db_session.query(RefreshToken).filter_by(user_id=victim.id, revoked=False).count() == 0


def test_google_links_verified_password_account_normally(
    client: TestClient, db_session: Session
) -> None:
    register_verified(client, "ok@example.com")
    before = db_session.query(User).one().hashed_password
    tokens = session(client, "ok@example.com")
    user = auth_service.get_or_create_google_user(db_session, "ok@example.com", "Ok")
    assert user.hashed_password == before and user.oauth_provider == "google"
    assert login(client, "ok@example.com").status_code == 200
    assert refresh(client, tokens["refresh_token"]).status_code == 200


# --------------------------------------------------------- H2: refresh cookie
def test_login_sets_hardened_cookie_and_no_token_in_body(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    register_verified(client)
    resp = login(client)
    assert resp.status_code == 200
    assert set(resp.json()) == {"access_token", "token_type"}
    raw = set_cookie_header(resp)
    assert raw is not None
    parts = {p.strip().lower() for p in raw.split(";")}
    assert {"httponly", "secure", "samesite=strict", "path=/api/v1/auth"} <= parts
    assert f"max-age={settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400}" in parts
    token = cookie_token(resp)
    assert token and token not in resp.text


def test_cookie_secure_flag_configurable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    register_verified(client)
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    raw = set_cookie_header(login(client))
    assert raw is not None and "secure" not in raw.lower()
    assert Settings.model_fields["COOKIE_SECURE"].default is True


def test_refresh_via_cookie_jar_and_rotation(client: TestClient) -> None:
    register_verified(client)
    old = cookie_token(login(client))
    # the browser-like cookie jar alone (plus the CSRF header) is enough
    resp = client.post(f"{AUTH}/refresh", headers=CSRF)
    assert resp.status_code == 200
    assert set(resp.json()) == {"access_token", "token_type"}
    new = cookie_token(resp)
    assert new and new != old
    raw = set_cookie_header(resp)
    assert raw is not None and "httponly" in raw.lower() and "samesite=strict" in raw.lower()
    bearer = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    assert client.get(f"{AUTH}/me", headers=bearer).status_code == 200


def test_refresh_requires_csrf_header(client: TestClient) -> None:
    tokens = register_and_login(client)
    cookie = {"Cookie": f"refresh_token={tokens['refresh_token']}"}
    for extra in ({}, {"X-Requested-With": "fetch"}):
        r = client.post(f"{AUTH}/refresh", headers={**extra, **cookie})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "FORBIDDEN"
    assert refresh(client, tokens["refresh_token"], csrf=False).status_code == 403
    # a rejected CSRF attempt must not consume the token
    assert refresh(client, tokens["refresh_token"]).status_code == 200


def test_refresh_ignores_body_and_needs_cookie(client: TestClient) -> None:
    tokens = register_and_login(client)
    client.cookies.clear()
    body_only = client.post(
        f"{AUTH}/refresh", headers=CSRF, json={"refresh_token": tokens["refresh_token"]}
    )
    assert body_only.status_code == 401


def test_refresh_failure_clears_cookie(client: TestClient) -> None:
    for token in (None, "garbage"):
        r = refresh(client, token)
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "UNAUTHORIZED"
        raw = set_cookie_header(r)
        assert raw is not None and 'refresh_token=""' in raw
        assert "max-age=0" in raw.lower() and "path=/api/v1/auth" in raw.lower()


def test_logout_clears_cookie_and_revokes(client: TestClient, db_session: Session) -> None:
    tokens = register_and_login(client)
    out = logout(client, tokens["refresh_token"])
    assert out.status_code == 200
    raw = set_cookie_header(out)
    assert raw is not None and 'refresh_token=""' in raw and "max-age=0" in raw.lower()
    assert db_session.query(RefreshToken).filter_by(revoked=False).count() == 0
    assert refresh(client, tokens["refresh_token"]).status_code == 401
    again = logout(client, None)
    assert again.status_code == 200 and set_cookie_header(again) is not None


def test_google_callback_cookie_and_clean_redirect(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "cs")

    async def fake_profile(code: str) -> dict[str, Any]:
        return {"email": "g@example.com", "name": "G", "email_verified": True}

    monkeypatch.setattr(oauth, "fetch_google_profile", fake_profile)
    resp = client.get(
        f"{AUTH}/google/callback",
        params={"code": "x", "state": oauth.create_state()},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert location == f"{settings.FRONTEND_URL}/auth/callback"
    token = cookie_token(resp)
    assert token and token not in location
    raw = set_cookie_header(resp)
    assert raw is not None and "httponly" in raw.lower() and "samesite=strict" in raw.lower()
    assert refresh(client, token).status_code == 200


def test_password_change_sets_cookie_without_body_tokens(client: TestClient) -> None:
    register_verified(client)
    tokens = session(client)
    bearer = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = client.put(
        f"{AUTH}/me", json={"current_password": PW, "password": "BrandNewPass1"}, headers=bearer
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "tokens" not in body and "refresh_token" not in resp.text and body["email"]
    assert cookie_token(resp)
    # a profile-only update does not touch the cookie
    plain = client.put(f"{AUTH}/me", json={"full_name": "Zed"}, headers=bearer)
    assert plain.status_code == 200 and set_cookie_header(plain) is None


def test_no_refresh_token_in_any_body_or_url(client: TestClient) -> None:
    register_verified(client)
    tokens = session(client)
    rotated = refresh(client, tokens["refresh_token"])
    new_token = cookie_token(rotated)
    assert new_token
    for resp in (rotated, login(client)):
        assert "refresh_token" not in resp.json()
        assert new_token not in resp.text
        assert "token=" not in str(resp.url)


# ------------------------------------------------------- rotation grace window
def test_grace_replay_returns_same_successor(client: TestClient, db_session: Session) -> None:
    tokens = register_and_login(client)
    first = refresh(client, tokens["refresh_token"])
    successor = cookie_token(first)
    assert successor
    replay = refresh(client, tokens["refresh_token"])  # second tab, same old cookie
    assert replay.status_code == 200
    assert cookie_token(replay) == successor
    assert replay.json()["access_token"]
    # nothing was killed: exactly one live token, the successor
    live = db_session.query(RefreshToken).filter_by(revoked=False).all()
    assert [t.token for t in live] == [jwt_utils.hash_token(successor)]
    assert refresh(client, successor).status_code == 200


def test_grace_chain_across_two_rotations(client: TestClient) -> None:
    tokens = register_and_login(client)
    b = cookie_token(refresh(client, tokens["refresh_token"]))
    assert b
    c = cookie_token(refresh(client, b))
    assert c
    assert cookie_token(refresh(client, b)) == c  # replay of B yields C
    # A's successor (B) is already rotated: refused, but sessions survive
    assert refresh(client, tokens["refresh_token"]).status_code == 401
    assert refresh(client, c).status_code == 200


def test_replay_after_grace_revokes_everything(client: TestClient, db_session: Session) -> None:
    tokens = register_and_login(client)
    other = session(client)
    successor = cookie_token(refresh(client, tokens["refresh_token"]))
    assert successor
    row = db_session.scalar(
        select(RefreshToken).where(
            RefreshToken.token == jwt_utils.hash_token(tokens["refresh_token"])
        )
    )
    assert row is not None and row.revoked
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)  # grace over
    db_session.commit()
    assert refresh(client, tokens["refresh_token"]).status_code == 401
    assert db_session.query(RefreshToken).filter_by(revoked=False).count() == 0
    assert refresh(client, successor).status_code == 401
    assert refresh(client, other["refresh_token"]).status_code == 401


def test_grace_not_granted_to_logged_out_tokens(client: TestClient) -> None:
    tokens = register_and_login(client)
    logout(client, tokens["refresh_token"])
    assert refresh(client, tokens["refresh_token"]).status_code == 401
    # rotated, then the successor was logged out: replay of the old one is refused
    t2 = session(client)
    succ = cookie_token(refresh(client, t2["refresh_token"]))
    logout(client, succ)
    assert refresh(client, t2["refresh_token"]).status_code == 401


def test_rotation_locks_row(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[bool] = []
    original = Select.with_for_update

    def spy(self: Select[Any], *a: Any, **k: Any) -> Select[Any]:
        seen.append(True)
        return original(self, *a, **k)

    monkeypatch.setattr(Select, "with_for_update", spy)
    tokens = register_and_login(client)
    assert refresh(client, tokens["refresh_token"]).status_code == 200
    assert seen


def test_deterministic_successor_depends_on_input() -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    a = jwt_utils.create_rotated_refresh_token(1, "tok", now)
    assert a == jwt_utils.create_rotated_refresh_token(1, "tok", now)
    assert a != jwt_utils.create_rotated_refresh_token(1, "tok2", now)
    assert jwt_utils.decode_token(a, jwt_utils.REFRESH) is not None


# ------------------------------------------------------------------------ CORS
def test_cors_credentials_and_headers(client: TestClient) -> None:
    origin = settings.ALLOWED_ORIGINS[0]
    pre = client.options(
        f"{AUTH}/refresh",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-requested-with",
        },
    )
    assert pre.status_code == 200
    assert pre.headers["access-control-allow-origin"] == origin
    assert pre.headers["access-control-allow-credentials"] == "true"
    assert "x-requested-with" in pre.headers["access-control-allow-headers"].lower()
    evil = client.options(
        f"{AUTH}/refresh",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in evil.headers


def test_wildcard_origin_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", '["*"]')
    with pytest.raises(ValueError):
        Settings()  # type: ignore[call-arg]


def test_verification_email_failure_does_not_break_register(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **k: Any) -> None:
        raise RuntimeError("queue down")

    monkeypatch.setattr(auth_service, "queue_email", boom)
    assert _register(client)["is_verified"] is False
