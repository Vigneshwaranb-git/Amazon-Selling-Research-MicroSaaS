"""Shared fixture: an in-memory console email service installed process-wide."""

from collections.abc import Iterator

import pytest

from app.services.email_service import ConsoleEmailBackend, EmailService, set_email_service


@pytest.fixture()
def mail() -> Iterator[EmailService]:
    service = EmailService(ConsoleEmailBackend())
    set_email_service(service)
    yield service
    set_email_service(None)
