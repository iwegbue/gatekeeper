import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.database import get_db
from app.services import idea_service, journal_service, trade_service

router = APIRouter(prefix="/trades")


@router.get("")
async def trade_list(request: Request, db: AsyncSession = Depends(get_db)):
    show_closed = request.query_params.get("closed") == "1"
    trades = await trade_service.list_trades(db, open_only=not show_closed)
    return request.app.state.templates.TemplateResponse(
        "trades/list.html",
        {
            "request": request,
            "trades": trades,
            "show_closed": show_closed,
        },
    )


@router.get("/{trade_id}")
async def trade_detail(request: Request, trade_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    trade = await trade_service.get_trade(db, trade_id)
    if trade is None:
        return RedirectResponse(url="/trades?msg=Trade+not+found&msg_type=error", status_code=303)
    idea = await idea_service.get_idea(db, trade.idea_id)
    journal_entry = await journal_service.get_entry_for_trade(db, trade_id)
    return request.app.state.templates.TemplateResponse(
        "trades/detail.html",
        {
            "request": request,
            "trade": trade,
            "idea": idea,
            "journal_entry": journal_entry,
        },
    )


@router.post("/open")
async def trade_open(
    idea_id: uuid.UUID = Form(...),
    entry_price: float = Form(...),
    sl_price: float = Form(...),
    tp_price: float | None = Form(None),
    lot_size: float | None = Form(None),
    risk_pct: float | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    idea = await idea_service.get_idea(db, idea_id)
    if idea is None:
        return RedirectResponse(url="/ideas?msg=Idea+not+found&msg_type=error", status_code=303)
    try:
        trade = await trade_service.open_trade(
            db, idea,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            lot_size=lot_size,
            risk_pct=risk_pct,
        )
        await db.commit()
        return RedirectResponse(url=f"/trades/{trade.id}?msg=Trade+opened", status_code=303)
    except ValueError as e:
        await db.rollback()
        return RedirectResponse(
            url=f"/ideas/{idea_id}?msg={str(e)}&msg_type=error",
            status_code=303,
        )


@router.post("/{trade_id}/update-sl")
async def trade_update_sl(
    trade_id: uuid.UUID,
    sl_price: float = Form(...),
    db: AsyncSession = Depends(get_db),
):
    await trade_service.update_trade(db, trade_id, sl_price=sl_price)
    await db.commit()
    return RedirectResponse(url=f"/trades/{trade_id}?msg=SL+updated", status_code=303)


@router.post("/{trade_id}/partial")
async def trade_partial(trade_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await trade_service.take_partial(db, trade_id)
    await db.commit()
    return RedirectResponse(url=f"/trades/{trade_id}?msg=Partial+recorded", status_code=303)


@router.post("/{trade_id}/be")
async def trade_be(trade_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await trade_service.lock_be(db, trade_id)
    await db.commit()
    return RedirectResponse(url=f"/trades/{trade_id}?msg=BE+locked", status_code=303)


@router.post("/{trade_id}/close")
async def trade_close(
    trade_id: uuid.UUID,
    exit_price: float = Form(...),
    db: AsyncSession = Depends(get_db),
):
    trade = await trade_service.get_trade(db, trade_id)
    if trade is None:
        return RedirectResponse(url="/trades?msg=Trade+not+found&msg_type=error", status_code=303)
    try:
        await trade_service.close_trade(db, trade, exit_price=exit_price)

        # Auto-create journal draft
        adherence_pct, violations = await trade_service.compute_plan_adherence(db, trade.idea_id)
        journal_entry = await journal_service.get_entry_for_trade(db, trade_id)
        if journal_entry is None:
            await journal_service.create_draft(
                db, trade,
                plan_adherence_pct=adherence_pct,
                rule_violations=violations,
            )

        await db.commit()
        return RedirectResponse(
            url=f"/trades/{trade_id}?msg=Trade+closed",
            status_code=303,
        )
    except ValueError as e:
        await db.rollback()
        return RedirectResponse(
            url=f"/trades/{trade_id}?msg={str(e)}&msg_type=error",
            status_code=303,
        )
