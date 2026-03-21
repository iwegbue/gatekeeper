import uuid

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.csrf import require_csrf
from app.database import get_db
from app.models.enums import AssetClass
from app.services import instrument_service

router = APIRouter(prefix="/instruments")


@router.get("")
async def instrument_list(request: Request, db: AsyncSession = Depends(get_db)):
    instruments = await instrument_service.get_all(db)
    return request.app.state.templates.TemplateResponse(
        "instruments/index.html",
        {"request": request, "instruments": instruments, "asset_classes": AssetClass},
    )


@router.get("/new")
async def instrument_form(request: Request):
    return request.app.state.templates.TemplateResponse(
        "instruments/form.html",
        {"request": request, "instrument": None, "asset_classes": AssetClass},
    )


@router.post("/new")
async def instrument_create(
    request: Request,
    symbol: str = Form(...),
    display_name: str = Form(...),
    asset_class: str = Form("FX"),
    is_enabled: bool = Form(False),
    priority: int = Form(0),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    await instrument_service.create(
        db,
        symbol=symbol.upper().strip(),
        display_name=display_name.strip(),
        asset_class=asset_class,
        is_enabled=is_enabled,
        priority=priority,
        notes=notes or None,
    )
    return RedirectResponse(url="/instruments?msg=Instrument+added", status_code=303)


@router.get("/{instrument_id}/edit")
async def instrument_edit(request: Request, instrument_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    inst = await instrument_service.get_by_id(db, instrument_id)
    if not inst:
        return RedirectResponse(url="/instruments?msg=Not+found&msg_type=error", status_code=303)
    return request.app.state.templates.TemplateResponse(
        "instruments/form.html",
        {"request": request, "instrument": inst, "asset_classes": AssetClass},
    )


@router.post("/{instrument_id}/edit")
async def instrument_update(
    request: Request,
    instrument_id: uuid.UUID,
    symbol: str = Form(...),
    display_name: str = Form(...),
    asset_class: str = Form("FX"),
    is_enabled: bool = Form(False),
    priority: int = Form(0),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    await instrument_service.update_instrument(
        db, instrument_id,
        symbol=symbol.upper().strip(),
        display_name=display_name.strip(),
        asset_class=asset_class,
        is_enabled=is_enabled,
        priority=priority,
        notes=notes or None,
    )
    return RedirectResponse(url="/instruments?msg=Instrument+updated", status_code=303)


@router.post("/{instrument_id}/delete")
async def instrument_delete(instrument_id: uuid.UUID, db: AsyncSession = Depends(get_db), _csrf: None = Depends(require_csrf)):
    await instrument_service.delete_instrument(db, instrument_id)
    return RedirectResponse(url="/instruments?msg=Instrument+deleted", status_code=303)
