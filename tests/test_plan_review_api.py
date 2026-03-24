"""
Integration tests for the Plan Review API.

Uses a test HTTP client with the DB overridden and the AI provider mocked
via dependency injection.
"""

import json
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idea import Idea
from app.models.journal import JournalEntry
from app.routers.api.v1.plan_review import _get_ai_provider
from app.services.settings_service import generate_api_token, update_settings
from tests.factories import create_plan, create_rule


class MockProvider:
    model = "mock"

    async def chat(self, system: str, messages: list[dict]) -> str:
        return json.dumps(
            {
                "summary": "Plan performing as expected.",
                "rule_performance": [],
                "assumptions_held": [],
                "assumptions_challenged": [],
                "suggested_changes": [],
                "overall_verdict": "keep",
            }
        )


@pytest_asyncio.fixture
async def api_client(client: AsyncClient, db: AsyncSession):
    """Client with a valid API token and AI provider mocked."""
    from app.main import app

    token = await generate_api_token(db)
    await db.commit()

    def mock_provider_dep():
        return MockProvider()

    app.dependency_overrides[_get_ai_provider] = mock_provider_dep
    client.headers.update({"Authorization": f"Bearer {token}"})
    yield client
    app.dependency_overrides.pop(_get_ai_provider, None)


async def _seed_completed_journal(db: AsyncSession, plan_id: uuid.UUID, r_multiple: float = 1.0):
    idea = Idea(instrument="EURUSD", direction="LONG", state="CLOSED", plan_id=plan_id)
    db.add(idea)
    await db.flush()

    entry = JournalEntry(
        trade_id=uuid.uuid4(),
        idea_id=idea.id,
        status="COMPLETED",
        trade_summary={"instrument": "EURUSD", "direction": "LONG", "grade": "A", "r_multiple": r_multiple},
        rule_violations={"violated": []},
    )
    db.add(entry)
    await db.flush()
    return entry


# ── POST /api/v1/plans/{plan_id}/review/run ───────────────────────────────────


@pytest.mark.asyncio
async def test_run_review_returns_201(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend Rule")
    await update_settings(db, plan_review_sample_size=1)
    await _seed_completed_journal(db, plan.id)

    response = await api_client.post(f"/api/v1/plans/{plan.id}/review/run")

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["plan_id"] == str(plan.id)
    assert "report" in data


@pytest.mark.asyncio
async def test_run_review_requires_auth(client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    response = await client.post(f"/api/v1/plans/{plan.id}/review/run")
    assert response.status_code == 401


# ── GET /api/v1/plans/{plan_id}/review/runs ──────────────────────────────────


@pytest.mark.asyncio
async def test_list_reviews_empty_initially(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    response = await api_client.get(f"/api/v1/plans/{plan.id}/review/runs")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_reviews_after_run(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend Rule")
    await update_settings(db, plan_review_sample_size=1)
    await _seed_completed_journal(db, plan.id)

    await api_client.post(f"/api/v1/plans/{plan.id}/review/run")

    response = await api_client.get(f"/api/v1/plans/{plan.id}/review/runs")
    assert response.status_code == 200
    assert len(response.json()) == 1


# ── GET /api/v1/plans/{plan_id}/review/runs/{review_id} ──────────────────────


@pytest.mark.asyncio
async def test_get_review_returns_detail(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend Rule")
    await update_settings(db, plan_review_sample_size=1)
    await _seed_completed_journal(db, plan.id)

    run_response = await api_client.post(f"/api/v1/plans/{plan.id}/review/run")
    review_id = run_response.json()["id"]

    response = await api_client.get(f"/api/v1/plans/{plan.id}/review/runs/{review_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == review_id
    assert data["report"] is not None


@pytest.mark.asyncio
async def test_get_review_returns_404_for_missing(api_client: AsyncClient, db: AsyncSession):
    plan = await create_plan(db)
    response = await api_client.get(f"/api/v1/plans/{plan.id}/review/runs/{uuid.uuid4()}")
    assert response.status_code == 404
