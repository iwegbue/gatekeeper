"""
Tests for checklist_service — scoring, grading, layer completion, blockers.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlanLayer, RuleType, SetupGrade
from app.models.idea_rule_check import IdeaRuleCheck
from app.services import checklist_service
from tests.factories import create_idea, create_plan, create_rule


# ── initialize_checks ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_initialize_checks_creates_one_per_active_rule(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Rule 1")
    await create_rule(db, plan.id, layer="SETUP", name="Rule 2")
    inactive = await create_rule(db, plan.id, layer="SETUP", name="Inactive", is_active=False)

    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)

    assert len(checks) == 2  # inactive rule excluded
    rule_ids = {c.rule_id for c in checks}
    assert inactive.id not in rule_ids


@pytest.mark.asyncio
async def test_initialize_checks_all_unchecked_by_default(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id)
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)
    assert all(not c.checked for c in checks)


# ── toggle_check ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toggle_check_marks_checked(db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id)
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)

    check = checks[0]
    result = await checklist_service.toggle_check(db, check.id, True)
    assert result is not None
    assert result.checked is True
    assert result.checked_at is not None


@pytest.mark.asyncio
async def test_toggle_check_unmarks(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id)
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)
    check = checks[0]

    await checklist_service.toggle_check(db, check.id, True)
    result = await checklist_service.toggle_check(db, check.id, False)
    assert result.checked is False
    assert result.checked_at is None


@pytest.mark.asyncio
async def test_toggle_check_saves_notes(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id)
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)

    result = await checklist_service.toggle_check(db, checks[0].id, True, notes="Confirmed on H4 close")
    assert result.notes == "Confirmed on H4 close"


@pytest.mark.asyncio
async def test_toggle_check_returns_none_for_invalid_id(db: AsyncSession):
    import uuid
    result = await checklist_service.toggle_check(db, uuid.uuid4(), True)
    assert result is None


# ── compute_score ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_score_empty_returns_zero(db: AsyncSession):
    plan = await create_plan(db)
    idea = await create_idea(db)
    await checklist_service.initialize_checks(db, idea.id, plan.id)
    checked, total = await checklist_service.compute_score(db, idea.id)
    assert checked == 0
    assert total == 0


@pytest.mark.asyncio
async def test_score_with_weights(db: AsyncSession):
    plan = await create_plan(db)
    r1 = await create_rule(db, plan.id, name="Light", weight=1)
    r2 = await create_rule(db, plan.id, name="Heavy", weight=2)
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)

    # Check only the weight=2 rule
    check_for_r2 = next(c for c in checks if c.rule_id == r2.id)
    await checklist_service.toggle_check(db, check_for_r2.id, True)

    checked, total = await checklist_service.compute_score(db, idea.id)
    assert total == 3  # 1 + 2
    assert checked == 2  # only r2


@pytest.mark.asyncio
async def test_advisory_rules_excluded_from_score(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, name="Required", rule_type="REQUIRED", weight=1)
    adv = await create_rule(db, plan.id, name="Advisory", rule_type="ADVISORY", weight=0)
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)

    # Check advisory rule — should not affect score
    adv_check = next(c for c in checks if c.rule_id == adv.id)
    await checklist_service.toggle_check(db, adv_check.id, True)

    checked, total = await checklist_service.compute_score(db, idea.id)
    assert total == 1  # only the REQUIRED rule counts
    assert checked == 0  # advisory not counted even if checked


# ── compute_grade ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_grade_none_when_no_scoreable_rules(db: AsyncSession):
    plan = await create_plan(db)
    idea = await create_idea(db)
    await checklist_service.initialize_checks(db, idea.id, plan.id)
    grade = await checklist_service.compute_grade(db, idea.id)
    assert grade is None


@pytest.mark.asyncio
async def test_grade_a_at_85_percent(db: AsyncSession):
    """17/20 = 85% → A"""
    plan = await create_plan(db)
    rules = []
    for i in range(20):
        r = await create_rule(db, plan.id, name=f"Rule {i}", weight=1)
        rules.append(r)
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)

    # Check 17 of 20
    for check in checks[:17]:
        await checklist_service.toggle_check(db, check.id, True)

    grade = await checklist_service.compute_grade(db, idea.id)
    assert grade == SetupGrade.A


@pytest.mark.asyncio
async def test_grade_b_at_65_percent(db: AsyncSession):
    """13/20 = 65% → B"""
    plan = await create_plan(db)
    for i in range(20):
        await create_rule(db, plan.id, name=f"Rule {i}", weight=1)
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)

    for check in checks[:13]:
        await checklist_service.toggle_check(db, check.id, True)

    grade = await checklist_service.compute_grade(db, idea.id)
    assert grade == SetupGrade.B


@pytest.mark.asyncio
async def test_grade_c_below_65(db: AsyncSession):
    """12/20 = 60% → C"""
    plan = await create_plan(db)
    for i in range(20):
        await create_rule(db, plan.id, name=f"Rule {i}", weight=1)
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)

    for check in checks[:12]:
        await checklist_service.toggle_check(db, check.id, True)

    grade = await checklist_service.compute_grade(db, idea.id)
    assert grade == SetupGrade.C


# ── get_layer_completion ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_layer_completion_all_complete_when_no_required_rules(db: AsyncSession):
    """A layer with no REQUIRED rules is considered complete."""
    plan = await create_plan(db)
    # Only optional rules
    await create_rule(db, plan.id, layer="CONTEXT", name="Optional rule", rule_type="OPTIONAL")
    idea = await create_idea(db)
    await checklist_service.initialize_checks(db, idea.id, plan.id)

    completion = await checklist_service.get_layer_completion(db, idea.id)
    assert completion["CONTEXT"] is True


@pytest.mark.asyncio
async def test_layer_completion_false_when_required_unchecked(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Must check", rule_type="REQUIRED")
    idea = await create_idea(db)
    await checklist_service.initialize_checks(db, idea.id, plan.id)

    completion = await checklist_service.get_layer_completion(db, idea.id)
    assert completion["CONTEXT"] is False


@pytest.mark.asyncio
async def test_layer_completion_true_when_all_required_checked(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Rule A", rule_type="REQUIRED")
    await create_rule(db, plan.id, layer="CONTEXT", name="Rule B", rule_type="REQUIRED")
    await create_rule(db, plan.id, layer="CONTEXT", name="Rule C", rule_type="OPTIONAL")
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)

    # Check only the REQUIRED ones (leave optional unchecked)
    for check in checks:
        from sqlalchemy import select
        from app.models.plan_rule import PlanRule
        result = await db.execute(select(PlanRule).where(PlanRule.id == check.rule_id))
        rule = result.scalar_one()
        if rule.rule_type == RuleType.REQUIRED:
            await checklist_service.toggle_check(db, check.id, True)

    completion = await checklist_service.get_layer_completion(db, idea.id)
    assert completion["CONTEXT"] is True


@pytest.mark.asyncio
async def test_layer_completion_ignores_advisory_rules(db: AsyncSession):
    """Advisory rules don't gate layer completion."""
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Advisory", rule_type="ADVISORY")
    idea = await create_idea(db)
    await checklist_service.initialize_checks(db, idea.id, plan.id)

    completion = await checklist_service.get_layer_completion(db, idea.id)
    assert completion["CONTEXT"] is True  # no required rules → complete


# ── get_layer_blockers ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_layer_blockers_returns_unchecked_required(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Must Pass", rule_type="REQUIRED")
    await create_rule(db, plan.id, layer="CONTEXT", name="Also Required", rule_type="REQUIRED")
    idea = await create_idea(db)
    await checklist_service.initialize_checks(db, idea.id, plan.id)

    blockers = await checklist_service.get_layer_blockers(db, idea.id, "CONTEXT")
    assert "Must Pass" in blockers
    assert "Also Required" in blockers


@pytest.mark.asyncio
async def test_layer_blockers_empty_when_layer_complete(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Required", rule_type="REQUIRED")
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)
    await checklist_service.toggle_check(db, checks[0].id, True)

    blockers = await checklist_service.get_layer_blockers(db, idea.id, "CONTEXT")
    assert blockers == []


@pytest.mark.asyncio
async def test_layer_blockers_excludes_optional_and_advisory(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Optional", rule_type="OPTIONAL")
    await create_rule(db, plan.id, layer="CONTEXT", name="Advisory", rule_type="ADVISORY")
    idea = await create_idea(db)
    await checklist_service.initialize_checks(db, idea.id, plan.id)

    blockers = await checklist_service.get_layer_blockers(db, idea.id, "CONTEXT")
    assert blockers == []  # only REQUIRED rules block


# ── update_idea_score ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_idea_score_persists_to_idea(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, name="Rule 1", weight=1)
    await create_rule(db, plan.id, name="Rule 2", weight=1)
    idea = await create_idea(db)
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)

    await checklist_service.toggle_check(db, checks[0].id, True)
    await checklist_service.update_idea_score(db, idea)

    assert idea.checklist_score == 50  # 1/2
    assert idea.grade == SetupGrade.C.value
