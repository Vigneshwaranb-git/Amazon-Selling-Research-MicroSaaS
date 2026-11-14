"""Pydantic schemas for the auth module."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str | None = Field(default=None, max_length=100)


class UserUpdate(BaseModel):
    """Profile update. Changing the password requires ``current_password``."""

    full_name: str | None = Field(default=None, max_length=100)
    current_password: str | None = Field(default=None, max_length=72)
    password: str | None = Field(default=None, min_length=8, max_length=72)

    @model_validator(mode="after")
    def _password_needs_current(self) -> "UserUpdate":
        if self.password is not None and not self.current_password:
            raise ValueError("current_password is required to change the password")
        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None = None
    is_active: bool
    is_verified: bool
    is_admin: bool
    oauth_provider: str | None = None
    created_at: datetime


class TokenResponse(BaseModel):
    """Body of login/refresh. The refresh token travels only in an HttpOnly cookie."""

    access_token: str
    token_type: str = "bearer"


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=2048)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=72)


class MessageResponse(BaseModel):
    message: str
