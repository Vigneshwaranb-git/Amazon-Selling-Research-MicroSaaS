"""FastAPI application entry point."""

import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler  # noqa: E402,I001
from slowapi.errors import RateLimitExceeded  # noqa: E402,I001

from app.config import settings
from app.exceptions import register_exception_handlers
from app.middleware import BodySizeLimitMiddleware
from app.rate_limit import limiter

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version="1.0.0")

# Added before CORS so CORS wraps it (413 responses keep CORS headers).
app.add_middleware(BodySizeLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

register_exception_handlers(app)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Versioned API router: Phase 2 modules register their routers here.
api_router = APIRouter()
# e.g. api_router.include_router(auth.router)
from app.routers import auth as auth_router  # noqa: E402

api_router.include_router(auth_router.router)
from app.routers import calculator as calculator_router  # noqa: E402
from app.routers import scenarios as scenarios_router  # noqa: E402

api_router.include_router(calculator_router.router)
api_router.include_router(scenarios_router.router)

from app.routers import billing as billing_router  # noqa: E402

api_router.include_router(billing_router.router)

from app.routers import products as products_router  # noqa: E402
from app.routers import tracking_lists as tracking_lists_router  # noqa: E402

api_router.include_router(products_router.router)
api_router.include_router(tracking_lists_router.router)

from app.routers import settings as settings_router  # noqa: E402

api_router.include_router(settings_router.router)

from app.routers import reviews as reviews_router  # noqa: E402

api_router.include_router(reviews_router.router)

from app.routers import admin as admin_router  # noqa: E402
from app.routers import analytics as analytics_router  # noqa: E402

api_router.include_router(admin_router.router)
api_router.include_router(analytics_router.router)

from app.routers import imports as imports_router  # noqa: E402
from app.routers import uploads as uploads_router  # noqa: E402

api_router.include_router(uploads_router.router)
api_router.include_router(imports_router.router)

from app.routers import meta as meta_router  # noqa: E402

api_router.include_router(meta_router.router)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "healthy"}
