"""Application settings loaded from environment variables / .env."""

import logging
from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    APP_NAME: str = "AmzScoutIQ"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Database / auth (required, no defaults for secrets)
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Refresh-token cookie: Secure flag. Keep True in production (HTTPS); set false only for
    # plain-http local development (http://localhost).
    COOKIE_SECURE: bool = True

    # Emails (case-insensitive) that are promoted to admin on register/login. Comma-separated.
    ADMIN_EMAILS: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Dodo Payments
    DODO_API_KEY: str = ""
    DODO_WEBHOOK_SECRET: str = ""
    DODO_BASE_URL: str = "https://test.dodopayments.com"  # live: https://live.dodopayments.com
    DODO_PRODUCT_ID_PRO: str = ""
    DODO_PRODUCT_ID_BUSINESS: str = ""
    # ISO 3166-1 alpha-2; None -> omit billing_address so Dodo collects it at checkout
    DODO_DEFAULT_BILLING_COUNTRY: str | None = None

    # Email
    SMTP_HOST: str = ""
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_PORT: int = 587
    SMTP_FROM: str = "AmzScoutIQ <no-reply@amzscoutiq.local>"
    SMTP_TLS: str = "starttls"  # starttls | ssl | none

    # Alerts / background worker
    ALERT_BSR_CHANGE_PCT: float = 20.0
    WORKER_INTERVAL_MINUTES: int = 360

    # External providers (empty key -> mock provider)
    AMAZON_DATA_API_KEY: str = ""
    LLM_API_KEY: str = ""

    # Open-dataset data provider (opt-in; default mock). Build the file first:
    #   cd backend && python -m app.data.import_amazon_2023 --category Appliances
    # DATA_PROVIDER=dataset with a missing/corrupt file is an error (never a silent mock).
    DATA_PROVIDER: Literal["mock", "dataset"] = "mock"
    DATASET_PATH: str = "data/amazon_reviews_2023.sqlite"
    # mock | lexicon (free rule-based sentiment/pain points; recommended with DATA_PROVIDER=dataset)
    LLM_PROVIDER: Literal["mock", "lexicon"] = "mock"

    # Local file storage (avatars); mount a volume here in production
    UPLOAD_DIR: str = "uploads"

    # Frontend / CORS
    VITE_API_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def _no_wildcard_origin(cls, value: list[str]) -> list[str]:
        # Credentialed CORS (refresh cookie) must never be opened to every origin.
        if any(origin.strip() == "*" for origin in value):
            raise ValueError("ALLOWED_ORIGINS must list explicit origins, not '*'")
        return value

    @field_validator("ADMIN_EMAILS", mode="before")
    @classmethod
    def _split_admin_emails(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                import json

                value = json.loads(value)
            else:
                value = value.split(",")
        if isinstance(value, list):
            return [str(v).strip().lower() for v in value if str(v).strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
