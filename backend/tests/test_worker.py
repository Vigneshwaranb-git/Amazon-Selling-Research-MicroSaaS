"""Background worker: --once, failure isolation and graceful stop."""

import asyncio
from collections.abc import Awaitable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app import worker
from app.config import settings
from app.models.bsr_snapshot import BsrSnapshot
from app.models.product import Product
from app.models.tracking_list import TrackedProduct, TrackingList
from app.models.user import User
from app.services.email_service import EmailService
from tests._mail import mail  # noqa: F401


def test_once_runs_snapshot_then_alerts(
    db_session: Session,
    mail: EmailService,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @contextmanager
    def fake_session() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(worker, "SessionLocal", fake_session)
    user = User(email="w@example.com")
    product = Product(asin="B0MOCK0001", title="Seed")
    db_session.add_all([user, product])
    db_session.flush()
    lst = TrackingList(user_id=user.id, name="L")
    db_session.add(lst)
    db_session.flush()
    db_session.add(TrackedProduct(tracking_list_id=lst.id, product_id=product.id))
    # Previous snapshot far from whatever the mock provider reports -> large change.
    db_session.add(
        BsrSnapshot(
            product_id=product.id, bsr=10**9, captured_at=datetime.now(UTC) - timedelta(days=1)
        )
    )
    db_session.commit()

    worker.main(["--once"])

    assert db_session.query(BsrSnapshot).filter_by(product_id=product.id).count() >= 2
    assert [m.to for m in mail.outbox] == ["w@example.com"]


def test_run_cycle_survives_failures(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def bad_snapshot(*a: object, **k: object) -> int:
        raise RuntimeError("boom")

    def bad_alerts() -> int:
        raise RuntimeError("boom2")

    @contextmanager
    def fake_session() -> Iterator[None]:
        yield None

    monkeypatch.setattr(worker, "SessionLocal", fake_session)
    monkeypatch.setattr(worker, "run_snapshot_job", bad_snapshot)
    monkeypatch.setattr(worker, "_alerts_job", bad_alerts)
    asyncio.run(worker.run_cycle())
    assert "Snapshot job failed" in caplog.text
    assert "Alert job failed" in caplog.text


def test_loop_stops_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    stop: asyncio.Event

    async def fake_cycle() -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            stop.set()

    monkeypatch.setattr(worker, "run_cycle", fake_cycle)
    monkeypatch.setattr(settings, "WORKER_INTERVAL_MINUTES", 1)

    async def fast_wait(aw: Awaitable[object], timeout: float) -> None:
        close = getattr(aw, "close", None)
        if close is not None:
            close()  # discard the un-awaited stop.wait() coroutine
        if not stop.is_set():
            raise TimeoutError

    monkeypatch.setattr(worker.asyncio, "wait_for", fast_wait)

    async def go() -> None:
        nonlocal stop
        stop = asyncio.Event()
        await worker.run_worker(stop=stop)

    asyncio.run(go())
    assert calls == 2
