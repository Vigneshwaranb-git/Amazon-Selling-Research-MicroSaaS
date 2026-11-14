"""Application settings loaded from environment variables / .env."""

import logging
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # External providers (empty key -> mock provider)
    AMAZON_DATA_API_KEY: str = ""
    LLM_API_KEY: str = ""

    # Frontend / CORS
    VITE_API_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
