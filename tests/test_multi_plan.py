"""Tests for multiple trading plans feature."""

import uuid

import pytest

from app.services import plan_service
from tests.factories import create_plan, create_rule


@pytest.mark.asyncio
async def test_get_active_plan_creates_default(db):
    plan = await plan_service.get_active_plan(db)
    assert plan.is_active is True
    assert plan.name == "My Trading Plan"


@pytest.mark.asyncio
async def test_get_active_plan_returns_existing(db):
    existing = await create_plan(db, name="Active Plan", is_active=True)
    plan = await plan_service.get_active_plan(db)
    assert plan.id == existing.id


@pytest.mark.asyncio
async def test_list_plans(db):
    await create_plan(db, name="Plan A", is_active=True)
    await create_plan(db, name="Plan B", is_active=False)
    plans = await plan_service.list_plans(db)
    assert len(plans) == 2
    names = [p.name for p in plans]
    assert "Plan A" in names
    assert "Plan B" in names


@pytest.mark.asyncio
async def test_create_plan_inactive_by_default(db):
    plan = await plan_service.create_plan(db, name="New Plan")
    assert plan.is_active is False


@pytest.mark.asyncio
async def test_create_plan_with_activate(db):
    existing = await create_plan(db, name="Old Active", is_active=True)
    new_plan = await plan_service.create_plan(db, name="New Active", activate=True)
    assert new_plan.is_active is True

    refreshed = await plan_service.get_plan_by_id(db, existing.id)
    assert refreshed.is_active is False


@pytest.mark.asyncio
async def test_activate_plan(db):
    plan_a = await create_plan(db, name="Plan A", is_active=True)
    plan_b = await create_plan(db, name="Plan B", is_active=False)

    result = await plan_service.activate_plan(db, plan_b.id)
    assert result.is_active is True

    refreshed_a = await plan_service.get_plan_by_id(db, plan_a.id)
    assert refreshed_a.is_active is False


@pytest.mark.asyncio
async def test_activate_nonexistent_plan(db):
    result = await plan_service.activate_plan(db, uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_delete_inactive_plan(db):
    await create_plan(db, name="Active", is_active=True)
    inactive = await create_plan(db, name="Inactive", is_active=False)
    error = await plan_service.delete_plan(db, inactive.id)
    assert error is None
    assert await plan_service.get_plan_by_id(db, inactive.id) is None


@pytest.mark.asyncio
async def test_cannot_delete_active_plan(db):
    active = await create_plan(db, name="Active", is_active=True)
    error = await plan_service.delete_plan(db, active.id)
    assert error == "active"
    assert await plan_service.get_plan_by_id(db, active.id) is not None


@pytest.mark.asyncio
async def test_delete_nonexistent_plan(db):
    error = await plan_service.delete_plan(db, uuid.uuid4())
    assert error is None


@pytest.mark.asyncio
async def test_cannot_delete_plan_with_ideas(db):
    from tests.factories import create_idea

    await create_plan(db, name="Active", is_active=True)
    inactive = await create_plan(db, name="Inactive", is_active=False)
    await create_idea(db, plan_id=inactive.id)

    error = await plan_service.delete_plan(db, inactive.id)
    assert error == "has_ideas"
    assert await plan_service.get_plan_by_id(db, inactive.id) is not None


@pytest.mark.asyncio
async def test_duplicate_plan(db):
    source = await create_plan(db, name="Source", is_active=True)
    await create_rule(db, source.id, layer="CONTEXT", name="Rule 1")
    await create_rule(db, source.id, layer="SETUP", name="Rule 2")

    copy = await plan_service.duplicate_plan(db, source.id, name="Copy")
    assert copy is not None
    assert copy.name == "Copy"
    assert copy.is_active is False
    assert copy.id != source.id

    copy_rules = await plan_service.get_rules(db, copy.id, active_only=False)
    assert len(copy_rules) == 2
    rule_names = {r.name for r in copy_rules}
    assert rule_names == {"Rule 1", "Rule 2"}


@pytest.mark.asyncio
async def test_duplicate_plan_default_name(db):
    source = await create_plan(db, name="My Strategy", is_active=True)
    copy = await plan_service.duplicate_plan(db, source.id)
    assert copy.name == "My Strategy (copy)"


@pytest.mark.asyncio
async def test_duplicate_nonexistent_plan(db):
    result = await plan_service.duplicate_plan(db, uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_update_plan_by_id(db):
    plan = await create_plan(db, name="Old Name", is_active=True)
    updated = await plan_service.update_plan(db, plan_id=plan.id, name="New Name")
    assert updated.name == "New Name"


@pytest.mark.asyncio
async def test_update_plan_defaults_to_active(db):
    plan = await create_plan(db, name="Active Plan", is_active=True)
    updated = await plan_service.update_plan(db, name="Updated")
    assert updated.id == plan.id
    assert updated.name == "Updated"


@pytest.mark.asyncio
async def test_get_plan_backward_compat(db):
    """get_plan() is an alias for get_active_plan()."""
    plan = await plan_service.get_plan(db)
    active = await plan_service.get_active_plan(db)
    assert plan.id == active.id
