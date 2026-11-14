"""Billing tests: webhook signature verification, idempotency, checkout, subscription."""

import json
import time
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.dependencies import get_current_user
from app.main import app
from app.models import Base, ProcessedWebhook, Subscription, User
from app.routers.billing import get_dodo_client
from app.services.dodo_client import DodoError, compute_signature, verify_webhook

SECRET = "test-webhook-secret"


class FakeDodo:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def create_checkout(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.fail:
            raise DodoError("boom")
        return {"checkout_url": "https://checkout.example/abc", "session_id": "cks_1"}


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    session.add(User(id=1, email="a@example.com"))
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def fake() -> FakeDodo:
    return FakeDodo()


@pytest.fixture()
def client(
    db: Session, fake: FakeDodo, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    from app.database import get_db

    monkeypatch.setattr(settings, "DODO_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(settings, "DODO_PRODUCT_ID_PRO", "prod_pro")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, 1)
    app.dependency_overrides[get_dodo_client] = lambda: fake
    yield TestClient(app)
    app.dependency_overrides.clear()


def _event(
    kind: str = "subscription.active",
    user_id: int = 1,
    sub_id: str = "sub_1",
    ts: str | None = None,
) -> bytes:
    return json.dumps(
        {
            "type": kind,
            **({"timestamp": ts} if ts else {}),
            "data": {
                "subscription_id": sub_id,
                "customer": {"customer_id": "cus_1"},
                "metadata": {"user_id": str(user_id), "plan": "pro"},
                "next_billing_date": "2030-01-01T00:00:00Z",
            },
        }
    ).encode()


def _headers(
    body: bytes, *, secret: str = SECRET, msg_id: str = "msg_1", ts: int | None = None
) -> dict[str, str]:
    stamp = str(int(time.time()) if ts is None else ts)
    sig = compute_signature(secret, msg_id, stamp, body)
    return {
        "webhook-id": msg_id,
        "webhook-timestamp": stamp,
        "webhook-signature": f"v1,{sig}",
        "content-type": "application/json",
    }


def _post(client: TestClient, body: bytes, headers: dict[str, str]) -> Any:
    return client.post("/api/v1/billing/webhook", content=body, headers=headers)


def test_valid_webhook_activates_subscription(client: TestClient, db: Session) -> None:
    body = _event()
    r = _post(client, body, _headers(body))
    assert r.status_code == 200 and r.json()["processed"] is True
    sub = db.query(Subscription).one()
    assert (sub.status, sub.plan, sub.dodo_subscription_id) == ("active", "pro", "sub_1")
    assert sub.dodo_customer_id == "cus_1"
    assert sub.current_period_end is not None


def test_invalid_signature_rejected(client: TestClient, db: Session) -> None:
    body = _event()
    r = _post(client, body, _headers(body, secret="wrong"))
    assert r.status_code == 400
    assert db.query(Subscription).count() == 0


def test_tampered_body_rejected(client: TestClient, db: Session) -> None:
    body = _event()
    headers = _headers(body)
    r = _post(client, _event("subscription.cancelled"), headers)
    assert r.status_code == 400
    assert db.query(Subscription).count() == 0


@pytest.mark.parametrize("missing", ["webhook-id", "webhook-timestamp", "webhook-signature"])
def test_missing_headers_rejected(client: TestClient, missing: str) -> None:
    body = _event()
    headers = _headers(body)
    del headers[missing]
    assert _post(client, body, headers).status_code == 400


def test_stale_timestamp_rejected(client: TestClient, db: Session) -> None:
    body = _event()
    r = _post(client, body, _headers(body, ts=int(time.time()) - 3600))
    assert r.status_code == 400
    assert db.query(Subscription).count() == 0


def test_unconfigured_secret_rejects(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DODO_WEBHOOK_SECRET", "")
    body = _event()
    assert _post(client, body, _headers(body, secret="")).status_code == 400


def test_replayed_webhook_is_idempotent(client: TestClient, db: Session) -> None:
    body = _event()
    headers = _headers(body)
    for _ in range(3):
        assert _post(client, body, headers).status_code == 200
    assert db.query(Subscription).count() == 1
    assert db.query(Subscription).one().status == "active"


def test_cancel_then_replayed_cancel(client: TestClient, db: Session) -> None:
    body = _event()
    _post(client, body, _headers(body))
    cancel = _event("subscription.cancelled")
    h = _headers(cancel, msg_id="msg_2")
    _post(client, cancel, h)
    _post(client, cancel, h)
    subs = db.query(Subscription).all()
    assert len(subs) == 1 and subs[0].status == "cancelled"


def test_unknown_event_ack_not_processed(client: TestClient, db: Session) -> None:
    body = _event("payment.something_else")
    r = _post(client, body, _headers(body))
    assert r.status_code == 200 and r.json()["processed"] is False
    assert db.query(Subscription).count() == 0


def test_unknown_user_not_processed(client: TestClient, db: Session) -> None:
    body = _event(user_id=999)
    r = _post(client, body, _headers(body))
    assert r.status_code == 200 and r.json()["processed"] is False
    assert db.query(Subscription).count() == 0


def test_multiple_signatures_header_accepts_any_valid() -> None:
    body = b"{}"
    good = compute_signature(SECRET, "m", "100", body)
    verify_webhook(
        secret=SECRET,
        webhook_id="m",
        timestamp="100",
        signature_header=f"v1,AAAA v1,{good}",
        body=body,
        now=100,
    )


def test_checkout_returns_url_and_does_not_change_state(
    client: TestClient, db: Session, fake: FakeDodo
) -> None:
    r = client.post("/api/v1/billing/checkout", json={"plan": "pro"})
    assert r.status_code == 200
    assert r.json() == {"checkout_url": "https://checkout.example/abc"}
    assert fake.calls[0]["product_id"] == "prod_pro"
    assert fake.calls[0]["metadata"] == {"user_id": "1", "plan": "pro"}
    assert db.query(Subscription).count() == 0


def test_checkout_rejects_unknown_plan_and_client_status(client: TestClient) -> None:
    assert client.post("/api/v1/billing/checkout", json={"plan": "free"}).status_code == 422


def test_checkout_unconfigured_plan(client: TestClient) -> None:
    r = client.post("/api/v1/billing/checkout", json={"plan": "business"})
    assert r.status_code == 503


def test_checkout_provider_failure(client: TestClient, fake: FakeDodo) -> None:
    fake.fail = True
    assert client.post("/api/v1/billing/checkout", json={"plan": "pro"}).status_code == 502


def test_subscription_defaults_to_free(client: TestClient) -> None:
    r = client.get("/api/v1/billing/subscription")
    assert r.status_code == 200
    assert r.json()["plan"] == "free" and r.json()["status"] == "inactive"


def test_subscription_reflects_webhook(client: TestClient) -> None:
    body = _event()
    _post(client, body, _headers(body))
    r = client.get("/api/v1/billing/subscription")
    assert r.json()["plan"] == "pro" and r.json()["status"] == "active"


def test_replayed_webhook_id_returns_processed_false(client: TestClient, db: Session) -> None:
    body = _event()
    headers = _headers(body)
    assert _post(client, body, headers).json()["processed"] is True
    assert _post(client, body, headers).json()["processed"] is False
    assert db.query(ProcessedWebhook).count() == 1


def test_replayed_old_event_does_not_overwrite_newer_state(client: TestClient, db: Session) -> None:
    active = _event("subscription.active")
    _post(client, active, _headers(active, msg_id="m1"))
    cancel = _event("subscription.cancelled")
    _post(client, cancel, _headers(cancel, msg_id="m2"))
    # same old event re-sent with a fresh webhook id is only blocked by timestamps (below);
    # the exact same id is blocked by the dedupe table
    r = _post(client, active, _headers(active, msg_id="m1"))
    assert r.json()["processed"] is False
    assert db.query(Subscription).one().status == "cancelled"


def test_out_of_order_event_ignored_by_timestamp(client: TestClient, db: Session) -> None:
    new = _event("subscription.cancelled", ts="2030-01-02T00:00:00Z")
    old = _event("subscription.active", ts="2030-01-01T00:00:00Z")
    assert _post(client, new, _headers(new, msg_id="m1")).json()["processed"] is True
    r = _post(client, old, _headers(old, msg_id="m2"))
    assert r.status_code == 200 and r.json()["processed"] is False
    assert db.query(Subscription).one().status == "cancelled"
    newer = _event("subscription.active", ts="2030-01-03T00:00:00Z")
    assert _post(client, newer, _headers(newer, msg_id="m3")).json()["processed"] is True
    assert db.query(Subscription).one().status == "active"


def test_second_subscription_gets_own_row(client: TestClient, db: Session) -> None:
    first = _event("subscription.cancelled", sub_id="sub_1")
    second = _event("subscription.active", sub_id="sub_2")
    _post(client, first, _headers(first, msg_id="m1"))
    _post(client, second, _headers(second, msg_id="m2"))
    rows = {s.dodo_subscription_id: s.status for s in db.query(Subscription).all()}
    assert rows == {"sub_1": "cancelled", "sub_2": "active"}
    assert client.get("/api/v1/billing/subscription").json()["status"] == "active"


def test_checkout_omits_billing_country_by_default_and_passes_when_set(
    client: TestClient, fake: FakeDodo, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post("/api/v1/billing/checkout", json={"plan": "pro"})
    assert fake.calls[0]["billing_country"] is None
    monkeypatch.setattr(settings, "DODO_DEFAULT_BILLING_COUNTRY", "IN")
    client.post("/api/v1/billing/checkout", json={"plan": "pro"})
    assert fake.calls[1]["billing_country"] == "IN"
