"""Authentication endpoints."""

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import oauth
from app.config import settings
from app.dependencies import get_current_user, get_db
from app.exceptions import UnauthorizedError
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.auth import (
    ForgotPasswordRequest,
    LogoutRequest,
    MessageResponse,
    ProfileUpdateResponse,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("10/minute")
def register(request: Request, data: UserCreate, db: Session = Depends(get_db)) -> User:
    return auth_service.register_user(db, data)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = auth_service.authenticate(db, form.username, form.password)
    return auth_service.issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
def refresh(request: Request, data: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return auth_service.refresh_tokens(db, data.refresh_token)


@router.post("/logout", response_model=MessageResponse)
@limiter.limit("30/minute")
def logout(request: Request, data: LogoutRequest, db: Session = Depends(get_db)) -> MessageResponse:
    auth_service.revoke_refresh_token(db, data.refresh_token)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
def read_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/me", response_model=ProfileUpdateResponse)
def update_me(
    data: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileUpdateResponse:
    """Update profile. A password change needs ``current_password``; it revokes all
    refresh tokens and returns a fresh pair in ``tokens`` for the current session."""
    updated, tokens = auth_service.update_profile(db, user, data)
    body = ProfileUpdateResponse.model_validate(updated)
    body.tokens = tokens
    return body


@router.get("/google")
@limiter.limit("20/minute")
def google_login(request: Request) -> RedirectResponse:
    return RedirectResponse(oauth.build_authorization_url(oauth.create_state()))


@router.get("/google/callback")
@limiter.limit("20/minute")
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not oauth.verify_state(state):
        raise UnauthorizedError("Invalid OAuth state")
    profile = await oauth.fetch_google_profile(code)
    user = auth_service.get_or_create_google_user(db, str(profile["email"]), profile.get("name"))
    tokens = auth_service.issue_tokens(db, user)
    # Tokens go in the URL fragment so they are never sent to servers or logged.
    return RedirectResponse(
        f"{settings.FRONTEND_URL}/auth/callback"
        f"#access_token={tokens.access_token}&refresh_token={tokens.refresh_token}"
    )


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("5/minute")
def forgot_password(
    request: Request, data: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    auth_service.send_password_reset(db, data.email)
    return MessageResponse(message="If the email exists, a reset link has been sent")


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit("10/minute")
def reset_password(
    request: Request, data: ResetPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    auth_service.reset_password(db, data.token, data.new_password)
    return MessageResponse(message="Password updated")
