"""Tests for plan_service: plan CRUD + rule CRUD/reorder/completeness."""
import pytest

from app.services import plan_service
from app.models.enums import PlanLayer
from tests.factories import create_plan, create_rule


@pytest.mark.asyncio
async def test_get_plan_creates_singleton(db):
    plan = await plan_service.get_plan(db)
    plan2 = await plan_service.get_plan(db)
    assert plan.id == plan2.id


@pytest.mark.asyncio
async def test_update_plan_name(db):
    plan = await plan_service.get_plan(db)
    updated = await plan_service.update_plan(db, name="Custom Plan")
    assert updated.name == "Custom Plan"
    assert updated.id == plan.id


@pytest.mark.asyncio
async def test_create_rule(db):
    plan = await create_plan(db)
    rule = await plan_service.create_rule(db, plan.id, layer="CONTEXT", name="Trend aligned")
    assert rule.id is not None
    assert rule.layer == "CONTEXT"
    assert rule.name == "Trend aligned"
    assert rule.rule_type == "REQUIRED"
    assert rule.weight == 1


@pytest.mark.asyncio
async def test_create_rule_auto_order(db):
    plan = await create_plan(db)
    r1 = await plan_service.create_rule(db, plan.id, layer="SETUP", name="Rule 1")
    r2 = await plan_service.create_rule(db, plan.id, layer="SETUP", name="Rule 2")
    assert r2.order > r1.order


@pytest.mark.asyncio
async def test_get_rules_by_layer(db):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="C1")
    await create_rule(db, plan.id, layer="CONTEXT", name="C2")
    await create_rule(db, plan.id, layer="SETUP", name="S1")

    by_layer = await plan_service.get_rules_by_layer(db, plan.id)
    assert len(by_layer["CONTEXT"]) == 2
    assert len(by_layer["SETUP"]) == 1
    assert len(by_layer["ENTRY"]) == 0


@pytest.mark.asyncio
async def test_get_rules_filters_inactive(db):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Active")
    await create_rule(db, plan.id, layer="CONTEXT", name="Inactive", is_active=False)

    active_rules = await plan_service.get_rules(db, plan.id, active_only=True)
    all_rules = await plan_service.get_rules(db, plan.id, active_only=False)
    assert len(active_rules) == 1
    assert len(all_rules) == 2


@pytest.mark.asyncio
async def test_update_rule(db):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Old Name")
    updated = await plan_service.update_rule(db, rule.id, name="New Name", weight=3)
    assert updated.name == "New Name"
    assert updated.weight == 3


@pytest.mark.asyncio
async def test_delete_rule(db):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="To Delete")
    deleted = await plan_service.delete_rule(db, rule.id)
    assert deleted is True
    fetched = await plan_service.get_rule(db, rule.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_delete_nonexistent_rule(db):
    import uuid
    result = await plan_service.delete_rule(db, uuid.uuid4())
    assert result is False


@pytest.mark.asyncio
async def test_reorder_rules(db):
    plan = await create_plan(db)
    r1 = await create_rule(db, plan.id, layer="RISK", name="Rule 1", order=0)
    r2 = await create_rule(db, plan.id, layer="RISK", name="Rule 2", order=1)
    r3 = await create_rule(db, plan.id, layer="RISK", name="Rule 3", order=2)

    # Reverse order: r3, r1, r2
    await plan_service.reorder_rules(db, plan.id, "RISK", [r3.id, r1.id, r2.id])

    from sqlalchemy import select
    from app.models.plan_rule import PlanRule
    result = await db.execute(select(PlanRule).where(PlanRule.id == r3.id))
    assert result.scalar_one().order == 0


@pytest.mark.asyncio
async def test_all_seven_layers_exist(db):
    """Each PlanLayer enum value should be a valid layer."""
    from app.models.enums import PlanLayer
    plan = await create_plan(db)
    for layer in PlanLayer:
        rule = await create_rule(db, plan.id, layer=layer.value, name=f"Test {layer.value}")
        assert rule.layer == layer.value
