"""Google OAuth (authorization code flow) with signed state verification."""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from app.auth.jwt import JWT_ALGORITHM
from app.config import settings
from app.exceptions import AppException

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
STATE_TTL_MINUTES = 10


class OAuthError(AppException):
    def __init__(self, message: str = "OAuth failed", status_code: int = 400) -> None:
        super().__init__(message, "OAUTH_ERROR", status_code)


def redirect_uri() -> str:
    return f"{settings.VITE_API_URL}{settings.API_V1_PREFIX}/auth/google/callback"


def is_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def create_state() -> str:
    """Signed, short-lived state token (stateless CSRF protection)."""
    payload = {
        "nonce": secrets.token_urlsafe(16),
        "type": "oauth_state",
        "exp": datetime.now(UTC) + timedelta(minutes=STATE_TTL_MINUTES),
    }
    return str(jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM))


def verify_state(state: str) -> bool:
    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return False
    return bool(payload.get("type") == "oauth_state")


def build_authorization_url(state: str) -> str:
    if not is_configured():
        raise OAuthError("Google OAuth is not configured", 503)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def fetch_google_profile(code: str) -> dict[str, Any]:
    """Exchange the authorization code and return the verified Google profile."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri(),
                    "grant_type": "authorization_code",
                },
            )
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]
            info_resp = await client.get(
                GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            info_resp.raise_for_status()
            profile: dict[str, Any] = info_resp.json()
        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("Google OAuth exchange failed: %s", exc)
            raise OAuthError("Google authentication failed") from exc
    if not profile.get("email") or not profile.get("email_verified", False):
        raise OAuthError("Google account email not verified")
    return profile
