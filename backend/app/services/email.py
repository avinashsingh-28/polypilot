"""
Outgoing email (password reset). Uses SMTP when SMTP_HOST is configured.

Without SMTP:
  * development: the reset link is written to the backend log at WARNING level so the feature can
    be used locally (the link is a secret — never enable this path in production);
  * production: nothing can be sent; an error is logged without the token.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings

log = logging.getLogger("polypilot.email")


def _mask(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:2]}***@{domain}"


def send_password_reset(email: str, link: str, ttl_min: int) -> None:
    s = get_settings()
    if not s.SMTP_HOST:
        if s.is_production:
            log.error("password reset requested but SMTP is not configured; no email sent",
                      extra={"to": _mask(email)})
        else:
            log.warning("DEV ONLY (no SMTP configured) password reset link for %s: %s", _mask(email), link)
        return
    msg = EmailMessage()
    msg["Subject"] = "Reset your PolyPilot password"
    msg["From"] = s.SMTP_FROM or s.SMTP_USER
    msg["To"] = email
    msg.set_content(
        f"Someone asked to reset the password for your PolyPilot account.\n\n"
        f"Open this link within {ttl_min} minutes to choose a new password:\n{link}\n\n"
        f"If you did not ask for this, ignore this email — your password stays the same.\n")
    try:
        with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=20) as smtp:
            if s.SMTP_STARTTLS:
                smtp.starttls(context=ssl.create_default_context())
            if s.SMTP_USER:
                smtp.login(s.SMTP_USER, s.SMTP_PASSWORD)
            smtp.send_message(msg)
        log.info("password reset email sent", extra={"to": _mask(email)})
    except (smtplib.SMTPException, OSError) as exc:
        log.error("password reset email failed: %s", type(exc).__name__, extra={"to": _mask(email)})
