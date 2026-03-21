import hmac

from fastapi import APIRouter, Form, Request
from starlette.responses import RedirectResponse

from app.auth import SESSION_COOKIE, MAX_SESSION_AGE, create_session_token
from app.config import settings

router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "error": None},
    )


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    if hmac.compare_digest(password, settings.ADMIN_PASSWORD):
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            SESSION_COOKIE,
            create_session_token(),
            httponly=True,
            samesite="lax",
            secure=True,
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
