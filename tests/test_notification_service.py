"""
Tests for notification_service — SMTP email, Telegram, and domain event helpers.

SMTP and Telegram network calls are patched so tests run without real servers.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import notification_service


def _settings(**kwargs) -> SimpleNamespace:
    """Build a settings-like object with sensible notification defaults."""
    defaults = dict(
        notifications_enabled=True,
        email_notifications_enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="user@example.com",
        smtp_password="secret",
        smtp_from_email="gatekeeper@example.com",
        smtp_tls=True,
        notify_email_to="trader@example.com",
        telegram_notifications_enabled=True,
        telegram_bot_token="123:TOKEN",
        telegram_chat_id="-100123",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ── send_email ────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_send_email_success():
    s = _settings()
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        result = await notification_service.send_email(s, "Subject", "Body")
    assert result is True
    mock_smtp.sendmail.assert_called_once()


@pytest.mark.anyio
async def test_send_email_master_disabled():
    s = _settings(notifications_enabled=False)
    result = await notification_service.send_email(s, "Subject", "Body")
    assert result is False


@pytest.mark.anyio
async def test_send_email_channel_disabled():
    s = _settings(email_notifications_enabled=False)
    result = await notification_service.send_email(s, "Subject", "Body")
    assert result is False


@pytest.mark.anyio
async def test_send_email_missing_host():
    s = _settings(smtp_host="")
    result = await notification_service.send_email(s, "Subject", "Body")
    assert result is False


@pytest.mark.anyio
async def test_send_email_missing_to():
    s = _settings(notify_email_to="")
    result = await notification_service.send_email(s, "Subject", "Body")
    assert result is False


@pytest.mark.anyio
async def test_send_email_smtp_error_returns_false():
    s = _settings()
    with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("refused")):
        result = await notification_service.send_email(s, "Subject", "Body")
    assert result is False


# ── send_telegram ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_send_telegram_success():
    s = _settings()
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await notification_service.send_telegram(s, "Hello")

    assert result is True
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert "123:TOKEN" in call_kwargs[0][0]


@pytest.mark.anyio
async def test_send_telegram_master_disabled():
    s = _settings(notifications_enabled=False)
    result = await notification_service.send_telegram(s, "Hello")
    assert result is False


@pytest.mark.anyio
async def test_send_telegram_channel_disabled():
    s = _settings(telegram_notifications_enabled=False)
    result = await notification_service.send_telegram(s, "Hello")
    assert result is False


@pytest.mark.anyio
async def test_send_telegram_missing_token():
    s = _settings(telegram_bot_token="")
    result = await notification_service.send_telegram(s, "Hello")
    assert result is False


@pytest.mark.anyio
async def test_send_telegram_api_error_returns_false():
    s = _settings()
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": False, "description": "Bad Request"}
    mock_response.text = '{"ok": false}'
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await notification_service.send_telegram(s, "Hello")

    assert result is False


# ── domain helpers ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_notify_idea_expired(db):
    from app.services.settings_service import update_settings
    await update_settings(
        db,
        notifications_enabled=True,
        email_notifications_enabled=True,
        smtp_host="smtp.example.com",
        smtp_from_email="gk@example.com",
        notify_email_to="trader@example.com",
        telegram_notifications_enabled=False,
    )
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        await notification_service.notify_idea_expired(db, "EURUSD", "LONG")
    mock_smtp.sendmail.assert_called_once()


@pytest.mark.anyio
async def test_notify_trade_closed(db):
    from app.services.settings_service import update_settings
    await update_settings(
        db,
        notifications_enabled=True,
        telegram_notifications_enabled=True,
        telegram_bot_token="123:TOKEN",
        telegram_chat_id="-100123",
        email_notifications_enabled=False,
    )
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await notification_service.notify_trade_closed(db, "BTCUSD", "LONG", 2.5)

    assert mock_client.post.call_count == 1
    payload = mock_client.post.call_args[1]["json"]
    assert "2.50R" in payload["text"]


@pytest.mark.anyio
async def test_notify_trade_closed_no_r_multiple(db):
    from app.services.settings_service import update_settings
    await update_settings(
        db,
        notifications_enabled=True,
        telegram_notifications_enabled=True,
        telegram_bot_token="123:TOKEN",
        telegram_chat_id="-100123",
        email_notifications_enabled=False,
    )
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await notification_service.notify_trade_closed(db, "BTCUSD", "SHORT", None)

    payload = mock_client.post.call_args[1]["json"]
    assert "N/A" in payload["text"]
