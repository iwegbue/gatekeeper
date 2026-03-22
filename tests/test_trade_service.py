"""
Tests for trade_service — open, update, close, R-multiple, plan adherence.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import IdeaState, TradeState
from app.services import checklist_service, trade_service
from tests.factories import create_idea, create_plan, create_rule, create_trade

# ── open_trade ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_open_trade_requires_entry_permitted_state(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.WATCHING.value)
    with pytest.raises(ValueError, match="ENTRY_PERMITTED"):
        await trade_service.open_trade(db, idea, entry_price=1.1000, sl_price=1.0950)


@pytest.mark.asyncio
async def test_open_trade_creates_trade(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.ENTRY_PERMITTED.value, instrument="EURUSD")
    trade = await trade_service.open_trade(db, idea, entry_price=1.1000, sl_price=1.0950)
    assert trade.id is not None
    assert trade.instrument == "EURUSD"
    assert float(trade.entry_price) == pytest.approx(1.1000)
    assert float(trade.sl_price) == pytest.approx(1.0950)
    assert float(trade.initial_sl_price) == pytest.approx(1.0950)
    assert trade.state == TradeState.OPEN.value


@pytest.mark.asyncio
async def test_open_trade_advances_idea_to_in_trade(db: AsyncSession):
    await create_plan(db)
    idea = await create_idea(db, state=IdeaState.ENTRY_PERMITTED.value)
    await trade_service.open_trade(db, idea, entry_price=1.1000, sl_price=1.0950)
    assert idea.state == IdeaState.IN_TRADE.value


@pytest.mark.asyncio
async def test_open_trade_with_tp_and_lot_size(db: AsyncSession):
    idea = await create_idea(db, state=IdeaState.ENTRY_PERMITTED.value)
    trade = await trade_service.open_trade(
        db,
        idea,
        entry_price=1.1000,
        sl_price=1.0950,
        tp_price=1.1100,
        lot_size=0.5,
    )
    assert float(trade.tp_price) == pytest.approx(1.1100)
    assert float(trade.lot_size) == pytest.approx(0.5)


# ── update_trade ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_trade_sl(db: AsyncSession):
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id, sl_price=1.0950)
    updated = await trade_service.update_trade(db, trade.id, sl_price=1.0980)
    assert float(updated.sl_price) == pytest.approx(1.0980)


@pytest.mark.asyncio
async def test_update_trade_cannot_change_protected_fields(db: AsyncSession):
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id, entry_price=1.1000)
    # entry_price is protected
    await trade_service.update_trade(db, trade.id, entry_price=1.2000)
    fresh = await trade_service.get_trade(db, trade.id)
    assert float(fresh.entry_price) == pytest.approx(1.1000)


@pytest.mark.asyncio
async def test_update_trade_returns_none_for_missing(db: AsyncSession):
    import uuid

    result = await trade_service.update_trade(db, uuid.uuid4(), sl_price=1.0)
    assert result is None


# ── take_partial / lock_be ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_take_partial_sets_flag_and_state(db: AsyncSession):
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id)
    assert trade.state == TradeState.OPEN.value

    updated = await trade_service.take_partial(db, trade.id)
    assert updated.partials_taken is True
    assert updated.state == TradeState.PARTIAL.value


@pytest.mark.asyncio
async def test_lock_be_sets_flag(db: AsyncSession):
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id)
    updated = await trade_service.lock_be(db, trade.id)
    assert updated.be_locked is True


# ── close_trade ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_close_trade_sets_exit_price_and_state(db: AsyncSession):
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id, entry_price=1.1000, sl_price=1.0950)
    result = await trade_service.close_trade(db, trade, exit_price=1.1100)
    assert result.state == TradeState.CLOSED.value
    assert float(result.exit_price) == pytest.approx(1.1100)
    assert result.exit_time is not None


@pytest.mark.asyncio
async def test_close_trade_raises_if_already_closed(db: AsyncSession):
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id, state=TradeState.CLOSED.value)
    with pytest.raises(ValueError, match="already closed"):
        await trade_service.close_trade(db, trade, exit_price=1.1000)


# ── R-multiple computation ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_r_multiple_long_win(db: AsyncSession):
    """LONG: entry=1.1000, SL=1.0950, exit=1.1100 → (1.1100-1.1000)/(1.1000-1.0950) = 2.0R"""
    idea = await create_idea(db, direction="LONG")
    trade = await create_trade(db, idea.id, direction="LONG", entry_price=1.1000, sl_price=1.0950)
    await trade_service.close_trade(db, trade, exit_price=1.1100)
    assert float(trade.r_multiple) == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_r_multiple_long_loss(db: AsyncSession):
    """LONG: entry=1.1000, SL=1.0950, exit=1.0975 → (1.0975-1.1000)/(1.1000-1.0950) = -0.5R"""
    idea = await create_idea(db, direction="LONG")
    trade = await create_trade(db, idea.id, direction="LONG", entry_price=1.1000, sl_price=1.0950)
    await trade_service.close_trade(db, trade, exit_price=1.0975)
    assert float(trade.r_multiple) == pytest.approx(-0.5)


@pytest.mark.asyncio
async def test_r_multiple_short_win(db: AsyncSession):
    """SHORT: entry=1.1000, SL=1.1050, exit=1.0900 → (1.1000-1.0900)/(1.1050-1.1000) = 2.0R"""
    idea = await create_idea(db, direction="SHORT")
    trade = await create_trade(db, idea.id, direction="SHORT", entry_price=1.1000, sl_price=1.1050)
    await trade_service.close_trade(db, trade, exit_price=1.0900)
    assert float(trade.r_multiple) == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_r_multiple_short_loss(db: AsyncSession):
    """SHORT: entry=1.1000, SL=1.1050, exit=1.1025 → (1.1000-1.1025)/(1.1050-1.1000) = -0.5R"""
    idea = await create_idea(db, direction="SHORT")
    trade = await create_trade(db, idea.id, direction="SHORT", entry_price=1.1000, sl_price=1.1050)
    await trade_service.close_trade(db, trade, exit_price=1.1025)
    assert float(trade.r_multiple) == pytest.approx(-0.5)


# ── compute_plan_adherence ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plan_adherence_all_required_checked(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, name="Rule 1", rule_type="REQUIRED")
    await create_rule(db, plan.id, name="Rule 2", rule_type="REQUIRED")
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)
    for check in checks:
        await checklist_service.toggle_check(db, check.id, True)

    pct, violations = await trade_service.compute_plan_adherence(db, idea.id)
    assert pct == 100
    assert violations == []


@pytest.mark.asyncio
async def test_plan_adherence_partial_compliance(db: AsyncSession):
    """3/5 required rules checked = 60% adherence."""
    plan = await create_plan(db)
    for i in range(5):
        await create_rule(db, plan.id, name=f"Rule {i}", rule_type="REQUIRED")
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)
    for check in checks[:3]:
        await checklist_service.toggle_check(db, check.id, True)

    pct, violations = await trade_service.compute_plan_adherence(db, idea.id)
    assert pct == 60
    assert len(violations) == 2


@pytest.mark.asyncio
async def test_plan_adherence_optional_rules_not_counted_as_violations(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, name="Required", rule_type="REQUIRED")
    await create_rule(db, plan.id, name="Optional", rule_type="OPTIONAL")
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)
    # Check only the required rule
    for check in checks:
        from sqlalchemy import select

        from app.models.plan_rule import PlanRule

        result = await db.execute(select(PlanRule).where(PlanRule.id == check.rule_id))
        rule = result.scalar_one()
        if rule.rule_type == "REQUIRED":
            await checklist_service.toggle_check(db, check.id, True)

    pct, violations = await trade_service.compute_plan_adherence(db, idea.id)
    assert pct == 100
    assert violations == []


@pytest.mark.asyncio
async def test_plan_adherence_no_rules_returns_100(db: AsyncSession):
    idea = await create_idea(db)
    pct, violations = await trade_service.compute_plan_adherence(db, idea.id)
    assert pct == 100
    assert violations == []


# ── get_trade / list_trades ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_trades_open_only(db: AsyncSession):
    idea = await create_idea(db)
    open_trade = await create_trade(db, idea.id, state=TradeState.OPEN.value)
    closed_trade = await create_trade(db, idea.id, state=TradeState.CLOSED.value)

    open_only = await trade_service.list_trades(db, open_only=True)
    ids = {t.id for t in open_only}
    assert open_trade.id in ids
    assert closed_trade.id not in ids


@pytest.mark.asyncio
async def test_get_trade_for_idea(db: AsyncSession):
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id)
    found = await trade_service.get_trade_for_idea(db, idea.id)
    assert found is not None
    assert found.id == trade.id
