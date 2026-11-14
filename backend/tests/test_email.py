"""Email service, templates, SMTP backend and auth wiring."""

import asyncio
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.services import email_service as es
from app.services.email_service import Email, EmailError, EmailService
from app.services.email_templates import (
    BsrAlertItem,
    bsr_alert_email,
    password_reset_email,
    welcome_email,
)
from tests._auth_helpers import register_verified
from tests._mail import mail  # noqa: F401

PREFIX = "/api/v1/auth"


def test_welcome_escapes_html() -> None:
    msg = welcome_email("a@example.com", "<script>alert(1)</script>")
    assert "<script>" not in msg.html
    assert "&lt;script&gt;" in msg.html
    assert msg.subject.startswith("Welcome")


def test_reset_template_builds_url() -> None:
    msg = password_reset_email("a@example.com", "abc.def&x=1")
    link = re.search(r"https?://\S+", msg.text)
    assert link is not None
    url = urlparse(link.group(0))
    assert url.path == "/reset-password"
    assert parse_qs(url.query)["token"] == ["abc.def&x=1"]
    assert "&amp;" not in msg.text


def test_alert_template_escapes() -> None:
    item = BsrAlertItem("B0<b>", '<img src=x onerror="1">', 100, 50, 50.0)
    msg = bsr_alert_email("a@example.com", [item], 20)
    assert "<img" not in msg.html
    assert "&lt;img" in msg.html
    assert "50.0%" in msg.text


@pytest.mark.parametrize(
    "msg",
    [
        Email("a@example.com\r\nBcc: x@evil.com", "s", "t", "h"),
        Email("a@example.com", "Hi\nBcc: x@evil.com", "t", "h"),
        Email("not-an-email", "s", "t", "h"),
        Email("a@example.com, b@example.com", "s", "t", "h"),
    ],
)
def test_rejects_injection_and_bad_recipient(mail: EmailService, msg: Email) -> None:  # noqa: F811
    with pytest.raises(EmailError):
        mail.send(msg)
    assert mail.outbox == []
    assert mail.send_safely(msg) is False


def test_send_async_uses_outbox(mail: EmailService) -> None:  # noqa: F811
    asyncio.run(mail.send_async(Email("a@example.com", "s", "t", "h")))
    assert [m.to for m in mail.outbox] == ["a@example.com"]


def test_backend_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    es.set_email_service(None)
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    assert isinstance(es.get_email_service().backend, es.ConsoleEmailBackend)
    es.set_email_service(None)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    assert isinstance(es.get_email_service().backend, es.SmtpEmailBackend)
    es.set_email_service(None)


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, host: str, port: int, **kwargs: Any) -> None:
        self.calls: list[str] = []
        self.sent: Any = None
        FakeSMTP.instances.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *a: object) -> None:
        return None

    def starttls(self, **kwargs: Any) -> None:
        self.calls.append("starttls")

    def login(self, user: str, pw: str) -> None:
        self.calls.append("login")

    def send_message(self, msg: Any, from_addr: str) -> None:
        self.sent = (msg, from_addr)


def test_smtp_backend_starttls(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSMTP.instances = []
    monkeypatch.setattr(es.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_USER", "u")
    monkeypatch.setattr(settings, "SMTP_TLS", "starttls")
    EmailService(es.SmtpEmailBackend()).send(Email("a@example.com", "Subj", "plain", "<p>h</p>"))
    inst = FakeSMTP.instances[0]
    assert inst.calls == ["starttls", "login"]
    msg, from_addr = inst.sent
    assert msg["To"] == "a@example.com"
    assert from_addr == "no-reply@amzscoutiq.local"
    assert msg.is_multipart()


def test_smtp_failure_becomes_email_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: Any, **k: Any) -> None:
        raise OSError("down")

    monkeypatch.setattr(es.smtplib, "SMTP", boom)
    monkeypatch.setattr(settings, "SMTP_TLS", "none")
    with pytest.raises(EmailError):
        EmailService(es.SmtpEmailBackend()).send(Email("a@example.com", "s", "t", "h"))


def test_register_sends_welcome_and_verification(client: TestClient, mail: EmailService) -> None:  # noqa: F811
    r = client.post(
        f"{PREFIX}/register",
        json={"email": "New@Example.com", "password": "StrongPass123", "full_name": "Neo"},
    )
    assert r.status_code == 201
    assert [m.to for m in mail.outbox] == ["new@example.com"]
    assert "Neo" in mail.outbox[0].html
    assert "/verify-email?token=" in mail.outbox[0].text


def test_register_survives_email_failure(
    client: TestClient,
    mail: EmailService,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(message: Email) -> None:
        raise EmailError("down")

    monkeypatch.setattr(mail.backend, "deliver", boom)
    r = client.post(
        f"{PREFIX}/register", json={"email": "x@example.com", "password": "StrongPass123"}
    )
    assert r.status_code == 201


def test_forgot_password_sends_email_uniform_response(
    client: TestClient,
    db_session: Session,
    mail: EmailService,  # noqa: F811
    caplog: pytest.LogCaptureFixture,
) -> None:
    register_verified(client, "u@example.com", "StrongPass123")
    mail.backend.outbox.clear()  # type: ignore[attr-defined]
    with caplog.at_level(logging.DEBUG):
        unknown = client.post(f"{PREFIX}/forgot-password", json={"email": "ghost@example.com"})
        known = client.post(f"{PREFIX}/forgot-password", json={"email": "u@example.com"})
    assert unknown.status_code == known.status_code == 200
    assert unknown.json() == known.json()
    assert [m.to for m in mail.outbox] == ["u@example.com"]
    link = re.search(r"https?://\S+", mail.outbox[0].text)
    assert link is not None
    token = parse_qs(urlparse(link.group(0)).query)["token"][0]
    assert token not in caplog.text
    r = client.post(
        f"{PREFIX}/reset-password", json={"token": token, "new_password": "BrandNewPass123"}
    )
    assert r.status_code == 200
    assert db_session.query(User).count() == 1
