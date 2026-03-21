import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.csrf import require_csrf
from app.database import get_db
from app.services import settings_service

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
