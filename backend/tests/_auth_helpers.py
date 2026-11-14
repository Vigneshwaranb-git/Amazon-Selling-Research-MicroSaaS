"""Shared auth helpers: verified-user creation, login, cookie-based refresh."""

from http.cookies import SimpleCookie
from typing import Any

from fastapi.testclient import TestClient

from app.auth import jwt as jwt_utils
from app.config import settings

AUTH = settings.API_V1_PREFIX + "/auth"
PW = "S3curePass!"
CSRF = {"X-Requested-With": "XMLHttpRequest"}


def register_verified(
    client: TestClient, email: str = "s@example.com", password: str = PW
) -> dict[str, Any]:
    """Register through the API, then verify through the real verify-email endpoint."""
    r = client.post(
        f"{AUTH}/register", json={"email": email, "password": password, "full_name": "S"}
    )
    assert r.status_code == 201, r.text
    user = dict(r.json())
    token = jwt_utils.create_email_verify_token(user["id"], user["email"])
    v = client.post(f"{AUTH}/verify-email", json={"token": token})
    assert v.status_code == 200, v.text
    return user


def login(client: TestClient, email: str = "s@example.com", password: str = PW) -> Any:
    return client.post(f"{AUTH}/login", data={"username": email, "password": password})


def set_cookie_header(resp: Any) -> str | None:
    for raw in resp.headers.get_list("set-cookie"):
        if raw.startswith("refresh_token="):
            return str(raw)
    return None


def cookie_token(resp: Any) -> str | None:
    raw = set_cookie_header(resp)
    if raw is None:
        return None
    morsel = SimpleCookie(raw)["refresh_token"].value
    return morsel or None


def session(client: TestClient, email: str = "s@example.com", password: str = PW) -> dict[str, str]:
    """Log in and return {access_token, refresh_token} (refresh read from the cookie)."""
    resp = login(client, email, password)
    assert resp.status_code == 200, resp.text
    refresh_token = cookie_token(resp)
    assert refresh_token
    return {"access_token": resp.json()["access_token"], "refresh_token": refresh_token}


def register_and_login(
    client: TestClient, email: str = "s@example.com", password: str = PW
) -> dict[str, str]:
    register_verified(client, email, password)
    return session(client, email, password)


def refresh(client: TestClient, token: str | None, csrf: bool = True) -> Any:
    """POST /auth/refresh presenting ``token`` as the refresh cookie (explicit header)."""
    headers = dict(CSRF) if csrf else {}
    if token is not None:
        headers["Cookie"] = f"refresh_token={token}"
    return client.post(f"{AUTH}/refresh", headers=headers)


def logout(client: TestClient, token: str | None) -> Any:
    headers = {"Cookie": f"refresh_token={token}"} if token else {}
    return client.post(f"{AUTH}/logout", headers=headers)
