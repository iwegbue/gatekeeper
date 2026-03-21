import logging

from fastapi import APIRouter, Depends, Form, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.auth import SESSION_COOKIE, MAX_SESSION_AGE, create_session_token
from app.config import settings as app_settings
from app.csrf import require_csrf
from app.database import get_db
from app.services.settings_service import set_admin_password

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


@router.get("/setup")
async def setup_page(request: Request):
    if not getattr(request.app.state, "needs_setup", False):
        return RedirectResponse(url="/login", status_code=302)
    return request.app.state.templates.TemplateResponse(
        "auth/setup.html",
        {"request": request, "error": None},
    )


@router.post("/setup")
@limiter.limit("10/minute")
async def setup_submit(
    request: Request,
    password: str = Form(...),
    password_confirm: str = Form(...),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    if not getattr(request.app.state, "needs_setup", False):
        return RedirectResponse(url="/login", status_code=302)

    if len(password) < 8:
        return request.app.state.templates.TemplateResponse(
            "auth/setup.html",
            {"request": request, "error": "Password must be at least 8 characters."},
        )

    if password != password_confirm:
        return request.app.state.templates.TemplateResponse(
            "auth/setup.html",
            {"request": request, "error": "Passwords do not match."},
        )

    await set_admin_password(db, password)
    request.app.state.needs_setup = False
    logger.info("Admin password configured via setup wizard")

    response = RedirectResponse(url="/", status_code=303)
    is_https = app_settings.APP_BASE_URL.startswith("https://")
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(),
        httponly=True,
        samesite="strict",
        secure=is_https,
        max_age=MAX_SESSION_AGE,
    )
    return response
