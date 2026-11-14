"""Model registry: importing this package registers all tables on Base.metadata."""

from app.models.alert_state import AlertState
from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.bsr_snapshot import BsrSnapshot
from app.models.cost_model import CostModel
from app.models.processed_webhook import ProcessedWebhook
from app.models.product import Product
from app.models.refresh_token import RefreshToken
from app.models.review_log import ReviewLog
from app.models.review_summary import ReviewSummary
from app.models.subscription import Subscription
from app.models.tracking_list import TrackedProduct, TrackingList
from app.models.user import User

__all__ = [
    "AlertState",
    "Base",
    "BsrSnapshot",
    "CostModel",
    "ProcessedWebhook",
    "Product",
    "RefreshToken",
    "ReviewLog",
    "ReviewSummary",
    "SoftDeleteMixin",
    "Subscription",
    "TimestampMixin",
    "TrackedProduct",
    "TrackingList",
    "User",
]
