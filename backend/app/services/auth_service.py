"""Auth business logic: users, token issuing/rotation, password reset."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import jwt as jwt_utils
from app.config import settings
from app.exceptions import ConflictError, UnauthorizedError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenResponse, UserCreate, UserUpdate

logger = logging.getLogger(__name__)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def register_user(db: Session, data: UserCreate) -> User:
    email = data.email.lower()
    if get_user_by_email(db, email):
        raise ConflictError("Email already registered")
    user = User(
        email=email,
        hashed_password=jwt_utils.hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if not user or not jwt_utils.verify_password(password, user.hashed_password):
        raise UnauthorizedError("Incorrect email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled")
    return user


def issue_tokens(db: Session, user: User) -> TokenResponse:
    refresh = jwt_utils.create_refresh_token(user.id)
    payload = jwt_utils.decode_token(refresh, jwt_utils.REFRESH)
    if payload is None:  # pragma: no cover - freshly minted token
        raise UnauthorizedError("Could not issue token")
    db.add(
        RefreshToken(
            user_id=user.id,
            token=jwt_utils.hash_token(refresh),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    )
    db.commit()
    return TokenResponse(access_token=jwt_utils.create_access_token(user.id), refresh_token=refresh)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def refresh_tokens(db: Session, refresh_token: str) -> TokenResponse:
    """Rotate: revoke the presented token and issue a new pair."""
    payload = jwt_utils.decode_token(refresh_token, jwt_utils.REFRESH)
    if payload is None:
        raise UnauthorizedError("Invalid refresh token")
    user_id = int(payload["sub"])
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token == jwt_utils.hash_token(refresh_token))
    )
    if row is None or row.user_id != user_id:
        raise UnauthorizedError("Invalid refresh token")
    if row.revoked:
        # Reuse of a rotated token: assume theft, revoke all sessions for the user.
        logger.warning("Refresh token reuse detected for user %s", user_id)
        revoke_all_user_tokens(db, user_id)
        raise UnauthorizedError("Refresh token revoked")
    if _aware(row.expires_at) < datetime.now(UTC):
        raise UnauthorizedError("Refresh token expired")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or disabled")
    row.revoked = True
    db.commit()
    return issue_tokens(db, user)


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token == jwt_utils.hash_token(refresh_token))
    )
    if row and not row.revoked:
        row.revoked = True
        db.commit()


def revoke_all_user_tokens(db: Session, user_id: int) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    db.commit()


def update_profile(db: Session, user: User, data: UserUpdate) -> tuple[User, TokenResponse | None]:
    """Update the profile.

    Changing the password requires the correct current password. On change, all
    of the user's refresh tokens are revoked (other sessions are signed out) and a
    fresh token pair is returned so the calling session can continue.
    """
    if data.password is not None:
        if not jwt_utils.verify_password(data.current_password or "", user.hashed_password):
            raise UnauthorizedError("Current password is incorrect")
        user.hashed_password = jwt_utils.hash_password(data.password)
    if data.full_name is not None:
        user.full_name = data.full_name
    db.commit()
    db.refresh(user)
    tokens: TokenResponse | None = None
    if data.password is not None:
        revoke_all_user_tokens(db, user.id)
        tokens = issue_tokens(db, user)
    return user, tokens


def get_or_create_google_user(db: Session, email: str, full_name: str | None) -> User:
    user = get_user_by_email(db, email)
    if user is None:
        user = User(
            email=email.lower(),
            full_name=full_name,
            is_verified=True,
            oauth_provider="google",
        )
        db.add(user)
    else:
        if not user.is_active:
            raise UnauthorizedError("Account is disabled")
        user.is_verified = True
        if user.oauth_provider is None:
            user.oauth_provider = "google"
    db.commit()
    db.refresh(user)
    return user


def send_password_reset(db: Session, email: str) -> None:
    """Silent about whether the account exists. Email delivery is a logged stub."""
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return
    token = jwt_utils.create_reset_token(user.id, user.hashed_password)
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    # TODO: integrate SMTP (settings.SMTP_*). The link is only logged in DEBUG mode.
    logger.info("Password reset requested for user_id=%s (email stub)", user.id)
    if settings.DEBUG:
        logger.debug("Password reset link: %s", link)


def reset_password(db: Session, token: str, new_password: str) -> None:
    payload = jwt_utils.decode_token(token, jwt_utils.RESET)
    if payload is None:
        raise UnauthorizedError("Invalid or expired reset token")
    user = db.get(User, int(payload["sub"]))
    if (
        user is None
        or not user.is_active
        or payload.get("fp") != jwt_utils.password_fingerprint(user.hashed_password)
    ):
        raise UnauthorizedError("Invalid or expired reset token")
    user.hashed_password = jwt_utils.hash_password(new_password)
    db.commit()
    revoke_all_user_tokens(db, user.id)
