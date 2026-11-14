"""Shared FastAPI dependencies."""

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.jwt import ACCESS, decode_token
from app.config import settings
from app.database import get_db
from app.exceptions import ForbiddenError, UnauthorizedError
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False
)

__all__ = ["get_current_admin", "get_current_user", "get_db", "oauth2_scheme"]


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode the bearer access token and load the active user."""
    if not token:
        raise UnauthorizedError("Not authenticated")
    payload = decode_token(token, ACCESS)
    if payload is None:
        raise UnauthorizedError("Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or disabled")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Require an authenticated admin user."""
    if not user.is_admin:
        raise ForbiddenError("Admin privileges required")
    return user
