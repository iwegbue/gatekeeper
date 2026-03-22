"""
Trade CRUD service.

Handles creating trades from ideas, updating SL/TP, marking partials/BE,
and closing trades with R-multiple computation.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import IdeaState, TradeState
from app.models.idea import Idea
from app.models.trade import Trade
from app.services import checklist_service, notification_service, state_machine


async def get_trade(db: AsyncSession, trade_id: uuid.UUID) -> Trade | None:
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    return result.scalar_one_or_none()


async def list_trades(
    db: AsyncSession,
    *,
    open_only: bool = False,
    instrument: str | None = None,
) -> list[Trade]:
    stmt = select(Trade).order_by(Trade.entry_time.desc())
    if open_only:
        stmt = stmt.where(Trade.state.not_in([TradeState.CLOSED.value]))
    if instrument:
        stmt = stmt.where(Trade.instrument == instrument.upper())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_trade_for_idea(db: AsyncSession, idea_id: uuid.UUID) -> Trade | None:
    result = await db.execute(select(Trade).where(Trade.idea_id == idea_id))
    return result.scalar_one_or_none()


async def open_trade(
    db: AsyncSession,
    idea: Idea,
    *,
    entry_price: float,
    sl_price: float,
    tp_price: float | None = None,
    lot_size: float | None = None,
    risk_pct: float | None = None,
) -> Trade:
    """
    Create a trade from an ENTRY_PERMITTED idea and advance the idea to IN_TRADE.
    Raises ValueError if idea is not in ENTRY_PERMITTED state.
    """
    if idea.state != IdeaState.ENTRY_PERMITTED.value:
        raise ValueError(f"Cannot open trade: idea must be in ENTRY_PERMITTED state (currently {idea.state})")

    trade = Trade(
        idea_id=idea.id,
        instrument=idea.instrument,
        direction=idea.direction,
        entry_time=datetime.now(timezone.utc),
        entry_price=entry_price,
        sl_price=sl_price,
        initial_sl_price=sl_price,
        tp_price=tp_price,
        risk_pct=risk_pct or idea.risk_pct or 1.0,
        lot_size=lot_size,
        grade=idea.grade or "C",
        state=TradeState.OPEN.value,
    )
    db.add(trade)
    await db.flush()

    # Advance idea to IN_TRADE
    await state_machine.advance(db, idea, reason="Trade opened")
    await db.flush()

    return trade


async def update_trade(
    db: AsyncSession,
    trade_id: uuid.UUID,
    **kwargs,
) -> Trade | None:
    trade = await get_trade(db, trade_id)
    if trade is None:
        return None
    protected = (
        "id",
        "idea_id",
        "instrument",
        "direction",
        "entry_time",
        "entry_price",
        "initial_sl_price",
        "r_multiple",
        "exit_time",
        "exit_price",
    )
    for key, value in kwargs.items():
        if hasattr(trade, key) and key not in protected:
            setattr(trade, key, value)
    await db.flush()
    return trade


async def take_partial(db: AsyncSession, trade_id: uuid.UUID) -> Trade | None:
    """Mark that partials have been taken; update state to PARTIAL."""
    trade = await get_trade(db, trade_id)
    if trade is None:
        return None
    trade.partials_taken = True
    if trade.state == TradeState.OPEN.value:
        trade.state = TradeState.PARTIAL.value
    await db.flush()
    return trade


async def lock_be(db: AsyncSession, trade_id: uuid.UUID) -> Trade | None:
    """Mark SL moved to breakeven."""
    trade = await get_trade(db, trade_id)
    if trade is None:
        return None
    trade.be_locked = True
    await db.flush()
    return trade


def _compute_r_multiple(
    direction: str,
    entry_price: float,
    exit_price: float,
    initial_sl_price: float,
) -> float | None:
    """
    Compute R-multiple: (exit - entry) / (entry - initial_sl) for LONG,
    flipped for SHORT.
    Returns None if SL distance is zero.
    """
    entry = float(entry_price)
    exit_ = float(exit_price)
    sl = float(initial_sl_price)

    sl_distance = entry - sl if direction == "LONG" else sl - entry
    if sl_distance == 0:
        return None

    pnl = exit_ - entry if direction == "LONG" else entry - exit_
    return round(pnl / sl_distance, 2)


async def close_trade(
    db: AsyncSession,
    trade: Trade,
    *,
    exit_price: float,
    exit_time: datetime | None = None,
) -> Trade:
    """
    Close a trade: record exit, compute R-multiple, update state to CLOSED.
    Does NOT auto-create a journal entry (that is done separately).
    """
    if trade.state == TradeState.CLOSED.value:
        raise ValueError("Trade is already closed")

    trade.exit_price = exit_price
    trade.exit_time = exit_time or datetime.now(timezone.utc)
    trade.state = TradeState.CLOSED.value
    trade.r_multiple = _compute_r_multiple(
        trade.direction,
        float(trade.entry_price),
        exit_price,
        float(trade.initial_sl_price or trade.sl_price),
    )
    await db.flush()
    await notification_service.notify_trade_closed(db, trade.instrument, trade.direction, trade.r_multiple)
    return trade


async def compute_plan_adherence(db: AsyncSession, idea_id: uuid.UUID) -> tuple[int, list[str]]:
    """
    Compute plan adherence from idea rule checks.
    Returns (adherence_pct, list_of_violated_rule_names).
    Only REQUIRED rules are considered for violations.
    """
    pairs = await checklist_service.get_checks_with_rules(db, idea_id)
    from app.models.enums import RuleType

    required_pairs = [(c, r) for c, r in pairs if r.rule_type == RuleType.REQUIRED]
    if not required_pairs:
        return 100, []

    total = len(required_pairs)
    checked_count = sum(1 for c, _ in required_pairs if c.checked)
    violations = [r.name for c, r in required_pairs if not c.checked]
    adherence_pct = int(checked_count * 100 / total)
    return adherence_pct, violations
