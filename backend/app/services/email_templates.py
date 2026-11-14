"""Email templates (HTML + plain text). Every interpolated value is escaped."""

from dataclasses import dataclass
from html import escape
from urllib.parse import quote

from app.config import settings
from app.services.email_service import Email


@dataclass(frozen=True)
class BsrAlertItem:
    asin: str
    title: str
    old_bsr: int
    new_bsr: int
    change_pct: float


def _base_url() -> str:
    return settings.FRONTEND_URL.rstrip("/")


def _wrap(heading: str, body_html: str) -> str:
    return (
        '<html><body style="font-family:Arial,sans-serif;color:#222">'
        f"<h2>{escape(heading)}</h2>{body_html}"
        f'<p style="color:#888;font-size:12px">{escape(settings.APP_NAME)}</p>'
        "</body></html>"
    )


def welcome_email(to: str, full_name: str | None) -> Email:
    name = full_name or "there"
    url = f"{_base_url()}/dashboard"
    text = f"Hi {name},\n\nWelcome to {settings.APP_NAME}! Get started: {url}\n"
    html = _wrap(
        f"Welcome to {settings.APP_NAME}",
        f"<p>Hi {escape(name)},</p><p>Your account is ready.</p>"
        f'<p><a href="{escape(url, quote=True)}">Open your dashboard</a></p>',
    )
    return Email(to=to, subject=f"Welcome to {settings.APP_NAME}", text=text, html=html)


def verification_email(to: str, full_name: str | None, token: str) -> Email:
    """Welcome + email verification in one message."""
    name = full_name or "there"
    url = f"{_base_url()}/verify-email?token={quote(token, safe='')}"
    text = (
        f"Hi {name},\n\nWelcome to {settings.APP_NAME}! Please confirm your email address "
        f"to activate your account:\n\n{url}\n\nThe link expires in 24 hours. "
        "If you did not sign up, ignore this email.\n"
    )
    html = _wrap(
        f"Welcome to {settings.APP_NAME}",
        f"<p>Hi {escape(name)},</p><p>Please confirm your email address to activate your "
        "account.</p>"
        f'<p><a href="{escape(url, quote=True)}">Verify email</a></p>'
        "<p>The link expires in 24 hours. If you did not sign up, ignore this email.</p>",
    )
    return Email(to=to, subject=f"Verify your email for {settings.APP_NAME}", text=text, html=html)


def password_reset_email(to: str, token: str) -> Email:
    url = f"{_base_url()}/reset-password?token={quote(token, safe='')}"
    text = (
        "We received a request to reset your password.\n\n"
        f"Reset it here: {url}\n\nIf this was not you, ignore this email.\n"
    )
    html = _wrap(
        "Reset your password",
        "<p>We received a request to reset your password.</p>"
        f'<p><a href="{escape(url, quote=True)}">Reset password</a></p>'
        "<p>If this was not you, ignore this email.</p>",
    )
    return Email(to=to, subject="Reset your password", text=text, html=html)


def bsr_alert_email(to: str, items: list[BsrAlertItem], threshold_pct: float) -> Email:
    settings_url = f"{_base_url()}/settings"
    n = len(items)
    thr = f"{threshold_pct:g}"
    lines: list[str] = []
    rows: list[str] = []
    for it in items:
        direction = "improved" if it.new_bsr < it.old_bsr else "dropped"
        url = f"{_base_url()}/products/{quote(it.asin, safe='')}"
        lines.append(
            f"- {it.title} ({it.asin}): BSR {it.old_bsr} -> {it.new_bsr} "
            f"({direction} {it.change_pct:.1f}%) {url}"
        )
        rows.append(
            f'<li><a href="{escape(url, quote=True)}">{escape(it.title)}</a> '
            f"({escape(it.asin)}): BSR {it.old_bsr} &rarr; {it.new_bsr} "
            f"({direction} {it.change_pct:.1f}%)</li>"
        )
    text = (
        f"{n} tracked product(s) changed BSR by {thr}% or more:\n\n"
        + "\n".join(lines)
        + f"\n\nManage alerts: {settings_url}\n"
    )
    html = _wrap(
        "BSR alert",
        f"<p>{n} tracked product(s) changed BSR by {escape(thr)}% or more:</p>"
        f"<ul>{''.join(rows)}</ul>"
        f'<p><a href="{escape(settings_url, quote=True)}">Manage alerts</a></p>',
    )
    return Email(to=to, subject=f"BSR alert: {n} tracked product(s) moved", text=text, html=html)
