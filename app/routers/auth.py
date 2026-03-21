from fastapi import APIRouter, Depends, Form, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.auth import SESSION_COOKIE, MAX_SESSION_AGE, create_session_token
from app.config import settings as app_settings
from app.csrf import require_csrf
from app.database import get_db
from app.services.settings_service import verify_admin_password

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "error": None},
    )


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    password: str = Form(...),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    if await verify_admin_password(db, password):
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

    return request.app.state.templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "error": "Invalid password"},
    )


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response
