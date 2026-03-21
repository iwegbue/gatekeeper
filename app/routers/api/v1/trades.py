import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.trades import (
    TradeCloseRequest,
    TradeOpenRequest,
    TradeResponse,
    TradeUpdateSLRequest,
)
from app.services import idea_service, journal_service, trade_service

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("", response_model=list[TradeResponse])
async def list_trades(
    open_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    trades = await trade_service.list_trades(db, open_only=open_only)
    return [TradeResponse.model_validate(t) for t in trades]


@router.post("", response_model=TradeResponse, status_code=201)
async def open_trade(body: TradeOpenRequest, db: AsyncSession = Depends(get_db)):
    idea = await idea_service.get_idea(db, body.idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    try:
        trade = await trade_service.open_trade(
            db,
            idea,
            entry_price=body.entry_price,
            sl_price=body.sl_price,
            tp_price=body.tp_price,
            lot_size=body.lot_size,
            risk_pct=body.risk_pct,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return TradeResponse.model_validate(trade)


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(trade_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    trade = await trade_service.get_trade(db, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return TradeResponse.model_validate(trade)


@router.post("/{trade_id}/update-sl", response_model=TradeResponse)
async def update_sl(
    trade_id: uuid.UUID,
    body: TradeUpdateSLRequest,
    db: AsyncSession = Depends(get_db),
):
    trade = await trade_service.update_trade(db, trade_id, sl_price=body.sl_price)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return TradeResponse.model_validate(trade)


@router.post("/{trade_id}/partial", response_model=TradeResponse)
async def take_partial(trade_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    trade = await trade_service.take_partial(db, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return TradeResponse.model_validate(trade)


@router.post("/{trade_id}/be", response_model=TradeResponse)
async def lock_be(trade_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    trade = await trade_service.lock_be(db, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return TradeResponse.model_validate(trade)


@router.post("/{trade_id}/close", response_model=TradeResponse)
async def close_trade(
    trade_id: uuid.UUID,
    body: TradeCloseRequest,
    db: AsyncSession = Depends(get_db),
):
    trade = await trade_service.get_trade(db, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    try:
        trade = await trade_service.close_trade(db, trade, exit_price=body.exit_price)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Auto-create journal draft (mirrors HTML route)
    adherence_pct, violations = await trade_service.compute_plan_adherence(db, trade.idea_id)
    existing_entry = await journal_service.get_entry_for_trade(db, trade_id)
    if existing_entry is None:
        await journal_service.create_draft(
            db,
            trade,
            plan_adherence_pct=adherence_pct,
            rule_violations=violations,
        )

    return TradeResponse.model_validate(trade)
