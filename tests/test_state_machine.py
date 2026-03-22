"""
Tests for state_machine — transitions, guards, blockers, regression, invalidation.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import IdeaState
from app.services import checklist_service, state_machine
from app.services.state_machine import GuardError, TransitionError
from tests.factories import create_idea, create_plan, create_rule


async def _make_idea_with_all_layers_checkable(db: AsyncSession):
    """Create a plan with one REQUIRED rule per layer, return (plan, idea, checks)."""
    from app.models.enums import PlanLayer

    plan = await create_plan(db)
    for layer in PlanLayer:
        await create_rule(db, plan.id, layer=layer.value, name=f"{layer.value} Gate", rule_type="REQUIRED")
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)
    return plan, idea, checks


async def _check_layer(db: AsyncSession, idea_id, checks, layer: str):
    """Check all rules for a given layer."""
    from sqlalchemy import select

    from app.models.plan_rule import PlanRule

    for check in checks:
        result = await db.execute(select(PlanRule).where(PlanRule.id == check.rule_id))
        rule = result.scalar_one()
        if rule.layer == layer and not check.checked:
            await checklist_service.toggle_check(db, check.id, True)


# ── Forward transitions ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_advance_blocked_when_layer_incomplete(db: AsyncSession):
    """WATCHING with unchecked CONTEXT rules cannot advance."""
    plan, idea, checks = await _make_idea_with_all_layers_checkable(db)
    assert idea.state == IdeaState.WATCHING.value

    with pytest.raises(GuardError) as exc_info:
        await state_machine.advance(db, idea)
    assert exc_info.value.blockers  # at least one blocker


@pytest.mark.asyncio
async def test_advance_watching_to_setup_valid(db: AsyncSession):
    """All CONTEXT required rules checked → can advance to SETUP_VALID."""
    plan, idea, checks = await _make_idea_with_all_layers_checkable(db)
    await _check_layer(db, idea.id, checks, "CONTEXT")

    result = await state_machine.advance(db, idea)
    assert result.state == IdeaState.SETUP_VALID.value


@pytest.mark.asyncio
async def test_advance_setup_valid_to_confirmed(db: AsyncSession):
    plan, idea, checks = await _make_idea_with_all_layers_checkable(db)

    # Check CONTEXT to advance to SETUP_VALID
    await _check_layer(db, idea.id, checks, "CONTEXT")
    await state_machine.advance(db, idea)
    assert idea.state == IdeaState.SETUP_VALID.value

    # Now check SETUP layer
    await _check_layer(db, idea.id, checks, "SETUP")
    await state_machine.advance(db, idea)
    assert idea.state == IdeaState.CONFIRMED.value


@pytest.mark.asyncio
async def test_advance_confirmed_requires_confirmation_entry_risk(db: AsyncSession):
    """CONFIRMED → ENTRY_PERMITTED requires CONFIRMATION + ENTRY + RISK layers."""
    plan, idea, checks = await _make_idea_with_all_layers_checkable(db)

    # Advance to CONFIRMED
    await _check_layer(db, idea.id, checks, "CONTEXT")
    await state_machine.advance(db, idea)
    await _check_layer(db, idea.id, checks, "SETUP")
    await state_machine.advance(db, idea)

    # Only check CONFIRMATION — should still be blocked
    await _check_layer(db, idea.id, checks, "CONFIRMATION")
    with pytest.raises(GuardError):
        await state_machine.advance(db, idea)

    # Check ENTRY too — still blocked (missing RISK)
    await _check_layer(db, idea.id, checks, "ENTRY")
    with pytest.raises(GuardError):
        await state_machine.advance(db, idea)

    # Check RISK — now should succeed
    await _check_layer(db, idea.id, checks, "RISK")
    await state_machine.advance(db, idea)
    assert idea.state == IdeaState.ENTRY_PERMITTED.value


@pytest.mark.asyncio
async def test_advance_entry_permitted_to_in_trade_no_layer_guard(db: AsyncSession):
    """ENTRY_PERMITTED → IN_TRADE has no layer requirements (manual trade open)."""
    plan, idea, checks = await _make_idea_with_all_layers_checkable(db)

    # Walk up to ENTRY_PERMITTED
    for layer in ["CONTEXT", "SETUP"]:
        await _check_layer(db, idea.id, checks, layer)
        await state_machine.advance(db, idea)
    for layer in ["CONFIRMATION", "ENTRY", "RISK"]:
        await _check_layer(db, idea.id, checks, layer)
    await state_machine.advance(db, idea)
    assert idea.state == IdeaState.ENTRY_PERMITTED.value

    # No guard for this step
    await state_machine.advance(db, idea)
    assert idea.state == IdeaState.IN_TRADE.value


@pytest.mark.asyncio
async def test_advance_in_trade_to_managed_requires_management_layer(db: AsyncSession):
    plan, idea, checks = await _make_idea_with_all_layers_checkable(db)

    # Walk to IN_TRADE
    for layer in ["CONTEXT", "SETUP"]:
        await _check_layer(db, idea.id, checks, layer)
        await state_machine.advance(db, idea)
    for layer in ["CONFIRMATION", "ENTRY", "RISK"]:
        await _check_layer(db, idea.id, checks, layer)
    await state_machine.advance(db, idea)
    await state_machine.advance(db, idea)
    assert idea.state == IdeaState.IN_TRADE.value

    # Should be blocked without MANAGEMENT checked
    with pytest.raises(GuardError):
        await state_machine.advance(db, idea)

    await _check_layer(db, idea.id, checks, "MANAGEMENT")
    await state_machine.advance(db, idea)
    assert idea.state == IdeaState.MANAGED.value


@pytest.mark.asyncio
async def test_advance_managed_to_closed_no_guard(db: AsyncSession):
    plan, idea, checks = await _make_idea_with_all_layers_checkable(db)

    # Walk to MANAGED
    for layer in ["CONTEXT", "SETUP"]:
        await _check_layer(db, idea.id, checks, layer)
        await state_machine.advance(db, idea)
    for layer in ["CONFIRMATION", "ENTRY", "RISK"]:
        await _check_layer(db, idea.id, checks, layer)
    await state_machine.advance(db, idea)
    await state_machine.advance(db, idea)
    await _check_layer(db, idea.id, checks, "MANAGEMENT")
    await state_machine.advance(db, idea)
    assert idea.state == IdeaState.MANAGED.value

    await state_machine.advance(db, idea)
    assert idea.state == IdeaState.CLOSED.value


@pytest.mark.asyncio
async def test_cannot_advance_from_terminal_states(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.CLOSED.value)
    with pytest.raises(TransitionError):
        await state_machine.advance(db, idea)

    idea2 = await create_idea(db, state=IdeaState.INVALIDATED.value)
    with pytest.raises(TransitionError):
        await state_machine.advance(db, idea2)


# ── Backward regression ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_regress_confirmed_to_setup_valid(db: AsyncSession):
    plan, idea, checks = await _make_idea_with_all_layers_checkable(db)
    await _check_layer(db, idea.id, checks, "CONTEXT")
    await state_machine.advance(db, idea)
    await _check_layer(db, idea.id, checks, "SETUP")
    await state_machine.advance(db, idea)
    assert idea.state == IdeaState.CONFIRMED.value

    await state_machine.regress(db, idea)
    assert idea.state == IdeaState.SETUP_VALID.value


@pytest.mark.asyncio
async def test_regress_setup_valid_to_watching(db: AsyncSession):
    plan, idea, checks = await _make_idea_with_all_layers_checkable(db)
    await _check_layer(db, idea.id, checks, "CONTEXT")
    await state_machine.advance(db, idea)
    assert idea.state == IdeaState.SETUP_VALID.value

    await state_machine.regress(db, idea)
    assert idea.state == IdeaState.WATCHING.value


@pytest.mark.asyncio
async def test_cannot_regress_from_in_trade(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.IN_TRADE.value)
    with pytest.raises(TransitionError):
        await state_machine.regress(db, idea)


@pytest.mark.asyncio
async def test_cannot_regress_from_managed(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.MANAGED.value)
    with pytest.raises(TransitionError):
        await state_machine.regress(db, idea)


@pytest.mark.asyncio
async def test_cannot_regress_from_closed(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.CLOSED.value)
    with pytest.raises(TransitionError):
        await state_machine.regress(db, idea)


@pytest.mark.asyncio
async def test_cannot_regress_from_watching(db: AsyncSession):
    """WATCHING has no backward transition."""
    idea = await create_idea(db, state=IdeaState.WATCHING.value)
    with pytest.raises(TransitionError):
        await state_machine.regress(db, idea)


# ── Invalidation ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalidation_from_watching(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.WATCHING.value)
    await state_machine.invalidate(db, idea, reason="Setup failed")
    assert idea.state == IdeaState.INVALIDATED.value


@pytest.mark.asyncio
async def test_invalidation_from_setup_valid(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.SETUP_VALID.value)
    await state_machine.invalidate(db, idea)
    assert idea.state == IdeaState.INVALIDATED.value


@pytest.mark.asyncio
async def test_invalidation_from_confirmed(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.CONFIRMED.value)
    await state_machine.invalidate(db, idea)
    assert idea.state == IdeaState.INVALIDATED.value


@pytest.mark.asyncio
async def test_invalidation_from_entry_permitted(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.ENTRY_PERMITTED.value)
    await state_machine.invalidate(db, idea)
    assert idea.state == IdeaState.INVALIDATED.value


@pytest.mark.asyncio
async def test_invalidation_from_in_trade(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.IN_TRADE.value)
    await state_machine.invalidate(db, idea)
    assert idea.state == IdeaState.INVALIDATED.value


@pytest.mark.asyncio
async def test_cannot_invalidate_from_closed(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.CLOSED.value)
    with pytest.raises(TransitionError):
        await state_machine.invalidate(db, idea)


@pytest.mark.asyncio
async def test_cannot_invalidate_already_invalidated(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.INVALIDATED.value)
    with pytest.raises(TransitionError):
        await state_machine.invalidate(db, idea)


# ── State transition history ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transition_is_recorded(db: AsyncSession):
    """Each state change creates a StateTransition record."""
    from sqlalchemy import select

    from app.models.state_transition import StateTransition

    plan, idea, checks = await _make_idea_with_all_layers_checkable(db)
    await _check_layer(db, idea.id, checks, "CONTEXT")
    await state_machine.advance(db, idea, reason="Context confirmed")

    result = await db.execute(select(StateTransition).where(StateTransition.idea_id == idea.id))
    transitions = list(result.scalars().all())
    assert len(transitions) == 1
    t = transitions[0]
    assert t.from_state == IdeaState.WATCHING.value
    assert t.to_state == IdeaState.SETUP_VALID.value
    assert t.reason == "Context confirmed"


# ── get_available_actions ──────────────────────────────────────────────────────


def test_available_actions_watching():
    actions = state_machine.get_available_actions(IdeaState.WATCHING.value)
    assert actions["can_advance"] is True
    assert actions["can_regress"] is False
    assert actions["can_invalidate"] is True


def test_available_actions_in_trade():
    actions = state_machine.get_available_actions(IdeaState.IN_TRADE.value)
    assert actions["can_advance"] is True
    assert actions["can_regress"] is False  # post-trade, no regression
    assert actions["can_invalidate"] is True


def test_available_actions_closed():
    actions = state_machine.get_available_actions(IdeaState.CLOSED.value)
    assert actions["can_advance"] is False
    assert actions["can_regress"] is False
    assert actions["can_invalidate"] is False


def test_available_actions_invalidated():
    actions = state_machine.get_available_actions(IdeaState.INVALIDATED.value)
    assert actions["can_advance"] is False
    assert actions["can_invalidate"] is False


def test_available_actions_confirmed():
    actions = state_machine.get_available_actions(IdeaState.CONFIRMED.value)
    assert actions["can_advance"] is True
    assert actions["can_regress"] is True
    assert actions["can_invalidate"] is True
