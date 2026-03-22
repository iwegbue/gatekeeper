"""
Notification service — sends email via SMTP or Telegram messages.

Reads configuration from the DB settings singleton. Both channels check the
master `notifications_enabled` flag and their own per-channel flag before
sending. All public functions gracefully no-op when not configured.
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import Settings
from app.services.settings_service import get_settings

logger = logging.getLogger(__name__)


async def send_email(settings: Settings, subject: str, body: str) -> bool:
    """
    Send an email via SMTP. Returns True on success, False on failure/skip.
    Requires email_notifications_enabled + notifications_enabled to be True,
    plus smtp_host, smtp_from_email, and notify_email_to to be configured.
    """
    if not settings.notifications_enabled or not settings.email_notifications_enabled:
        return False

    host = settings.smtp_host
    from_email = settings.smtp_from_email
    to_email = settings.notify_email_to

    if not host or not from_email or not to_email:
        logger.debug("Email not configured, skipping: %s", subject)
        return False

    port = settings.smtp_port or 587
    username = settings.smtp_username
    password = settings.smtp_password
    use_tls = settings.smtp_tls

    def _sync_send() -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_tls:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
            if username and password:
                smtp.login(username, password)
            smtp.sendmail(from_email, [to_email], msg.as_string())

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_send)
        logger.info("Email sent: %s → %s", subject, to_email)
        return True
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False


async def send_telegram(settings: Settings, message: str) -> bool:
    """
    Send a Telegram message via Bot API. Returns True on success.
    Requires telegram_notifications_enabled + notifications_enabled to be True,
    plus telegram_bot_token and telegram_chat_id to be configured.
    """
    if not settings.notifications_enabled or not settings.telegram_notifications_enabled:
        return False

    bot_token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    if not bot_token or not chat_id:
        logger.debug("Telegram not configured, skipping notification")
        return False

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10,
            )
            data = resp.json()
            if not data.get("ok"):
                logger.warning("Telegram error: %s", resp.text[:200])
                return False
        logger.info("Telegram message sent to chat %s", chat_id)
        return True
    except Exception as e:
        logger.error("Failed to send Telegram message: %s", e)
        return False


async def notify_idea_expired(db: AsyncSession, instrument: str, direction: str) -> None:
    """Notify when an idea's entry window has expired."""
    s = await get_settings(db)
    msg = f"Entry window expired: {instrument} {direction}"
    await send_email(s, subject=f"[Gatekeeper] {msg}", body=msg)
    await send_telegram(s, f"⏰ {msg}")


async def notify_trade_closed(
    db: AsyncSession,
    instrument: str,
    direction: str,
    r_multiple: float | None,
) -> None:
    """Notify when a trade is closed."""
    s = await get_settings(db)
    r_str = f"{r_multiple:.2f}R" if r_multiple is not None else "N/A"
    msg = f"Trade closed: {instrument} {direction} → {r_str}"
    await send_email(s, subject=f"[Gatekeeper] {msg}", body=msg)
    await send_telegram(s, f"✅ {msg}")
