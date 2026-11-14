"""SmtpEmailBackend against a real local aiosmtpd server (plain, STARTTLS, SSL, auth, failures)."""

import datetime as dt
import email
import email.policy
import logging
import socket
import ssl
from collections.abc import Iterator
from email.message import EmailMessage as MimeMessage
from pathlib import Path
from typing import Any

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP as SmtpServer
from aiosmtpd.smtp import AuthResult, Envelope, LoginPassword, Session
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.config import settings
from app.services import email_service as es
from app.services.email_service import Email, EmailError, EmailService

MSG = Email("rcpt@example.com", "Hello subject", "plain body", "<p>html body</p>")


class Collector:
    def __init__(self) -> None:
        self.messages: list[tuple[str, list[str], MimeMessage]] = []

    async def handle_DATA(self, server: SmtpServer, session: Session, envelope: Envelope) -> str:
        parsed = email.message_from_bytes(envelope.content or b"", policy=email.policy.default)
        self.messages.append(
            (str(envelope.mail_from), list(envelope.rcpt_tos), parsed)  # type: ignore[arg-type]
        )
        return "250 OK"


def _authenticator(
    server: SmtpServer, session: Session, envelope: Envelope, mechanism: str, data: Any
) -> AuthResult:
    ok = isinstance(data, LoginPassword) and (data.login, data.password) == (b"user", b"s3cret")
    return AuthResult(success=ok, handled=ok)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _server_ctx(cert: tuple[Path, Path]) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert[0]), str(cert[1]))
    return ctx


@pytest.fixture(scope="module")
def cert(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = dt.datetime.now(dt.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    d = tmp_path_factory.mktemp("tls")
    cert_path, key_path = d / "cert.pem", d / "key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


@pytest.fixture
def trust_cert(monkeypatch: pytest.MonkeyPatch, cert: tuple[Path, Path]) -> None:
    """Make the backend's default TLS context trust only our self-signed cert."""

    original = ssl.create_default_context

    def _ctx(*args: Any, **kwargs: Any) -> ssl.SSLContext:
        if args or kwargs:  # aiosmtpd's own readiness probe (ssl module is shared)
            return original(*args, **kwargs)
        return original(cafile=str(cert[0]))

    monkeypatch.setattr(es.ssl, "create_default_context", _ctx)


def _configure(
    monkeypatch: pytest.MonkeyPatch, port: int, tls: str, user: str = "", password: str = ""
) -> None:
    monkeypatch.setattr(settings, "SMTP_HOST", "localhost")
    monkeypatch.setattr(settings, "SMTP_PORT", port)
    monkeypatch.setattr(settings, "SMTP_TLS", tls)
    monkeypatch.setattr(settings, "SMTP_USER", user)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", password)
    monkeypatch.setattr(settings, "SMTP_FROM", "AmzScoutIQ <no-reply@example.com>")


@pytest.fixture
def server() -> Iterator[tuple[Collector, int]]:
    handler = Collector()
    port = _free_port()
    controller = Controller(handler, hostname="localhost", port=port)
    controller.start()
    yield handler, port
    controller.stop()


def _service() -> EmailService:
    return EmailService(es.SmtpEmailBackend())


def test_plain_delivery(server: tuple[Collector, int], monkeypatch: pytest.MonkeyPatch) -> None:
    handler, port = server
    _configure(monkeypatch, port, "none")
    _service().send(MSG)
    [(sender, rcpts, parsed)] = handler.messages
    assert sender == "no-reply@example.com"
    assert rcpts == ["rcpt@example.com"]
    assert parsed["Subject"] == "Hello subject"
    assert parsed["To"] == "rcpt@example.com"
    plain = parsed.get_body(("plain",))
    html = parsed.get_body(("html",))
    assert plain is not None and "plain body" in plain.get_content()
    assert html is not None and "<p>html body</p>" in html.get_content()


@pytest.mark.filterwarnings("ignore:Requiring AUTH while not requiring TLS")
def test_auth_over_plain_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = Collector()
    port = _free_port()
    controller = Controller(
        handler,
        hostname="localhost",
        port=port,
        authenticator=_authenticator,
        auth_required=True,
        auth_require_tls=False,
    )
    controller.start()
    try:
        _configure(monkeypatch, port, "none", "user", "s3cret")
        _service().send(MSG)
        assert len(handler.messages) == 1

        _configure(monkeypatch, port, "none", "user", "wrong")
        with pytest.raises(EmailError):
            _service().send(MSG)
        assert len(handler.messages) == 1
    finally:
        controller.stop()


def test_starttls_delivery(
    cert: tuple[Path, Path], trust_cert: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    handler = Collector()
    port = _free_port()
    controller = Controller(
        handler,
        hostname="localhost",
        port=port,
        tls_context=_server_ctx(cert),
        require_starttls=True,
        authenticator=_authenticator,
        auth_required=True,
    )
    controller.start()
    try:
        _configure(monkeypatch, port, "starttls", "user", "s3cret")
        _service().send(MSG)
        assert len(handler.messages) == 1
        # Without STARTTLS the server refuses, and the failure surfaces as EmailError.
        _configure(monkeypatch, port, "none", "user", "s3cret")
        with pytest.raises(EmailError):
            _service().send(MSG)
    finally:
        controller.stop()


def test_starttls_rejects_untrusted_certificate(
    cert: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    port = _free_port()
    controller = Controller(
        Collector(), hostname="localhost", port=port, tls_context=_server_ctx(cert)
    )
    controller.start()
    try:
        _configure(monkeypatch, port, "starttls")  # default trust store: self-signed is rejected
        with pytest.raises(EmailError):
            _service().send(MSG)
    finally:
        controller.stop()


def test_implicit_ssl_delivery(
    cert: tuple[Path, Path], trust_cert: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    handler = Collector()
    port = _free_port()
    controller = Controller(handler, hostname="localhost", port=port, ssl_context=_server_ctx(cert))
    controller.start()
    try:
        _configure(monkeypatch, port, "ssl")
        _service().send(MSG)
        assert len(handler.messages) == 1
    finally:
        controller.stop()


def test_server_down_is_logged_not_raised(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _configure(monkeypatch, _free_port(), "none")  # nothing is listening
    service = _service()
    with pytest.raises(EmailError):
        service.send(MSG)
    with caplog.at_level(logging.ERROR, logger="app.services.email_service"):
        assert service.send_safely(MSG) is False
    assert "Email send failed" in caplog.text
    assert "plain body" not in caplog.text


def test_header_injection_never_reaches_server(
    server: tuple[Collector, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    handler, port = server
    _configure(monkeypatch, port, "none")
    service = _service()
    bad = [
        Email("a@example.com\r\nBcc: evil@example.com", "s", "t", "h"),
        Email("a@example.com", "Hi\r\nBcc: evil@example.com", "t", "h"),
    ]
    for msg in bad:
        with pytest.raises(EmailError):
            service.send(msg)
        assert service.send_safely(msg) is False
    monkeypatch.setattr(settings, "SMTP_FROM", "x@example.com\r\nBcc: evil@example.com")
    with pytest.raises(EmailError):
        service.send(MSG)
    assert handler.messages == []
