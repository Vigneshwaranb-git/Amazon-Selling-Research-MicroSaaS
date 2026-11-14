"""Authentication endpoints."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import oauth
from app.config import settings
from app.dependencies import get_current_user, get_db
from app.exceptions import ForbiddenError, UnauthorizedError
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.auth import (
    ForgotPasswordRequest,
    MessageResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
    VerifyEmailRequest,
)
from app.services import auth_service
from app.services.auth_service import IssuedTokens

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = f"{settings.API_V1_PREFIX}/auth"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "XMLHttpRequest"


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
    )


def _session_response(response: Response, tokens: IssuedTokens) -> TokenResponse:
    set_refresh_cookie(response, tokens.refresh_token)
    return TokenResponse(access_token=tokens.access_token)


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("10/minute")
def register(
    request: Request,
    data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> User:
    user = auth_service.register_user(db, data)
    auth_service.send_verification(user, background_tasks)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = auth_service.authenticate(db, form.username, form.password)
    return _session_response(response, auth_service.issue_tokens(db, user))


@router.post("/verify-email", response_model=MessageResponse)
@limiter.limit("10/minute")
def verify_email(
    request: Request, data: VerifyEmailRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    auth_service.verify_email(db, data.token)
    return MessageResponse(message="Email verified")


@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit("3/minute")
def resend_verification(
    request: Request,
    data: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> MessageResponse:
    auth_service.resend_verification(db, data.email, background_tasks)
    return MessageResponse(
        message="If the account exists and is not yet verified, a verification email has been sent"
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
def refresh(request: Request, db: Session = Depends(get_db)) -> Response:
    """Rotate the refresh cookie. Needs ``X-Requested-With: XMLHttpRequest`` (CSRF defence)."""
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise ForbiddenError("Missing X-Requested-With header")
    token = request.cookies.get(REFRESH_COOKIE)
    try:
        if not token:
            raise UnauthorizedError("Invalid refresh token")
        tokens = auth_service.refresh_tokens(db, token)
    except UnauthorizedError as exc:
        failure = JSONResponse(
            status_code=401,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers={"WWW-Authenticate": "Bearer"},
        )
        clear_refresh_cookie(failure)
        return failure
    ok = JSONResponse(TokenResponse(access_token=tokens.access_token).model_dump())
    set_refresh_cookie(ok, tokens.refresh_token)
    return ok


@router.post("/logout", response_model=MessageResponse)
@limiter.limit("30/minute")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> MessageResponse:
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        auth_service.revoke_refresh_token(db, token)
    clear_refresh_cookie(response)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
def read_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/me", response_model=UserResponse)
def update_me(
    data: UserUpdate,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Update profile. A password change needs ``current_password``; it revokes all
    refresh tokens and sets a fresh refresh cookie for the current session."""
    updated, tokens = auth_service.update_profile(db, user, data)
    if tokens is not None:
        set_refresh_cookie(response, tokens.refresh_token)
    return updated


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
    # No tokens in the URL: the refresh cookie is set here, the SPA then calls /auth/refresh.
    redirect = RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback")
    set_refresh_cookie(redirect, tokens.refresh_token)
    return redirect


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> MessageResponse:
    auth_service.send_password_reset(db, data.email, background_tasks)
    return MessageResponse(message="If the email exists, a reset link has been sent")


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit("10/minute")
def reset_password(
    request: Request, data: ResetPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    auth_service.reset_password(db, data.token, data.new_password)
    return MessageResponse(message="Password updated")
