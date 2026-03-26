import logging
import uuid

from fastapi import APIRouter, Depends, Form, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.auth import MAX_SESSION_AGE, SESSION_COOKIE, create_session_token
from app.config import settings as app_settings
from app.csrf import require_csrf
from app.database import get_db
from app.models.enums import AssetClass
from app.services import instrument_service, plan_service, settings_service
from app.services.plan_templates import get_template, list_templates

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

# ── helpers ───────────────────────────────────────────────────────────────────


def _already_completed(request: Request) -> bool:
    return getattr(request.app.state, "setup_completed", False)


def _needs_setup(request: Request) -> bool:
    return getattr(request.app.state, "needs_setup", False)


# ── Step 0: password (first-run only) ─────────────────────────────────────────


@router.get("/setup")
async def setup_page(request: Request):
    if not _needs_setup(request):
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
    if not _needs_setup(request):
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

    await settings_service.set_admin_password(db, password)
    request.app.state.needs_setup = False
    logger.info("Admin password configured via setup wizard")

    # Redirect into the onboarding walkthrough (not directly to dashboard)
    response = RedirectResponse(url="/setup/welcome", status_code=303)
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


# ── Step 1: Welcome ───────────────────────────────────────────────────────────


@router.get("/setup/welcome")
async def setup_welcome(request: Request):
    if _already_completed(request):
        return RedirectResponse(url="/", status_code=302)
    return request.app.state.templates.TemplateResponse(
        "setup/welcome.html",
        {"request": request, "step": 1},
    )


# ── Step 2: AI provider ───────────────────────────────────────────────────────


@router.get("/setup/ai")
async def setup_ai_page(request: Request, db: AsyncSession = Depends(get_db)):
    if _already_completed(request):
        return RedirectResponse(url="/", status_code=302)
    s = await settings_service.get_settings(db)
    return request.app.state.templates.TemplateResponse(
        "setup/ai.html",
        {"request": request, "step": 2, "settings": s},
    )


@router.post("/setup/ai")
async def setup_ai_submit(
    request: Request,
    ai_provider: str = Form("anthropic"),
    anthropic_api_key: str = Form(""),
    openai_api_key: str = Form(""),
    ollama_base_url: str = Form(""),
    ai_model: str = Form(""),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    kwargs: dict = dict(ai_provider=ai_provider, ollama_base_url=ollama_base_url, ai_model=ai_model)
    if anthropic_api_key:
        kwargs["anthropic_api_key"] = anthropic_api_key
    if openai_api_key:
        kwargs["openai_api_key"] = openai_api_key
    await settings_service.update_settings(db, **kwargs)
    return RedirectResponse(url="/setup/plan", status_code=303)


# ── Step 3: Trading plan ──────────────────────────────────────────────────────


@router.get("/setup/plan")
async def setup_plan_page(request: Request, db: AsyncSession = Depends(get_db)):
    if _already_completed(request):
        return RedirectResponse(url="/", status_code=302)
    plan = await plan_service.get_active_plan(db)
    templates = list_templates()
    return request.app.state.templates.TemplateResponse(
        "setup/plan.html",
        {
            "request": request,
            "step": 3,
            "plan": plan,
            "templates": templates,
        },
    )


@router.post("/setup/plan")
async def setup_plan_submit(
    request: Request,
    template_id: str = Form("scratch"),
    plan_name: str = Form("My Trading Plan"),
    plan_description: str = Form(""),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    effective_template_id = template_id if template_id != "scratch" else None
    plan = await plan_service.update_plan(
        db,
        name=plan_name or "My Trading Plan",
        description=plan_description or None,
        template_id=effective_template_id,
    )

    if effective_template_id:
        tmpl = get_template(effective_template_id)
        if tmpl:
            for rule in tmpl["rules"]:
                await plan_service.create_rule(
                    db,
                    plan.id,
                    layer=rule["layer"],
                    name=rule["name"],
                    description=rule["description"],
                    rule_type=rule["rule_type"],
                    weight=rule["weight"],
                )
            logger.info("Applied plan template '%s' during setup", effective_template_id)

    return RedirectResponse(url="/setup/instruments", status_code=303)


# ── Step 4: Watchlist ─────────────────────────────────────────────────────────


@router.get("/setup/instruments")
async def setup_instruments_page(request: Request, db: AsyncSession = Depends(get_db)):
    if _already_completed(request):
        return RedirectResponse(url="/", status_code=302)
    instruments = await instrument_service.get_all(db)
    return request.app.state.templates.TemplateResponse(
        "setup/instruments.html",
        {
            "request": request,
            "step": 4,
            "instruments": instruments,
            "asset_classes": [ac.value for ac in AssetClass],
        },
    )


@router.post("/setup/instruments")
async def setup_instruments_add(
    request: Request,
    symbol: str = Form(...),
    display_name: str = Form(...),
    asset_class: str = Form("FX"),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    symbol = symbol.strip().upper()
    display_name = display_name.strip()

    existing = await instrument_service.get_by_symbol(db, symbol)
    if not existing and symbol and display_name:
        await instrument_service.create(
            db,
            symbol=symbol,
            display_name=display_name,
            asset_class=asset_class,
        )

    instruments = await instrument_service.get_all(db)
    return request.app.state.templates.TemplateResponse(
        "setup/_instrument_list.html",
        {
            "request": request,
            "instruments": instruments,
            "asset_classes": [ac.value for ac in AssetClass],
        },
    )


@router.post("/setup/instruments/delete/{instrument_id}")
async def setup_instruments_delete(
    request: Request,
    instrument_id: uuid.UUID,
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    await instrument_service.delete_instrument(db, instrument_id)
    instruments = await instrument_service.get_all(db)
    return request.app.state.templates.TemplateResponse(
        "setup/_instrument_list.html",
        {
            "request": request,
            "instruments": instruments,
            "asset_classes": [ac.value for ac in AssetClass],
        },
    )


# ── Step 5: Quick tour ────────────────────────────────────────────────────────


@router.get("/setup/tour")
async def setup_tour_page(request: Request):
    if _already_completed(request):
        return RedirectResponse(url="/", status_code=302)
    return request.app.state.templates.TemplateResponse(
        "setup/tour.html",
        {"request": request, "step": 5},
    )


@router.post("/setup/complete")
async def setup_complete(
    request: Request,
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    await settings_service.update_settings(db, setup_completed=True)
    request.app.state.setup_completed = True
    logger.info("Onboarding walkthrough completed")
    return RedirectResponse(url="/?msg=Welcome+to+Gatekeeper", status_code=303)
