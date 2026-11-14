"""Auth business logic: users, token issuing/rotation, email verification, password reset."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import jwt as jwt_utils
from app.config import settings
from app.exceptions import (
    ConflictError,
    EmailNotVerifiedError,
    InvalidTokenError,
    UnauthorizedError,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import UserCreate, UserUpdate
from app.services.email_service import queue_email
from app.services.email_templates import password_reset_email, verification_email

logger = logging.getLogger(__name__)

# A just-rotated refresh token stays replayable for this long (multi-tab races).
ROTATION_GRACE_SECONDS = 10


@dataclass(frozen=True)
class IssuedTokens:
    """Access token (JSON body) plus the refresh token (cookie only, never serialized)."""

    access_token: str
    refresh_token: str


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def _promote_if_admin_email(user: User) -> bool:
    """Grant admin to users listed in ADMIN_EMAILS. Returns True if the user changed."""
    if not user.is_admin and user.email.lower() in settings.ADMIN_EMAILS:
        user.is_admin = True
        return True
    return False


def register_user(db: Session, data: UserCreate) -> User:
    email = data.email.lower()
    if get_user_by_email(db, email):
        raise ConflictError("Email already registered")
    user = User(
        email=email,
        hashed_password=jwt_utils.hash_password(data.password),
        full_name=data.full_name,
        is_verified=False,
    )
    _promote_if_admin_email(user)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def send_verification(user: User, background_tasks: BackgroundTasks | None = None) -> None:
    """Queue the welcome + verification email; never raises."""
    try:
        token = jwt_utils.create_email_verify_token(user.id, user.email)
        queue_email(background_tasks, verification_email(user.email, user.full_name, token))
    except Exception:
        logger.exception("Could not queue verification email for user_id=%s", user.id)


def verify_email(db: Session, token: str) -> None:
    """Mark the account verified. Idempotent; any bad/expired/mismatched token -> 400."""
    payload = jwt_utils.decode_token(token, jwt_utils.EMAIL_VERIFY)
    if payload is None:
        raise InvalidTokenError("Invalid or expired verification token")
    user = db.get(User, int(payload["sub"]))
    if (
        user is None
        or not user.is_active
        or str(payload.get("email", "")).lower() != user.email.lower()
    ):
        raise InvalidTokenError("Invalid or expired verification token")
    if not user.is_verified:
        user.is_verified = True
        db.commit()


def resend_verification(
    db: Session, email: str, background_tasks: BackgroundTasks | None = None
) -> None:
    """Silent about whether the account exists; sends only for unverified password accounts."""
    user = get_user_by_email(db, email)
    if user is None or not user.is_active or user.is_verified or not user.hashed_password:
        return
    send_verification(user, background_tasks)


def authenticate(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    # Password first: verification state is never revealed without proving the password.
    if not user or not jwt_utils.verify_password(password, user.hashed_password):
        raise UnauthorizedError("Incorrect email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled")
    if not user.is_verified:
        raise EmailNotVerifiedError()
    if _promote_if_admin_email(user):
        db.commit()
    return user


def _store_refresh(db: Session, user_id: int, raw: str) -> None:
    payload = jwt_utils.decode_token(raw, jwt_utils.REFRESH)
    if payload is None:  # pragma: no cover - freshly minted token
        raise UnauthorizedError("Could not issue token")
    db.add(
        RefreshToken(
            user_id=user_id,
            token=jwt_utils.hash_token(raw),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    )


def issue_tokens(db: Session, user: User) -> IssuedTokens:
    refresh = jwt_utils.create_refresh_token(user.id)
    _store_refresh(db, user.id, refresh)
    db.commit()
    return IssuedTokens(jwt_utils.create_access_token(user.id), refresh)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _grace_successor(db: Session, row: RefreshToken, token: str, now: datetime) -> str | None:
    """Successor of a token rotated within the grace window, else None.

    Rotation marks the old row revoked and sets its ``expires_at`` to
    ``rotated_at + grace``; every other revocation sets ``expires_at`` to the revocation
    time. So a revoked row whose expiry is still in the (near) future was rotated moments
    ago, and its successor (deterministic from the old token) can be re-derived without
    storing raw tokens.
    """
    expires = _aware(row.expires_at)
    if not (now < expires <= now + timedelta(seconds=ROTATION_GRACE_SECONDS)):
        return None
    rotated_at = expires - timedelta(seconds=ROTATION_GRACE_SECONDS)
    successor = jwt_utils.create_rotated_refresh_token(row.user_id, token, rotated_at)
    succ_row = db.scalar(
        select(RefreshToken).where(RefreshToken.token == jwt_utils.hash_token(successor))
    )
    if succ_row is None or succ_row.revoked:
        return None
    return successor


def refresh_tokens(db: Session, refresh_token: str) -> IssuedTokens:
    """Rotate: revoke the presented token and issue its successor."""
    payload = jwt_utils.decode_token(refresh_token, jwt_utils.REFRESH)
    if payload is None:
        raise UnauthorizedError("Invalid refresh token")
    user_id = int(payload["sub"])
    row = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token == jwt_utils.hash_token(refresh_token))
        .with_for_update()
    )
    if row is None or row.user_id != user_id:
        raise UnauthorizedError("Invalid refresh token")
    now = datetime.now(UTC).replace(microsecond=0)
    if row.revoked:
        successor = _grace_successor(db, row, refresh_token, now)
        if successor is not None:
            db.rollback()  # release the row lock; nothing changed
            return IssuedTokens(jwt_utils.create_access_token(user_id), successor)
        if _aware(row.expires_at) > now:
            # Rotated moments ago but the successor is gone (revoked): no replay.
            db.rollback()
            raise UnauthorizedError("Refresh token revoked")
        # Reuse of a rotated token: assume theft, revoke all sessions for the user.
        logger.warning("Refresh token reuse detected for user %s", user_id)
        revoke_all_user_tokens(db, user_id)
        raise UnauthorizedError("Refresh token revoked")
    if _aware(row.expires_at) < now:
        raise UnauthorizedError("Refresh token expired")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or disabled")
    new_refresh = jwt_utils.create_rotated_refresh_token(user_id, refresh_token, now)
    row.revoked = True
    row.expires_at = now + timedelta(seconds=ROTATION_GRACE_SECONDS)
    _store_refresh(db, user_id, new_refresh)
    db.commit()
    return IssuedTokens(jwt_utils.create_access_token(user_id), new_refresh)


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token == jwt_utils.hash_token(refresh_token))
    )
    if row and not row.revoked:
        row.revoked = True
        row.expires_at = datetime.now(UTC)
        db.commit()


def revoke_all_user_tokens(db: Session, user_id: int) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True, expires_at=datetime.now(UTC))
    )
    db.commit()


def update_profile(db: Session, user: User, data: UserUpdate) -> tuple[User, IssuedTokens | None]:
    """Update the profile.

    Changing the password requires the correct current password. On change, all
    of the user's refresh tokens are revoked (other sessions are signed out) and a
    fresh token pair is issued so the calling session can continue.
    """
    if data.password is not None:
        if not jwt_utils.verify_password(data.current_password or "", user.hashed_password):
            raise UnauthorizedError("Current password is incorrect")
        user.hashed_password = jwt_utils.hash_password(data.password)
    if data.full_name is not None:
        user.full_name = data.full_name
    db.commit()
    db.refresh(user)
    tokens: IssuedTokens | None = None
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
        _promote_if_admin_email(user)
        db.add(user)
    else:
        if not user.is_active:
            raise UnauthorizedError("Account is disabled")
        if not user.is_verified and user.hashed_password:
            # Unverified password signup: whoever registered it never proved they own the
            # mailbox (possible pre-registration). Do not link silently: drop the password and
            # kill every session so the pre-registrant is locked out.
            logger.warning("Google sign-in took over unverified password account %s", user.id)
            user.hashed_password = None
            revoke_all_user_tokens(db, user.id)
        user.is_verified = True
        if user.oauth_provider is None:
            user.oauth_provider = "google"
        _promote_if_admin_email(user)
    db.commit()
    db.refresh(user)
    return user


def send_password_reset(
    db: Session, email: str, background_tasks: BackgroundTasks | None = None
) -> None:
    """Silent about whether the account exists; the email is sent off the request path."""
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return
    token = jwt_utils.create_reset_token(user.id, user.hashed_password)
    queue_email(background_tasks, password_reset_email(user.email, token))
    logger.info("Password reset email queued for user_id=%s", user.id)


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
    user.is_verified = True  # the reset link proved control of the mailbox
    db.commit()
    revoke_all_user_tokens(db, user.id)
