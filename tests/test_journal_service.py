"""
Tests for journal_service — draft creation, adherence, rule violations, tags.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import IdeaState
from app.services import checklist_service, journal_service, trade_service
from tests.factories import create_idea, create_plan, create_rule


async def _make_closed_trade(db: AsyncSession):
    """Helper: create an idea + open trade + close it."""
    idea = await create_idea(db, state=IdeaState.ENTRY_PERMITTED.value)
    trade = await trade_service.open_trade(db, idea, entry_price=1.1000, sl_price=1.0950)
    await trade_service.close_trade(db, trade, exit_price=1.1100)
    return idea, trade


# ── create_draft ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_draft_sets_trade_summary(db: AsyncSession):
    idea, trade = await _make_closed_trade(db)
    entry = await journal_service.create_draft(db, trade, plan_adherence_pct=80)
    assert entry.id is not None
    assert entry.trade_id == trade.id
    assert entry.idea_id == idea.id
    assert entry.status == "DRAFT"
    assert entry.trade_summary["instrument"] == idea.instrument
    assert float(entry.trade_summary["r_multiple"]) == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_create_draft_captures_plan_adherence(db: AsyncSession):
    idea, trade = await _make_closed_trade(db)
    entry = await journal_service.create_draft(
        db,
        trade,
        plan_adherence_pct=60,
        rule_violations=["Rule A", "Rule B"],
    )
    assert entry.plan_adherence_pct == 60
    assert entry.rule_violations["violated"] == ["Rule A", "Rule B"]


@pytest.mark.asyncio
async def test_create_draft_empty_violations(db: AsyncSession):
    idea, trade = await _make_closed_trade(db)
    entry = await journal_service.create_draft(db, trade, plan_adherence_pct=100)
    assert entry.rule_violations["violated"] == []


# ── get_entry / list_entries ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_entry_for_trade(db: AsyncSession):
    idea, trade = await _make_closed_trade(db)
    created = await journal_service.create_draft(db, trade)
    found = await journal_service.get_entry_for_trade(db, trade.id)
    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio
async def test_list_entries_returns_all(db: AsyncSession):
    idea1, trade1 = await _make_closed_trade(db)
    idea2, trade2 = await _make_closed_trade(db)
    await journal_service.create_draft(db, trade1)
    await journal_service.create_draft(db, trade2)
    entries = await journal_service.list_entries(db)
    assert len(entries) == 2


@pytest.mark.asyncio
async def test_get_entry_returns_none_for_missing(db: AsyncSession):
    import uuid

    result = await journal_service.get_entry(db, uuid.uuid4())
    assert result is None


# ── update_entry ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_entry_fields(db: AsyncSession):
    idea, trade = await _make_closed_trade(db)
    entry = await journal_service.create_draft(db, trade)

    updated = await journal_service.update_entry(
        db,
        entry.id,
        what_went_well="Patient entry",
        what_went_wrong="Moved SL too early",
        lessons_learned="Trust the plan",
        emotions="Calm",
        would_take_again=True,
        rating=4,
    )
    assert updated.what_went_well == "Patient entry"
    assert updated.what_went_wrong == "Moved SL too early"
    assert updated.lessons_learned == "Trust the plan"
    assert updated.emotions == "Calm"
    assert updated.would_take_again is True
    assert updated.rating == 4


@pytest.mark.asyncio
async def test_update_entry_cannot_change_trade_summary(db: AsyncSession):
    """trade_summary should be immutable after creation."""
    idea, trade = await _make_closed_trade(db)
    entry = await journal_service.create_draft(db, trade)
    original_instrument = entry.trade_summary["instrument"]

    await journal_service.update_entry(
        db,
        entry.id,
        trade_summary={"instrument": "HACKED"},
    )
    fresh = await journal_service.get_entry(db, entry.id)
    assert fresh.trade_summary["instrument"] == original_instrument


@pytest.mark.asyncio
async def test_update_entry_returns_none_for_missing(db: AsyncSession):
    import uuid

    result = await journal_service.update_entry(db, uuid.uuid4(), what_went_well="x")
    assert result is None


# ── complete_entry ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_entry_changes_status(db: AsyncSession):
    idea, trade = await _make_closed_trade(db)
    entry = await journal_service.create_draft(db, trade)
    assert entry.status == "DRAFT"

    completed = await journal_service.complete_entry(db, entry.id)
    assert completed.status == "COMPLETED"


# ── delete_entry ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_entry(db: AsyncSession):
    idea, trade = await _make_closed_trade(db)
    entry = await journal_service.create_draft(db, trade)
    success = await journal_service.delete_entry(db, entry.id)
    assert success is True
    assert await journal_service.get_entry(db, entry.id) is None


@pytest.mark.asyncio
async def test_delete_entry_returns_false_for_missing(db: AsyncSession):
    import uuid

    result = await journal_service.delete_entry(db, uuid.uuid4())
    assert result is False


# ── tags ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_or_create_tag_idempotent(db: AsyncSession):
    tag1 = await journal_service.get_or_create_tag(db, "discipline")
    tag2 = await journal_service.get_or_create_tag(db, "discipline")
    assert tag1.id == tag2.id


@pytest.mark.asyncio
async def test_get_or_create_tag_normalizes_case(db: AsyncSession):
    tag1 = await journal_service.get_or_create_tag(db, "FOMO")
    tag2 = await journal_service.get_or_create_tag(db, "fomo")
    assert tag1.id == tag2.id


@pytest.mark.asyncio
async def test_set_entry_tags(db: AsyncSession):
    idea, trade = await _make_closed_trade(db)
    entry = await journal_service.create_draft(db, trade)

    updated = await journal_service.set_entry_tags(db, entry.id, ["discipline", "patient", "fomo"])
    tag_names = {t.name for t in updated.tags}
    assert "discipline" in tag_names
    assert "patient" in tag_names
    assert "fomo" in tag_names


@pytest.mark.asyncio
async def test_set_entry_tags_replaces_existing(db: AsyncSession):
    idea, trade = await _make_closed_trade(db)
    entry = await journal_service.create_draft(db, trade)
    await journal_service.set_entry_tags(db, entry.id, ["old-tag"])
    updated = await journal_service.set_entry_tags(db, entry.id, ["new-tag"])
    tag_names = {t.name for t in updated.tags}
    assert "new-tag" in tag_names
    assert "old-tag" not in tag_names


# ── Full pipeline integration ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_pipeline_idea_to_journal(db: AsyncSession):
    """
    Create a plan with rules → create idea → walk to ENTRY_PERMITTED
    → open trade → close trade → auto-create journal with adherence.
    """
    plan = await create_plan(db)
    for i in range(5):
        await create_rule(db, plan.id, name=f"Rule {i}", rule_type="REQUIRED", layer="CONTEXT")

    idea = await create_idea(db, state=IdeaState.ENTRY_PERMITTED.value)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)

    # Check 3 of 5 required rules
    for check in checks[:3]:
        await checklist_service.toggle_check(db, check.id, True)

    trade = await trade_service.open_trade(db, idea, entry_price=1.1000, sl_price=1.0950)
    await trade_service.close_trade(db, trade, exit_price=1.1100)

    adherence_pct, violations = await trade_service.compute_plan_adherence(db, idea.id)
    entry = await journal_service.create_draft(
        db,
        trade,
        plan_adherence_pct=adherence_pct,
        rule_violations=violations,
    )

    assert entry.plan_adherence_pct == 60
    assert len(entry.rule_violations["violated"]) == 2
    assert float(entry.trade_summary["r_multiple"]) == pytest.approx(2.0)
