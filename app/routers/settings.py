import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.csrf import require_csrf
from app.database import get_db
from app.services import notification_service, settings_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings")


@router.get("")
async def settings_page(request: Request, db: AsyncSession = Depends(get_db)):
    s = await settings_service.get_settings(db)
    return request.app.state.templates.TemplateResponse(
        "settings/edit.html",
        {"request": request, "settings": s},
    )


@router.post("")
async def settings_update(
    request: Request,
    ai_provider: str = Form("anthropic"),
    anthropic_api_key: str = Form(""),
    openai_api_key: str = Form(""),
    ollama_base_url: str = Form(""),
    ai_model: str = Form(""),
    notifications_enabled: bool = Form(False),  # unchecked checkbox = not submitted = False
    entry_window_hours: int = Form(4),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    kwargs: dict = dict(
        ai_provider=ai_provider,
        ollama_base_url=ollama_base_url,
        ai_model=ai_model,
        notifications_enabled=notifications_enabled,
        entry_window_hours=entry_window_hours,
    )
    if anthropic_api_key:
        kwargs["anthropic_api_key"] = anthropic_api_key
    if openai_api_key:
        kwargs["openai_api_key"] = openai_api_key

    await settings_service.update_settings(db, **kwargs)
    return RedirectResponse(url="/settings?msg=Settings+saved", status_code=303)


@router.post("/ai")
async def settings_ai_update(
    request: Request,
    ai_provider: str = Form("anthropic"),
    anthropic_api_key: str = Form(""),
    openai_api_key: str = Form(""),
    ollama_base_url: str = Form(""),
    ai_model: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    kwargs: dict = dict(ai_provider=ai_provider, ollama_base_url=ollama_base_url, ai_model=ai_model)
    if anthropic_api_key:
        kwargs["anthropic_api_key"] = anthropic_api_key
    if openai_api_key:
        kwargs["openai_api_key"] = openai_api_key
    await settings_service.update_settings(db, **kwargs)
    return RedirectResponse(url="/settings?msg=AI+settings+saved", status_code=303)


@router.post("/general")
async def settings_general_update(
    request: Request,
    notifications_enabled: bool = Form(False),
    entry_window_hours: int = Form(4),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    await settings_service.update_settings(
        db,
        notifications_enabled=notifications_enabled,
        entry_window_hours=entry_window_hours,
    )
    return RedirectResponse(url="/settings?msg=General+settings+saved", status_code=303)


@router.post("/generate-token")
async def generate_token(
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    raw_token = await settings_service.generate_api_token(db)
    return JSONResponse({"token": raw_token})


@router.post("/notifications")
async def settings_notifications_update(
    request: Request,
    notifications_enabled: bool = Form(False),
    email_notifications_enabled: bool = Form(False),
    smtp_host: str = Form(""),
    smtp_port: int = Form(587),
    smtp_username: str = Form(""),
    smtp_password: str = Form(""),
    smtp_from_email: str = Form(""),
    smtp_tls: bool = Form(False),
    notify_email_to: str = Form(""),
    telegram_notifications_enabled: bool = Form(False),
    telegram_bot_token: str = Form(""),
    telegram_chat_id: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    kwargs: dict = dict(
        notifications_enabled=notifications_enabled,
        email_notifications_enabled=email_notifications_enabled,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_username=smtp_username,
        smtp_from_email=smtp_from_email,
        smtp_tls=smtp_tls,
        notify_email_to=notify_email_to,
        telegram_notifications_enabled=telegram_notifications_enabled,
        telegram_chat_id=telegram_chat_id,
    )
    # Only overwrite secrets when the user actually submits a new value
    if smtp_password:
        kwargs["smtp_password"] = smtp_password
    if telegram_bot_token:
        kwargs["telegram_bot_token"] = telegram_bot_token
    await settings_service.update_settings(db, **kwargs)
    return RedirectResponse(url="/settings?msg=Notification+settings+saved", status_code=303)


@router.post("/notifications/test-email")
async def test_email_notification(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    s = await settings_service.get_settings(db)
    ok = await notification_service.send_email(
        s,
        subject="[Gatekeeper] Test notification",
        body="This is a test email from Gatekeeper. Your email notifications are working correctly.",
    )
    if ok:
        return RedirectResponse(url="/settings?msg=Test+email+sent+successfully", status_code=303)
    return RedirectResponse(url="/settings?msg=Failed+to+send+test+email+%E2%80%94+check+your+SMTP+settings&msg_type=error", status_code=303)


@router.post("/notifications/test-telegram")
async def test_telegram_notification(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    s = await settings_service.get_settings(db)
    ok = await notification_service.send_telegram(
        s,
        "🔔 This is a test message from Gatekeeper. Your Telegram notifications are working correctly.",
    )
    if ok:
        return RedirectResponse(url="/settings?msg=Test+Telegram+message+sent", status_code=303)
    return RedirectResponse(url="/settings?msg=Failed+to+send+Telegram+message+%E2%80%94+check+your+token+and+chat+ID&msg_type=error", status_code=303)


@router.post("/restart-setup")
async def restart_setup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    """Reset the onboarding wizard so it runs again on next page load."""
    await settings_service.update_settings(db, setup_completed=False)
    request.app.state.setup_completed = False
    logger.info("Setup wizard reset via Settings")
    return RedirectResponse(url="/setup/welcome", status_code=303)
