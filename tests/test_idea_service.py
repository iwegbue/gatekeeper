"""
Tests for idea_service — CRUD, active filtering, checklist initialization.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import IdeaState
from app.services import checklist_service, idea_service
from tests.factories import create_idea, create_plan, create_rule

# ── create_idea ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_idea_defaults(db: AsyncSession):
    await create_plan(db)
    idea = await idea_service.create_idea(db, instrument="GBPUSD", direction="SHORT")
    assert idea.id is not None
    assert idea.instrument == "GBPUSD"
    assert idea.direction == "SHORT"
    assert idea.state == IdeaState.WATCHING.value


@pytest.mark.asyncio
async def test_create_idea_upcases_instrument(db: AsyncSession):
    await create_plan(db)
    idea = await idea_service.create_idea(db, instrument="eurusd", direction="LONG")
    assert idea.instrument == "EURUSD"


@pytest.mark.asyncio
async def test_create_idea_strips_whitespace(db: AsyncSession):
    await create_plan(db)
    idea = await idea_service.create_idea(db, instrument="  XAUUSD  ", direction="LONG")
    assert idea.instrument == "XAUUSD"


@pytest.mark.asyncio
async def test_create_idea_initializes_checks(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, name="Rule A")
    await create_rule(db, plan.id, name="Rule B")

    idea = await idea_service.create_idea(db, instrument="EURUSD", direction="LONG", plan_id=plan.id)
    checks = await checklist_service.get_checks(db, idea.id)
    assert len(checks) == 2


@pytest.mark.asyncio
async def test_create_idea_sets_entry_window(db: AsyncSession):
    await create_plan(db)
    idea = await idea_service.create_idea(db, instrument="EURUSD", direction="LONG")
    assert idea.entry_window_expires_at is not None


@pytest.mark.asyncio
async def test_create_idea_with_notes_and_risk(db: AsyncSession):
    await create_plan(db)
    idea = await idea_service.create_idea(
        db,
        instrument="AUDUSD",
        direction="LONG",
        risk_pct=1.5,
        notes="Solid OB confluence",
    )
    assert idea.risk_pct is not None
    assert float(idea.risk_pct) == pytest.approx(1.5)
    assert idea.notes == "Solid OB confluence"


# ── get_idea ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_idea_returns_correct(db: AsyncSession):
    idea = await create_idea(db, instrument="USDJPY")
    fetched = await idea_service.get_idea(db, idea.id)
    assert fetched is not None
    assert fetched.id == idea.id
    assert fetched.instrument == "USDJPY"


@pytest.mark.asyncio
async def test_get_idea_returns_none_for_missing(db: AsyncSession):
    import uuid

    result = await idea_service.get_idea(db, uuid.uuid4())
    assert result is None


# ── list_ideas ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_ideas_returns_all(db: AsyncSession):
    await create_idea(db, instrument="EURUSD")
    await create_idea(db, instrument="GBPUSD")
    await create_idea(db, instrument="USDJPY", state=IdeaState.CLOSED.value)

    ideas = await idea_service.list_ideas(db)
    assert len(ideas) == 3


@pytest.mark.asyncio
async def test_list_ideas_active_only_excludes_terminal(db: AsyncSession):
    await create_idea(db, instrument="EURUSD", state=IdeaState.WATCHING.value)
    await create_idea(db, instrument="GBPUSD", state=IdeaState.CONFIRMED.value)
    await create_idea(db, instrument="USDJPY", state=IdeaState.CLOSED.value)
    await create_idea(db, instrument="AUDUSD", state=IdeaState.INVALIDATED.value)

    active = await idea_service.list_ideas(db, active_only=True)
    instruments = {i.instrument for i in active}
    assert "EURUSD" in instruments
    assert "GBPUSD" in instruments
    assert "USDJPY" not in instruments
    assert "AUDUSD" not in instruments


@pytest.mark.asyncio
async def test_list_ideas_filter_by_instrument(db: AsyncSession):
    await create_idea(db, instrument="EURUSD")
    await create_idea(db, instrument="EURUSD")
    await create_idea(db, instrument="GBPUSD")

    results = await idea_service.list_ideas(db, instrument="EURUSD")
    assert len(results) == 2
    assert all(i.instrument == "EURUSD" for i in results)


@pytest.mark.asyncio
async def test_list_ideas_instrument_filter_case_insensitive(db: AsyncSession):
    await create_idea(db, instrument="EURUSD")
    results = await idea_service.list_ideas(db, instrument="eurusd")
    assert len(results) == 1


# ── update_idea ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_idea_fields(db: AsyncSession):
    idea = await create_idea(db)
    updated = await idea_service.update_idea(db, idea.id, notes="Updated notes", risk_pct=2.0)
    assert updated is not None
    assert updated.notes == "Updated notes"
    assert float(updated.risk_pct) == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_update_idea_cannot_change_state_via_kwargs(db: AsyncSession):
    """State changes must go through the state machine, not update_idea."""
    idea = await create_idea(db, state=IdeaState.WATCHING.value)
    updated = await idea_service.update_idea(db, idea.id, state=IdeaState.CONFIRMED.value)
    # state kwarg is blocked by update_idea implementation
    assert updated.state == IdeaState.WATCHING.value


@pytest.mark.asyncio
async def test_update_idea_returns_none_for_missing(db: AsyncSession):
    import uuid

    result = await idea_service.update_idea(db, uuid.uuid4(), notes="x")
    assert result is None


# ── delete_idea ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_idea_removes_it(db: AsyncSession):
    idea = await create_idea(db)
    success = await idea_service.delete_idea(db, idea.id)
    assert success is True
    fetched = await idea_service.get_idea(db, idea.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_delete_idea_returns_false_for_missing(db: AsyncSession):
    import uuid

    result = await idea_service.delete_idea(db, uuid.uuid4())
    assert result is False
