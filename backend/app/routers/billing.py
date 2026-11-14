"""Billing endpoints (Dodo Payments)."""

import logging

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.exceptions import AppException
from app.models.user import User
from app.schemas.billing import (
    CheckoutRequest,
    CheckoutResponse,
    SubscriptionResponse,
    WebhookAck,
)
from app.services import billing_service
from app.services.dodo_client import (
    DodoClient,
    HttpxDodoClient,
    InvalidSignatureError,
    verify_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


def get_dodo_client() -> DodoClient:
    return HttpxDodoClient(settings.DODO_API_KEY, settings.DODO_BASE_URL)


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    client: DodoClient = Depends(get_dodo_client),
) -> CheckoutResponse:
    url = await billing_service.create_checkout(client, current_user, body.plan)
    return CheckoutResponse(checkout_url=url)


@router.post("/webhook", response_model=WebhookAck)
async def webhook(
    request: Request,
    db: Session = Depends(get_db),
    webhook_id: str | None = Header(default=None, alias="webhook-id"),
    webhook_timestamp: str | None = Header(default=None, alias="webhook-timestamp"),
    webhook_signature: str | None = Header(default=None, alias="webhook-signature"),
) -> WebhookAck:
    raw = await request.body()
    try:
        verify_webhook(
            secret=settings.DODO_WEBHOOK_SECRET,
            webhook_id=webhook_id,
            timestamp=webhook_timestamp,
            signature_header=webhook_signature,
            body=raw,
        )
    except InvalidSignatureError as exc:
        logger.warning("Rejected Dodo webhook: %s", exc)
        raise AppException("Invalid webhook signature", "INVALID_SIGNATURE", 400) from exc
    processed = billing_service.process_webhook(db, raw, webhook_id)
    return WebhookAck(processed=processed)


@router.get("/subscription", response_model=SubscriptionResponse)
async def my_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubscriptionResponse:
    sub = billing_service.get_subscription(db, current_user.id)
    if sub is None:
        return SubscriptionResponse(plan="free", status="inactive")
    return SubscriptionResponse.model_validate(sub)
