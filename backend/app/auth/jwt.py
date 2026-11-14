"""JWT creation/verification and bcrypt password hashing."""

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import settings

logger = logging.getLogger(__name__)

ACCESS = "access"
REFRESH = "refresh"
RESET = "reset"
RESET_TOKEN_EXPIRE_MINUTES = 30
# Pinned: never derived from config or from the token header.
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def _encode(data: dict[str, Any], token_type: str, expires: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        **data,
        "exp": now + expires,
        "iat": now,
        "jti": uuid.uuid4().hex,
        "type": token_type,
    }
    return str(jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM))


def create_access_token(user_id: int) -> str:
    return _encode(
        {"sub": str(user_id)}, ACCESS, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(user_id: int) -> str:
    return _encode(
        {"sub": str(user_id)}, REFRESH, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def password_fingerprint(password_hash: str | None) -> str:
    return hashlib.sha256((password_hash or "").encode("utf-8")).hexdigest()[:16]


def create_reset_token(user_id: int, password_hash: str | None) -> str:
    """Reset token bound to the current password hash so it is single-use."""
    return _encode(
        {"sub": str(user_id), "fp": password_fingerprint(password_hash)},
        RESET,
        timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
    )


def hash_token(token: str) -> str:
    """Stable digest used to store refresh tokens at rest."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_token(token: str, expected_type: str) -> dict[str, Any] | None:
    """Return the payload if valid and of the expected type, else None."""
    try:
        payload: dict[str, Any] = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != expected_type or not str(payload.get("sub", "")).isdigit():
        logger.debug("Token type/subject mismatch")
        return None
    return payload
