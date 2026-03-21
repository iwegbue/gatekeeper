"""
Notification service — sends email (SendGrid) or Telegram messages.

Configured from DB settings + env vars. Gracefully no-ops when not configured.
"""
import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def send_email(
    subject: str,
    body: str,
    to_email: str | None = None,
) -> bool:
    """
    Send an email via SendGrid. Returns True on success, False on failure/not configured.
    Uses SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, NOTIFY_EMAIL env vars.
    """
    api_key = os.environ.get("SENDGRID_API_KEY", "")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "")
    notify_email = to_email or os.environ.get("NOTIFY_EMAIL", "")

    if not api_key or not from_email or not notify_email:
        logger.debug("Email not configured, skipping notification: %s", subject)
        return False

    try:
        import httpx
        payload = {
            "personalizations": [{"to": [{"email": notify_email}]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            if resp.status_code not in (200, 202):
                logger.warning("SendGrid error %s: %s", resp.status_code, resp.text[:200])
                return False
        return True
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False


async def send_telegram(
    message: str,
    chat_id: str | None = None,
) -> bool:
    """
    Send a Telegram message via Bot API.
    Uses TELEGRAM_BOT_TOKEN env var and chat_id from env or parameter.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    target_chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    if not bot_token or not target_chat_id:
        logger.debug("Telegram not configured, skipping notification")
        return False

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": target_chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10,
            )
            if not resp.json().get("ok"):
                logger.warning("Telegram error: %s", resp.text[:200])
                return False
        return True
    except Exception as e:
        logger.error("Failed to send Telegram message: %s", e)
        return False


async def notify_idea_expired(instrument: str, direction: str) -> None:
    """Notify when an idea's entry window has expired."""
    msg = f"Entry window expired: {instrument} {direction}"
    await send_email(subject=f"[Gatekeeper] {msg}", body=msg)
    await send_telegram(f"⏰ {msg}")


async def notify_trade_closed(
    instrument: str,
    direction: str,
    r_multiple: float | None,
) -> None:
    """Notify when a trade is closed."""
    r_str = f"{r_multiple:.2f}R" if r_multiple is not None else "N/A"
    msg = f"Trade closed: {instrument} {direction} → {r_str}"
    await send_email(subject=f"[Gatekeeper] {msg}", body=msg)
    await send_telegram(f"✅ {msg}")
