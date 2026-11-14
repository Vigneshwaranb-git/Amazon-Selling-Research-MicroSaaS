"""BSR alerts, notification settings endpoint."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user
from app.main import app
from app.models.alert_state import AlertState
from app.models.bsr_snapshot import BsrSnapshot
from app.models.product import Product
from app.models.tracking_list import TrackedProduct, TrackingList
from app.models.user import User
from app.services.alert_service import run_bsr_alerts
from app.services.email_service import EmailService
from tests._mail import mail  # noqa: F401

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _user(db: Session, email: str, **kw: object) -> User:
    u = User(email=email, **kw)
    db.add(u)
    db.flush()
    return u


def _track(db: Session, user: User, asin: str, bsrs: list[int | None], title: str = "Prod") -> int:
    product = db.query(Product).filter_by(asin=asin).one_or_none()
    if product is None:
        product = Product(asin=asin, title=title)
        db.add(product)
        db.flush()
        for i, b in enumerate(bsrs):
            db.add(BsrSnapshot(product_id=product.id, bsr=b, captured_at=NOW + timedelta(days=i)))
    lst = db.query(TrackingList).filter_by(user_id=user.id).first()
    if lst is None:
        lst = TrackingList(user_id=user.id, name="L")
        db.add(lst)
        db.flush()
    db.add(TrackedProduct(tracking_list_id=lst.id, product_id=product.id))
    db.commit()
    return product.id


def test_digest_threshold_and_dedupe(db_session: Session, mail: EmailService) -> None:  # noqa: F811
    u = _user(db_session, "a@example.com")
    _track(db_session, u, "B000000001", [1000, 700], "Big mover")  # 30%
    _track(db_session, u, "B000000002", [1000, 1100], "Small")  # 10%
    _track(db_session, u, "B000000003", [1000, 1250], "Dropper")  # 25%
    _track(db_session, u, "B000000004", [None, 500], "NoData")
    _track(db_session, u, "B000000005", [900], "Single")
    assert run_bsr_alerts(db_session, mail) == 1
    assert len(mail.outbox) == 1  # one digest, not per product
    m = mail.outbox[0]
    assert "Big mover" in m.html and "Dropper" in m.html
    assert "Small" not in m.html and "NoData" not in m.html and "Single" not in m.html
    assert m.text.index("Big mover") < m.text.index("Dropper")  # sorted by magnitude
    # same change is not re-sent
    assert run_bsr_alerts(db_session, mail) == 0
    assert len(mail.outbox) == 1
    # a new snapshot with a fresh big change alerts again (only that product)
    pid = db_session.query(Product).filter_by(asin="B000000001").one().id
    db_session.add(BsrSnapshot(product_id=pid, bsr=300, captured_at=NOW + timedelta(days=9)))
    db_session.commit()
    assert run_bsr_alerts(db_session, mail) == 1
    assert "Big mover" in mail.outbox[1].html and "Dropper" not in mail.outbox[1].html
    assert db_session.query(AlertState).count() == 2


def test_opt_out_and_inactive(db_session: Session, mail: EmailService) -> None:  # noqa: F811
    off = _user(db_session, "off@example.com", notify_bsr_alerts=False)
    inactive = _user(db_session, "gone@example.com", is_active=False)
    on = _user(db_session, "on@example.com")
    for u in (off, inactive, on):
        _track(db_session, u, "B000000009", [1000, 500])
    assert run_bsr_alerts(db_session, mail) == 1
    assert [m.to for m in mail.outbox] == ["on@example.com"]


def test_threshold_setting(
    db_session: Session,
    mail: EmailService,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    u = _user(db_session, "a@example.com")
    _track(db_session, u, "B000000001", [1000, 1100])
    assert run_bsr_alerts(db_session, mail) == 0
    monkeypatch.setattr(settings, "ALERT_BSR_CHANGE_PCT", 10.0)
    assert run_bsr_alerts(db_session, mail) == 1


def test_send_failure_retries_next_run(
    db_session: Session,
    mail: EmailService,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    u = _user(db_session, "a@example.com")
    _track(db_session, u, "B000000001", [1000, 500])
    good = mail.backend.deliver

    def boom(message: object) -> None:
        raise RuntimeError("smtp down")

    monkeypatch.setattr(mail.backend, "deliver", boom)
    assert run_bsr_alerts(db_session, mail) == 0
    assert db_session.query(AlertState).count() == 0
    monkeypatch.setattr(mail.backend, "deliver", good)
    assert run_bsr_alerts(db_session, mail) == 1


def test_notifications_endpoint(client: TestClient, db_session: Session) -> None:
    assert client.get("/api/v1/settings/notifications").status_code == 401
    u = _user(db_session, "a@example.com")
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: u
    try:
        r = client.get("/api/v1/settings/notifications")
        assert r.json() == {"bsr_alerts_enabled": True}
        r = client.put("/api/v1/settings/notifications", json={"bsr_alerts_enabled": False})
        assert r.status_code == 200 and r.json() == {"bsr_alerts_enabled": False}
        db_session.refresh(u)
        assert u.notify_bsr_alerts is False
        assert client.get("/api/v1/settings/notifications").json() == {"bsr_alerts_enabled": False}
        assert client.put("/api/v1/settings/notifications", json={}).status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)
