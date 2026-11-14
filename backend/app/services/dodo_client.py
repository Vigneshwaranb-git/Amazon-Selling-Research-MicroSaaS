"""Thin Dodo Payments client and webhook signature verification.

Verified against Dodo docs (fetched 2026-11-14):
  * Checkout Sessions: ``POST {base}/checkouts`` with required ``product_cart``
    (``[{product_id, quantity}]``); optional ``customer`` (``{email, name}``),
    ``billing_address`` (``country`` required if present, ISO alpha-2), ``return_url``,
    ``metadata``. Response: ``session_id`` and ``checkout_url`` (nullable).
    https://docs.dodopayments.com/api-reference/checkout-sessions/create
  * Webhooks follow Standard Webhooks (``webhook-id``/``-timestamp``/``-signature``,
    signed ``"{id}.{timestamp}.{body}"``, ``whsec_`` base64 secret, 5 min tolerance).
  * Base URLs: test.dodopayments.com / live.dodopayments.com, Bearer API key.

UNCONFIRMED: whether checkout ``metadata`` propagates onto subscription webhook
payloads (the user_id fallback in billing_service depends on it); verify in test mode.
"""

import base64
import binascii
import hashlib
import hmac
import logging
import time
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

TIMESTAMP_TOLERANCE_SECONDS = 300


class DodoError(Exception):
    """Dodo API call failed."""


class InvalidSignatureError(Exception):
    """Webhook signature/timestamp verification failed."""


class DodoClient(Protocol):
    async def create_checkout(
        self,
        *,
        product_id: str,
        email: str,
        name: str | None,
        return_url: str,
        metadata: dict[str, str],
        billing_country: str | None = None,
    ) -> dict[str, Any]: ...


class HttpxDodoClient:
    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def create_checkout(
        self,
        *,
        product_id: str,
        email: str,
        name: str | None,
        return_url: str,
        metadata: dict[str, str],
        billing_country: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "product_cart": [{"product_id": product_id, "quantity": 1}],
            "customer": {"email": email, "name": name or email},
            "return_url": return_url,
            "metadata": metadata,
        }
        if billing_country:
            payload["billing_address"] = {"country": billing_country}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._base_url}/checkouts",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Dodo checkout creation failed: %s", type(exc).__name__)
            raise DodoError("Payment provider error") from exc
        return data


def _secret_bytes(secret: str) -> bytes:
    if secret.startswith("whsec_"):
        try:
            return base64.b64decode(secret[len("whsec_") :], validate=True)
        except (binascii.Error, ValueError):
            pass
    return secret.encode()


def compute_signature(secret: str, webhook_id: str, timestamp: str, body: bytes) -> str:
    signed = f"{webhook_id}.{timestamp}.".encode() + body
    digest = hmac.new(_secret_bytes(secret), signed, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def verify_webhook(
    *,
    secret: str,
    webhook_id: str | None,
    timestamp: str | None,
    signature_header: str | None,
    body: bytes,
    now: float | None = None,
) -> None:
    """Raise InvalidSignatureError unless the webhook is authentic and fresh."""
    if not secret:
        raise InvalidSignatureError("Webhook secret not configured")
    if not webhook_id or not timestamp or not signature_header:
        raise InvalidSignatureError("Missing signature headers")
    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise InvalidSignatureError("Invalid timestamp") from exc
    current = time.time() if now is None else now
    if abs(current - ts) > TIMESTAMP_TOLERANCE_SECONDS:
        raise InvalidSignatureError("Timestamp outside tolerance")

    expected = compute_signature(secret, webhook_id, timestamp, body).encode()
    valid = False
    for part in signature_header.split():
        version, _, sig = part.partition(",")
        # compare every candidate (no early exit) with constant-time comparison
        if hmac.compare_digest(sig.encode(), expected) and version == "v1":
            valid = True
    if not valid:
        raise InvalidSignatureError("Signature mismatch")
