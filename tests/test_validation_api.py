"""
Integration tests for the Plan Validation Engine API.

Uses a test HTTP client with the DB overridden and the AI provider mocked
via dependency injection.
"""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.routers.api.v1.validation import get_validation_ai_provider
from app.services.settings_service import generate_api_token
from tests.factories import create_plan, create_rule


class MockProvider:
    model = "mock"

    async def chat(self, system: str, messages: list[dict]) -> str:
        return json.dumps({
            "status": "TESTABLE",
            "proxy_type": "sma_trend",
            "proxy_params": {"period": 200, "timeframe": "1d", "direction_match": True},
            "confidence": 0.9,
            "interpretation_notes": "Mapped to SMA 200.",
        })


@pytest_asyncio.fixture
async def api_client(client: AsyncClient, db: AsyncSession):
    """Client with a valid API token and AI provider mocked."""
    from app.main import app

    token = await generate_api_token(db)
    await db.commit()

    def mock_provider_dep():
        return MockProvider()

    app.dependency_overrides[get_validation_ai_provider] = mock_provider_dep

    client.headers.update({"Authorization": f"Bearer {token}"})
    yield client

    app.dependency_overrides.pop(get_validation_ai_provider, None)


# ── POST /api/v1/validation/compile ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_compile_returns_201(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend rule")
    await db.commit()

    response = await api_client.post("/api/v1/validation/compile")
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_compile_returns_run_with_compiled_plan(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend rule")
    await db.commit()

    response = await api_client.post("/api/v1/validation/compile")
    data = response.json()

    assert "id" in data
    assert "compiled_plan" in data
    assert "feedback" in data
    assert len(data["compiled_plan"]["compiled_rules"]) == 1


@pytest.mark.asyncio
async def test_compile_includes_interpretability_score(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Rule")
    await db.commit()

    response = await api_client.post("/api/v1/validation/compile")
    data = response.json()

    assert "interpretability_score" in data["compiled_plan"]
    assert data["compiled_plan"]["interpretability_score"] == 100.0


@pytest.mark.asyncio
async def test_compile_requires_auth(client: AsyncClient, db: AsyncSession):
    response = await client.post("/api/v1/validation/compile")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_compile_with_unconfigured_ai_returns_422(client: AsyncClient, db: AsyncSession):
    from fastapi import HTTPException

    from app.main import app

    token = await generate_api_token(db)
    await db.commit()

    def broken_provider_dep():
        raise HTTPException(status_code=422, detail="No AI provider configured.")

    app.dependency_overrides[get_validation_ai_provider] = broken_provider_dep
    client.headers.update({"Authorization": f"Bearer {token}"})

    try:
        response = await client.post("/api/v1/validation/compile")
        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_validation_ai_provider, None)


# ── GET /api/v1/validation/runs ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_runs_empty_initially(api_client: AsyncClient, db: AsyncSession):
    await create_plan(db)
    await db.commit()

    response = await api_client.get("/api/v1/validation/runs")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_runs_returns_runs_after_compile(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Rule")
    await db.commit()

    await api_client.post("/api/v1/validation/compile")
    response = await api_client.get("/api/v1/validation/runs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "COMPLETED"
    assert data[0]["mode"] == "INTERPRETABILITY"


# ── GET /api/v1/validation/runs/{id} ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_run_returns_detail(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Rule")
    await db.commit()

    compile_resp = await api_client.post("/api/v1/validation/compile")
    run_id = compile_resp.json()["id"]

    response = await api_client.get(f"/api/v1/validation/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == run_id
    assert "compiled_plan" in data
    assert "feedback" in data


@pytest.mark.asyncio
async def test_get_run_returns_404_for_missing(api_client: AsyncClient, db: AsyncSession):
    await create_plan(db)
    await db.commit()

    response = await api_client.get(f"/api/v1/validation/runs/{uuid.uuid4()}")
    assert response.status_code == 404


# ── PUT /api/v1/validation/compiled-plans/{id}/rules/{rule_id}/confirm ───────

@pytest.mark.asyncio
async def test_confirm_rule_updates_interpretation(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="Trade with trend")
    await db.commit()

    compile_resp = await api_client.post("/api/v1/validation/compile")
    compiled_plan_id = compile_resp.json()["compiled_plan"]["id"]
    rule_id = str(rule.id)

    response = await api_client.put(
        f"/api/v1/validation/compiled-plans/{compiled_plan_id}/rules/{rule_id}/confirm",
        json={
            "status": "APPROXIMATED",
            "proxy_type": "ema_trend",
            "proxy_params": {"period": 50, "timeframe": "4h", "direction_match": True},
            "interpretation_notes": "User override: EMA 50 on 4H.",
        },
    )
    assert response.status_code == 200
    data = response.json()

    updated_rule = next(
        (r for r in data["compiled_rules"] if r["rule_id"] == rule_id), None
    )
    assert updated_rule is not None
    assert updated_rule["status"] == "APPROXIMATED"
    assert updated_rule["proxy"]["type"] == "ema_trend"
    assert updated_rule["user_confirmed"] is True
    assert updated_rule["interpretation_notes"] == "User override: EMA 50 on 4H."


@pytest.mark.asyncio
async def test_confirm_rule_returns_404_for_missing_plan(api_client: AsyncClient, db: AsyncSession):
    await create_plan(db)
    await db.commit()

    response = await api_client.put(
        f"/api/v1/validation/compiled-plans/{uuid.uuid4()}/rules/some-id/confirm",
        json={"status": "TESTABLE"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_confirm_rule_returns_404_for_missing_rule_id(api_client: AsyncClient, db: AsyncSession):
    """When the compiled plan exists but the rule_id is not in it, expect 404."""
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Real rule")
    await db.commit()

    compile_resp = await api_client.post("/api/v1/validation/compile")
    compiled_plan_id = compile_resp.json()["compiled_plan"]["id"]

    response = await api_client.put(
        f"/api/v1/validation/compiled-plans/{compiled_plan_id}/rules/{uuid.uuid4()}/confirm",
        json={"status": "TESTABLE"},
    )
    assert response.status_code == 404


# ── Feedback structure ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compile_feedback_has_expected_keys(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Rule")
    await db.commit()

    response = await api_client.post("/api/v1/validation/compile")
    feedback = response.json()["feedback"]

    assert "interpretability_score" in feedback
    assert "replay_readiness" in feedback
    assert "summary" in feedback
    assert "layer_breakdown" in feedback
    assert "coherence_warnings" in feedback
    assert "refinement_suggestions" in feedback


@pytest.mark.asyncio
async def test_compile_behavioral_rule_not_testable_in_response(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="BEHAVIORAL", name="No revenge trading")
    await db.commit()

    response = await api_client.post("/api/v1/validation/compile")
    compiled_rules = response.json()["compiled_plan"]["compiled_rules"]

    behavioral = next((r for r in compiled_rules if r["layer"] == "BEHAVIORAL"), None)
    assert behavioral is not None
    assert behavioral["status"] == "NOT_TESTABLE"
    assert behavioral["proxy"] is None
