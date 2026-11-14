"""Background worker: snapshot job then BSR alerts every WORKER_INTERVAL_MINUTES.

Run with ``python -m app.worker`` (loop) or ``python -m app.worker --once``.
"""

import argparse
import asyncio
import logging
import signal
import threading

from app.config import settings
from app.database import SessionLocal
from app.services.alert_service import run_bsr_alerts
from app.services.email_service import get_email_service
from app.services.providers import get_product_data_provider
from app.services.snapshot_job import run_snapshot_job

logger = logging.getLogger(__name__)


def _alerts_job() -> int:
    with SessionLocal() as db:
        return run_bsr_alerts(db, get_email_service())


async def run_cycle() -> None:
    """One worker pass. Failures are logged so the loop keeps running."""
    try:
        with SessionLocal() as db:
            await run_snapshot_job(db, get_product_data_provider())
    except Exception:
        logger.exception("Snapshot job failed")
    try:
        await asyncio.to_thread(_alerts_job)
    except Exception:
        logger.exception("Alert job failed")


async def run_worker(once: bool = False, stop: asyncio.Event | None = None) -> None:
    stop = stop or asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop(*_: object) -> None:
        logger.info("Shutdown signal received")
        loop.call_soon_threadsafe(stop.set)

    previous: dict[signal.Signals, object] = {}
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                previous[sig] = signal.signal(sig, request_stop)
            except (ValueError, OSError):  # pragma: no cover
                pass

    interval = max(1, settings.WORKER_INTERVAL_MINUTES) * 60
    logger.info("Worker started (once=%s, interval=%ss)", once, interval)
    try:
        while not stop.is_set():
            await run_cycle()
            if once:
                break
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TimeoutError:
                pass
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)  # type: ignore[arg-type]
    logger.info("Worker stopped")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="AmzScoutIQ background worker")
    parser.add_argument("--once", action="store_true", help="run one cycle and exit")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_worker(once=args.once))


if __name__ == "__main__":
    main()
