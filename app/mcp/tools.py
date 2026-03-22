"""
MCP tools — operations that read or mutate Gatekeeper state.

All tools open their own DB session and commit on success.
Errors are returned as plain strings (MCP surfaces them to the agent).
"""
import logging
import uuid
from typing import Annotated

from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register(mcp: FastMCP) -> None:
    """Register all tools onto the given FastMCP instance."""

    # ── Ideas ──────────────────────────────────────────────────────────────────

    @mcp.tool
    async def list_ideas(
        active_only: Annotated[bool, "Only return non-terminal ideas (exclude CLOSED/INVALIDATED)"] = False,
        instrument: Annotated[str | None, "Filter by instrument symbol (e.g. EURUSD)"] = None,
    ) -> list[dict]:
        """List trading ideas, optionally filtered by status or instrument."""
        from app.database import AsyncSessionFactory
        from app.services import idea_service
        async with AsyncSessionFactory() as db:
            ideas = await idea_service.list_ideas(db, active_only=active_only, instrument=instrument)
            return [_idea_summary(i) for i in ideas]

    @mcp.tool
    async def get_idea(
        idea_id: Annotated[str, "UUID of the idea"],
    ) -> dict:
        """Get full detail for a single idea including its checklist state and grade."""
        from app.database import AsyncSessionFactory
        from app.services import checklist_service, idea_service
        async with AsyncSessionFactory() as db:
            idea = await idea_service.get_idea(db, uuid.UUID(idea_id))
            if idea is None:
                return {"error": f"Idea {idea_id} not found"}
            pairs = await checklist_service.get_checks_with_rules(db, idea.id)
            checklist = [
                {
                    "check_id": str(c.id),
                    "rule_id": str(r.id),
                    "layer": r.layer,
                    "rule_name": r.name,
                    "rule_type": r.rule_type,
                    "checked": c.checked,
                    "notes": c.notes,
                }
                for c, r in pairs
            ]
            result = _idea_summary(idea)
            result["checklist"] = checklist
            return result

    @mcp.tool
    async def create_idea(
        instrument: Annotated[str, "Instrument symbol (e.g. EURUSD, AAPL)"],
        direction: Annotated[str, "LONG or SHORT"],
        notes: Annotated[str | None, "Optional setup notes"] = None,
        risk_pct: Annotated[float | None, "Risk percentage for this trade (e.g. 1.0)"] = None,
    ) -> dict:
        """Create a new trading idea in WATCHING state with a fresh checklist."""
        from app.database import AsyncSessionFactory
        from app.services import idea_service
        async with AsyncSessionFactory() as db:
            direction_upper = direction.upper()
            if direction_upper not in ("LONG", "SHORT"):
                return {"error": "direction must be LONG or SHORT"}
            idea = await idea_service.create_idea(
                db,
                instrument=instrument,
                direction=direction_upper,
                notes=notes,
                risk_pct=risk_pct,
            )
            await db.commit()
            return _idea_summary(idea)

    @mcp.tool
    async def toggle_check(
        check_id: Annotated[str, "UUID of the checklist item to toggle"],
        checked: Annotated[bool, "True to check, False to uncheck"],
        notes: Annotated[str | None, "Optional notes for this check"] = None,
    ) -> dict:
        """Toggle a rule check on an idea's checklist."""
        from app.database import AsyncSessionFactory
        from app.services import checklist_service
        async with AsyncSessionFactory() as db:
            check = await checklist_service.toggle_check(db, uuid.UUID(check_id), checked=checked, notes=notes)
            if check is None:
                return {"error": f"Check {check_id} not found"}
            await db.commit()
            return {"check_id": str(check.id), "checked": check.checked, "notes": check.notes}

    @mcp.tool
    async def advance_idea(
        idea_id: Annotated[str, "UUID of the idea to advance"],
        reason: Annotated[str | None, "Optional reason for the transition"] = None,
    ) -> dict:
        """
        Advance an idea to the next state in the state machine.
        Will fail with an error if required rules for the current layer are not checked.
        """
        from app.database import AsyncSessionFactory
        from app.services import idea_service, state_machine
        from app.services.state_machine import GuardError, TransitionError
        async with AsyncSessionFactory() as db:
            idea = await idea_service.get_idea(db, uuid.UUID(idea_id))
            if idea is None:
                return {"error": f"Idea {idea_id} not found"}
            try:
                idea = await state_machine.advance(db, idea, reason=reason)
                await db.commit()
                return _idea_summary(idea)
            except (GuardError, TransitionError) as e:
                return {"error": str(e)}

    @mcp.tool
    async def regress_idea(
        idea_id: Annotated[str, "UUID of the idea to regress"],
        reason: Annotated[str | None, "Optional reason for the regression"] = None,
    ) -> dict:
        """Regress an idea one step back in the state machine (only allowed before IN_TRADE)."""
        from app.database import AsyncSessionFactory
        from app.services import idea_service, state_machine
        from app.services.state_machine import TransitionError
        async with AsyncSessionFactory() as db:
            idea = await idea_service.get_idea(db, uuid.UUID(idea_id))
            if idea is None:
                return {"error": f"Idea {idea_id} not found"}
            try:
                idea = await state_machine.regress(db, idea, reason=reason)
                await db.commit()
                return _idea_summary(idea)
            except TransitionError as e:
                return {"error": str(e)}

    @mcp.tool
    async def invalidate_idea(
        idea_id: Annotated[str, "UUID of the idea to invalidate"],
        reason: Annotated[str | None, "Reason for invalidation"] = None,
    ) -> dict:
        """Invalidate an idea (marks it as no longer valid; cannot be undone)."""
        from app.database import AsyncSessionFactory
        from app.services import idea_service, state_machine
        from app.services.state_machine import TransitionError
        async with AsyncSessionFactory() as db:
            idea = await idea_service.get_idea(db, uuid.UUID(idea_id))
            if idea is None:
                return {"error": f"Idea {idea_id} not found"}
            try:
                idea = await state_machine.invalidate(db, idea, reason=reason)
                await db.commit()
                return _idea_summary(idea)
            except TransitionError as e:
                return {"error": str(e)}

    # ── Trades ─────────────────────────────────────────────────────────────────

    @mcp.tool
    async def list_trades(
        open_only: Annotated[bool, "Only return open trades"] = False,
    ) -> list[dict]:
        """List trades, optionally filtered to open trades only."""
        from app.database import AsyncSessionFactory
        from app.services import trade_service
        async with AsyncSessionFactory() as db:
            trades = await trade_service.list_trades(db, open_only=open_only)
            return [_trade_summary(t) for t in trades]

    @mcp.tool
    async def get_trade(
        trade_id: Annotated[str, "UUID of the trade"],
    ) -> dict:
        """Get full detail for a single trade."""
        from app.database import AsyncSessionFactory
        from app.services import trade_service
        async with AsyncSessionFactory() as db:
            trade = await trade_service.get_trade(db, uuid.UUID(trade_id))
            if trade is None:
                return {"error": f"Trade {trade_id} not found"}
            return _trade_summary(trade)

    @mcp.tool
    async def open_trade(
        idea_id: Annotated[str, "UUID of the ENTRY_PERMITTED idea to open a trade from"],
        entry_price: Annotated[float, "Entry price"],
        sl_price: Annotated[float, "Stop loss price"],
        tp_price: Annotated[float | None, "Take profit price (optional)"] = None,
        lot_size: Annotated[float | None, "Position size in lots (optional)"] = None,
        risk_pct: Annotated[float | None, "Risk percentage override (optional)"] = None,
    ) -> dict:
        """Open a trade from an ENTRY_PERMITTED idea. The idea must be in ENTRY_PERMITTED state."""
        from app.database import AsyncSessionFactory
        from app.services import idea_service, trade_service
        async with AsyncSessionFactory() as db:
            idea = await idea_service.get_idea(db, uuid.UUID(idea_id))
            if idea is None:
                return {"error": f"Idea {idea_id} not found"}
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
                return _trade_summary(trade)
            except ValueError as e:
                return {"error": str(e)}

    @mcp.tool
    async def close_trade(
        trade_id: Annotated[str, "UUID of the open trade to close"],
        exit_price: Annotated[float, "Exit price"],
    ) -> dict:
        """Close an open trade and compute the R-multiple. Auto-creates a journal draft."""
        from app.database import AsyncSessionFactory
        from app.services import trade_service
        async with AsyncSessionFactory() as db:
            try:
                trade = await trade_service.close_trade(db, uuid.UUID(trade_id), exit_price=exit_price)
                if trade is None:
                    return {"error": f"Trade {trade_id} not found"}
                await db.commit()
                return _trade_summary(trade)
            except ValueError as e:
                return {"error": str(e)}

    @mcp.tool
    async def update_stop_loss(
        trade_id: Annotated[str, "UUID of the open trade"],
        sl_price: Annotated[float, "New stop loss price"],
    ) -> dict:
        """Update the stop loss on an open trade."""
        from app.database import AsyncSessionFactory
        from app.services import trade_service
        async with AsyncSessionFactory() as db:
            trade = await trade_service.update_trade(db, uuid.UUID(trade_id), sl_price=sl_price)
            if trade is None:
                return {"error": f"Trade {trade_id} not found"}
            await db.commit()
            return _trade_summary(trade)

    @mcp.tool
    async def take_partial(
        trade_id: Annotated[str, "UUID of the open trade"],
    ) -> dict:
        """Record a partial close on an open trade."""
        from app.database import AsyncSessionFactory
        from app.services import trade_service
        async with AsyncSessionFactory() as db:
            trade = await trade_service.take_partial(db, uuid.UUID(trade_id))
            if trade is None:
                return {"error": f"Trade {trade_id} not found"}
            await db.commit()
            return _trade_summary(trade)

    @mcp.tool
    async def lock_breakeven(
        trade_id: Annotated[str, "UUID of the open trade"],
    ) -> dict:
        """Lock breakeven on an open trade (moves SL to entry price)."""
        from app.database import AsyncSessionFactory
        from app.services import trade_service
        async with AsyncSessionFactory() as db:
            trade = await trade_service.lock_be(db, uuid.UUID(trade_id))
            if trade is None:
                return {"error": f"Trade {trade_id} not found"}
            await db.commit()
            return _trade_summary(trade)

    # ── Journal ────────────────────────────────────────────────────────────────

    @mcp.tool
    async def list_journal(
        completed_only: Annotated[bool, "Only return completed entries"] = False,
    ) -> list[dict]:
        """List journal entries."""
        from app.database import AsyncSessionFactory
        from app.services import journal_service
        async with AsyncSessionFactory() as db:
            entries = await journal_service.list_entries(db)
            if completed_only:
                entries = [e for e in entries if e.completed]
            return [_journal_summary(e) for e in entries]

    @mcp.tool
    async def get_journal_entry(
        entry_id: Annotated[str, "UUID of the journal entry"],
    ) -> dict:
        """Get full detail for a single journal entry."""
        from app.database import AsyncSessionFactory
        from app.services import journal_service
        async with AsyncSessionFactory() as db:
            entry = await journal_service.get_entry(db, uuid.UUID(entry_id))
            if entry is None:
                return {"error": f"Journal entry {entry_id} not found"}
            return _journal_detail(entry)

    @mcp.tool
    async def update_journal_entry(
        entry_id: Annotated[str, "UUID of the journal entry"],
        what_went_well: Annotated[str | None, "What went well in this trade"] = None,
        what_went_wrong: Annotated[str | None, "What went wrong in this trade"] = None,
        lessons_learned: Annotated[str | None, "Key lessons from this trade"] = None,
        emotions: Annotated[str | None, "Emotional state during the trade"] = None,
        would_take_again: Annotated[bool | None, "Would you take this trade again?"] = None,
    ) -> dict:
        """Update the reflective fields on a journal entry."""
        from app.database import AsyncSessionFactory
        from app.services import journal_service
        async with AsyncSessionFactory() as db:
            kwargs = {k: v for k, v in {
                "what_went_well": what_went_well,
                "what_went_wrong": what_went_wrong,
                "lessons_learned": lessons_learned,
                "emotions": emotions,
                "would_take_again": would_take_again,
            }.items() if v is not None}
            entry = await journal_service.update_entry(db, uuid.UUID(entry_id), **kwargs)
            if entry is None:
                return {"error": f"Journal entry {entry_id} not found"}
            await db.commit()
            return _journal_detail(entry)

    @mcp.tool
    async def complete_journal_entry(
        entry_id: Annotated[str, "UUID of the journal entry to mark complete"],
    ) -> dict:
        """Mark a journal entry as complete (locks it from further edits)."""
        from app.database import AsyncSessionFactory
        from app.services import journal_service
        async with AsyncSessionFactory() as db:
            entry = await journal_service.complete_entry(db, uuid.UUID(entry_id))
            if entry is None:
                return {"error": f"Journal entry {entry_id} not found"}
            await db.commit()
            return _journal_summary(entry)

    # ── AI ─────────────────────────────────────────────────────────────────────

    @mcp.tool
    async def review_idea(
        idea_id: Annotated[str, "UUID of the idea to review"],
    ) -> dict:
        """Run an AI review of an idea against the trading plan rules."""
        from app.database import AsyncSessionFactory
        from app.services import ai_service
        from app.services.ai.factory import AIConfigError, get_provider_from_db
        async with AsyncSessionFactory() as db:
            try:
                provider = await get_provider_from_db(db)
            except AIConfigError as e:
                return {"error": f"AI not configured: {e}"}
            content = await ai_service.idea_review(db, provider, uuid.UUID(idea_id))
            await db.commit()
            return {"review": content}

    @mcp.tool
    async def coach_journal(
        entry_id: Annotated[str, "UUID of the journal entry to coach"],
    ) -> dict:
        """Run AI coaching on a journal entry to identify behavioral patterns."""
        from app.database import AsyncSessionFactory
        from app.services import ai_service
        from app.services.ai.factory import AIConfigError, get_provider_from_db
        async with AsyncSessionFactory() as db:
            try:
                provider = await get_provider_from_db(db)
            except AIConfigError as e:
                return {"error": f"AI not configured: {e}"}
            content = await ai_service.journal_coach(db, provider, uuid.UUID(entry_id))
            await db.commit()
            return {"coaching": content}

    # ── Status ─────────────────────────────────────────────────────────────────

    @mcp.tool
    async def get_status() -> dict:
        """Get app health, version, and counts of active ideas and open trades."""
        from app.database import AsyncSessionFactory
        from app.services import idea_service, trade_service
        async with AsyncSessionFactory() as db:
            active_ideas = await idea_service.list_ideas(db, active_only=True)
            open_trades = await trade_service.list_trades(db, open_only=True)
            return {
                "status": "ok",
                "active_ideas": len(active_ideas),
                "open_trades": len(open_trades),
            }


# ── Serialisation helpers ───────────────────────────────────────────────────

def _idea_summary(idea) -> dict:
    return {
        "id": str(idea.id),
        "instrument": idea.instrument,
        "direction": idea.direction,
        "state": idea.state,
        "grade": idea.grade,
        "checklist_score": idea.checklist_score,
        "notes": idea.notes,
        "created_at": idea.created_at.isoformat() if idea.created_at else None,
        "entry_window_expires_at": (
            idea.entry_window_expires_at.isoformat() if idea.entry_window_expires_at else None
        ),
    }


def _trade_summary(trade) -> dict:
    return {
        "id": str(trade.id),
        "idea_id": str(trade.idea_id),
        "instrument": trade.instrument,
        "direction": trade.direction,
        "state": trade.state,
        "entry_price": trade.entry_price,
        "sl_price": trade.sl_price,
        "tp_price": trade.tp_price,
        "lot_size": trade.lot_size,
        "risk_pct": trade.risk_pct,
        "grade": trade.grade,
        "r_multiple": trade.r_multiple,
        "partials_taken": trade.partials_taken,
        "be_locked": trade.be_locked,
        "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
        "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
        "exit_price": trade.exit_price,
    }


def _journal_summary(entry) -> dict:
    return {
        "id": str(entry.id),
        "trade_id": str(entry.trade_id),
        "completed": entry.completed,
        "plan_adherence_pct": entry.plan_adherence_pct,
        "would_take_again": entry.would_take_again,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def _journal_detail(entry) -> dict:
    result = _journal_summary(entry)
    result.update({
        "what_went_well": entry.what_went_well,
        "what_went_wrong": entry.what_went_wrong,
        "lessons_learned": entry.lessons_learned,
        "emotions": entry.emotions,
        "trade_summary": entry.trade_summary,
        "rule_violations": entry.rule_violations,
    })
    return result
