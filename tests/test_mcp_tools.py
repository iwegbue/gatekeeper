"""
Tests for the MCP tools layer.

Uses the fastmcp in-process Client to call tools directly, with the DB
session patched via AsyncSessionFactory override so each test gets an
isolated schema.
"""
import pytest
from fastmcp import Client
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import create_idea, create_idea_with_checks, create_plan, create_rule, create_trade

# ── Helpers ─────────────────────────────────────────────────────────────────

def _patch_session_factory(db: AsyncSession):
    """
    Patch AsyncSessionFactory so MCP tools use the test session.
    Returns a context manager that restores the original on exit.
    """

    import app.database as db_module

    original = db_module.AsyncSessionFactory

    class _FakeFactory:
        async def __aenter__(self_inner):
            return db

        async def __aexit__(self_inner, exc_type, exc_val, exc_tb):
            # Flush so queries see the written data, but don't close
            if exc_type is None:
                await db.flush()
            return False

    db_module.AsyncSessionFactory = _FakeFactory
    return original, db_module


def _restore_session_factory(original, db_module):
    db_module.AsyncSessionFactory = original


# ── MCP server fixture ───────────────────────────────────────────────────────

@pytest.fixture
def mcp_server():
    from app.mcp import create_mcp_server
    return create_mcp_server()


# ── Tool tests ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_status(db, mcp_server):
    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("get_status", {})
            data = result.data
            assert data["status"] == "ok"
            assert "active_ideas" in data
            assert "open_trades" in data
    finally:
        _restore_session_factory(original, db_module)


def _list_result(result) -> list:
    """Extract a list from a fastmcp CallToolResult (handles Root wrapper for lists)."""
    sc = result.structured_content
    if sc and "result" in sc:
        return sc["result"]
    data = result.data
    return data if isinstance(data, list) else []


@pytest.mark.anyio
async def test_list_ideas_empty(db, mcp_server):
    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("list_ideas", {})
            assert _list_result(result) == []
    finally:
        _restore_session_factory(original, db_module)


@pytest.mark.anyio
async def test_create_idea(db, mcp_server):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Market trend aligned")
    await db.flush()

    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("create_idea", {
                "instrument": "EURUSD",
                "direction": "LONG",
                "notes": "Strong trend",
            })
            data = result.data
            assert data["instrument"] == "EURUSD"
            assert data["direction"] == "LONG"
            assert data["state"] == "WATCHING"
            assert data["notes"] == "Strong trend"
            assert "checklist_score" in data
    finally:
        _restore_session_factory(original, db_module)


@pytest.mark.anyio
async def test_create_idea_invalid_direction(db, mcp_server):
    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("create_idea", {
                "instrument": "EURUSD",
                "direction": "SIDEWAYS",
            })
            assert "error" in result.data
    finally:
        _restore_session_factory(original, db_module)


@pytest.mark.anyio
async def test_get_idea_not_found(db, mcp_server):
    import uuid
    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("get_idea", {"idea_id": str(uuid.uuid4())})
            assert "error" in result.data
    finally:
        _restore_session_factory(original, db_module)


@pytest.mark.anyio
async def test_get_idea_with_checklist(db, mcp_server):
    plan = await create_plan(db)
    idea, checks = await create_idea_with_checks(db, plan.id)
    await db.flush()

    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("get_idea", {"idea_id": str(idea.id)})
            data = result.data
            assert data["id"] == str(idea.id)
            assert "checklist" in data
            assert len(data["checklist"]) == len(checks)
    finally:
        _restore_session_factory(original, db_module)


@pytest.mark.anyio
async def test_toggle_check(db, mcp_server):
    plan = await create_plan(db)
    idea, checks = await create_idea_with_checks(db, plan.id, num_rules_per_layer=1)
    check = checks[0]
    await db.flush()

    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("toggle_check", {
                "check_id": str(check.id),
                "checked": True,
                "notes": "Confirmed on H4",
            })
            data = result.data
            assert data["checked"] is True
            assert data["notes"] == "Confirmed on H4"
    finally:
        _restore_session_factory(original, db_module)


@pytest.mark.anyio
async def test_list_ideas_active_filter(db, mcp_server):
    from app.models.enums import IdeaState
    await create_plan(db)
    active = await create_idea(db, state=IdeaState.WATCHING.value)
    closed = await create_idea(db, state=IdeaState.CLOSED.value)
    await db.flush()

    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("list_ideas", {"active_only": True})
            items = _list_result(result)
            ids = [i["id"] for i in items]
            assert str(active.id) in ids
            assert str(closed.id) not in ids
    finally:
        _restore_session_factory(original, db_module)


@pytest.mark.anyio
async def test_list_trades_empty(db, mcp_server):
    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("list_trades", {})
            assert _list_result(result) == []
    finally:
        _restore_session_factory(original, db_module)


@pytest.mark.anyio
async def test_get_trade_not_found(db, mcp_server):
    import uuid
    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("get_trade", {"trade_id": str(uuid.uuid4())})
            assert "error" in result.data
    finally:
        _restore_session_factory(original, db_module)


@pytest.mark.anyio
async def test_get_trade(db, mcp_server):
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id)
    await db.flush()

    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("get_trade", {"trade_id": str(trade.id)})
            data = result.data
            assert data["id"] == str(trade.id)
            assert data["instrument"] == "EURUSD"
    finally:
        _restore_session_factory(original, db_module)


@pytest.mark.anyio
async def test_advance_idea_guard_error(db, mcp_server):
    """Advancing without required checks returns an error, not an exception."""
    plan = await create_plan(db)
    idea, checks = await create_idea_with_checks(db, plan.id, num_rules_per_layer=1)
    await db.flush()

    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("advance_idea", {"idea_id": str(idea.id)})
            assert "error" in result.data
    finally:
        _restore_session_factory(original, db_module)


@pytest.mark.anyio
async def test_invalidate_idea(db, mcp_server):
    idea = await create_idea(db)
    await db.flush()

    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("invalidate_idea", {
                "idea_id": str(idea.id),
                "reason": "Setup invalidated by news",
            })
            data = result.data
            assert data["state"] == "INVALIDATED"
    finally:
        _restore_session_factory(original, db_module)


@pytest.mark.anyio
async def test_list_journal_empty(db, mcp_server):
    original, db_module = _patch_session_factory(db)
    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool("list_journal", {})
            assert _list_result(result) == []
    finally:
        _restore_session_factory(original, db_module)
