from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.database import get_db
from app.services import settings_service

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
):
    await settings_service.update_settings(
        db,
        ai_provider=ai_provider,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
        ollama_base_url=ollama_base_url,
        ai_model=ai_model,
        notifications_enabled=notifications_enabled,
        entry_window_hours=entry_window_hours,
    )
    return RedirectResponse(url="/settings?msg=Settings+saved", status_code=303)
