"""Email delivery: SMTP backend, console/log backend with an in-memory outbox."""

import logging
import re
import smtplib
import ssl
from collections import deque
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import parseaddr
from typing import Protocol

from fastapi import BackgroundTasks
from starlette.concurrency import run_in_threadpool

from app.config import settings

logger = logging.getLogger(__name__)

_ADDR_RE = re.compile(r"^[^@\s<>\",;]+@[^@\s<>\",;]+\.[^@\s<>\",;]+$")


class EmailError(Exception):
    """Invalid message or delivery failure."""


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    html: str


def _reject_crlf(value: str, field: str) -> None:
    if "\r" in value or "\n" in value or "\0" in value:
        raise EmailError(f"Invalid {field}: control characters not allowed")


def validate_email(message: Email) -> None:
    """Reject header injection and malformed recipients before any backend sees it."""
    _reject_crlf(message.to, "recipient")
    _reject_crlf(message.subject, "subject")
    _reject_crlf(settings.SMTP_FROM, "sender")
    if not _ADDR_RE.match(message.to):
        raise EmailError("Invalid recipient address")


class EmailBackend(Protocol):
    def deliver(self, message: Email) -> None: ...


class ConsoleEmailBackend:
    """Logs metadata only (bodies hold tokens/links) and keeps a bounded outbox."""

    def __init__(self) -> None:
        self.outbox: deque[Email] = deque(maxlen=200)

    def deliver(self, message: Email) -> None:
        self.outbox.append(message)
        logger.info("Email (console backend) to=%s subject=%r", message.to, message.subject)


class SmtpEmailBackend:
    def deliver(self, message: Email) -> None:
        mime = MimeMessage()
        mime["From"] = settings.SMTP_FROM
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text)
        mime.add_alternative(message.html, subtype="html")
        mode = settings.SMTP_TLS.lower()
        try:
            if mode == "ssl":
                client: smtplib.SMTP = smtplib.SMTP_SSL(
                    settings.SMTP_HOST,
                    settings.SMTP_PORT,
                    timeout=15,
                    context=ssl.create_default_context(),
                )
            else:
                client = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
            with client:
                if mode == "starttls":
                    client.starttls(context=ssl.create_default_context())
                if settings.SMTP_USER:
                    client.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                client.send_message(mime, from_addr=parseaddr(settings.SMTP_FROM)[1])
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailError(f"SMTP delivery failed: {type(exc).__name__}") from exc


class EmailService:
    def __init__(self, backend: EmailBackend) -> None:
        self.backend = backend

    @property
    def outbox(self) -> list[Email]:
        box = getattr(self.backend, "outbox", None)
        return list(box) if box is not None else []

    def send(self, message: Email) -> None:
        """Blocking send; raises EmailError."""
        validate_email(message)
        self.backend.deliver(message)

    async def send_async(self, message: Email) -> None:
        await run_in_threadpool(self.send, message)

    def send_safely(self, message: Email) -> bool:
        """Send and swallow/log failures (for background tasks)."""
        try:
            self.send(message)
        except Exception as exc:
            logger.error("Email send failed (subject=%r): %s", message.subject, exc)
            return False
        return True


_service: EmailService | None = None


def get_email_service() -> EmailService:
    global _service
    if _service is None:
        backend: EmailBackend = SmtpEmailBackend() if settings.SMTP_HOST else ConsoleEmailBackend()
        _service = EmailService(backend)
    return _service


def set_email_service(service: EmailService | None) -> None:
    """Override (or reset with None) the process-wide service, e.g. in tests."""
    global _service
    _service = service


def queue_email(background_tasks: BackgroundTasks | None, message: Email) -> None:
    """Send off the request path; with no BackgroundTasks, send inline (safely)."""
    service = get_email_service()
    if background_tasks is not None:
        background_tasks.add_task(service.send_safely, message)
    else:
        service.send_safely(message)
