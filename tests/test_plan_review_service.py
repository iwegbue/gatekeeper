"""
Unit tests for plan_review_service.

Tests run against a real throwaway Postgres DB.
The AI provider is mocked.
"""

import json
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idea import Idea
from app.models.journal import JournalEntry
from app.services import plan_review_service
from app.services.settings_service import update_settings
from tests.factories import create_plan, create_rule


class MockProvider:
    model = "mock"

    async def chat(self, system: str, messages: list[dict]) -> str:
        return json.dumps(
            {
                "summary": "Plan is performing well overall.",
                "rule_performance": [
                    {
                        "rule_name": "Trend Rule",
                        "layer": "CONTEXT",
                        "adherence_pct": 80.0,
                        "win_rate_when_followed": 0.6,
                        "win_rate_when_skipped": 0.3,
                        "verdict": "keep",
                        "notes": "Strong positive impact.",
                    }
                ],
                "assumptions_held": ["Trend following works in this market."],
                "assumptions_challenged": ["Volume filter may not be necessary."],
                "suggested_changes": ["Relax the volume requirement."],
                "overall_verdict": "refine",
            }
        )


class FailingProvider:
    model = "mock"

    async def chat(self, system: str, messages: list[dict]) -> str:
        raise RuntimeError("AI provider unavailable")


async def _create_completed_journal(
    db: AsyncSession,
    plan_id: uuid.UUID,
    rule_name: str = "Trend Rule",
    r_multiple: float = 1.5,
    violated: bool = False,
) -> JournalEntry:
    idea = Idea(
        instrument="EURUSD",
        direction="LONG",
        state="CLOSED",
        plan_id=plan_id,
    )
    db.add(idea)
    await db.flush()

    entry = JournalEntry(
        trade_id=uuid.uuid4(),
        idea_id=idea.id,
        status="COMPLETED",
        trade_summary={
            "instrument": "EURUSD",
            "direction": "LONG",
            "grade": "A",
            "r_multiple": r_multiple,
        },
        rule_violations={"violated": [rule_name] if violated else []},
        what_went_well="Good entry.",
        what_went_wrong=None,
        lessons_learned=None,
    )
    db.add(entry)
    await db.flush()
    return entry


# ── Eligibility ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_review_not_eligible_when_insufficient_trades(db: AsyncSession):
    plan = await create_plan(db)
    await update_settings(db, plan_review_sample_size=20)
    eligibility = await plan_review_service.get_review_eligibility(db, plan.id)
    assert eligibility["eligible"] is False
    assert eligibility["completed_count"] == 0
    assert eligibility["required"] == 20


@pytest.mark.asyncio
async def test_review_eligible_when_enough_completed_journals(db: AsyncSession):
    plan = await create_plan(db)
    await update_settings(db, plan_review_sample_size=2)

    for _ in range(2):
        await _create_completed_journal(db, plan.id)

    eligibility = await plan_review_service.get_review_eligibility(db, plan.id)
    assert eligibility["eligible"] is True
    assert eligibility["completed_count"] == 2


@pytest.mark.asyncio
async def test_eligibility_last_review_at_is_none_initially(db: AsyncSession):
    plan = await create_plan(db)
    eligibility = await plan_review_service.get_review_eligibility(db, plan.id)
    assert eligibility["last_review_at"] is None


# ── run_plan_review ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_review_creates_plan_review_record(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend Rule")
    await update_settings(db, plan_review_sample_size=1)
    await _create_completed_journal(db, plan.id)

    review = await plan_review_service.run_plan_review(db, MockProvider(), plan.id)

    assert review.plan_id == plan.id
    assert review.status == "COMPLETED"
    assert review.trade_count == 1


@pytest.mark.asyncio
async def test_run_review_report_has_expected_keys(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend Rule")
    await update_settings(db, plan_review_sample_size=1)
    await _create_completed_journal(db, plan.id)

    review = await plan_review_service.run_plan_review(db, MockProvider(), plan.id)

    report = review.report
    assert report is not None
    for key in ("summary", "sample_size", "win_rate", "avg_r", "rule_performance",
                "assumptions_held", "assumptions_challenged", "suggested_changes", "overall_verdict"):
        assert key in report, f"Missing key: {key}"

    assert report["sample_size"] == 1
    assert isinstance(report["rule_performance"], list)


@pytest.mark.asyncio
async def test_run_review_handles_ai_failure_gracefully(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend Rule")
    await update_settings(db, plan_review_sample_size=1)
    await _create_completed_journal(db, plan.id)

    review = await plan_review_service.run_plan_review(db, FailingProvider(), plan.id)

    assert review.status == "FAILED"
    assert review.error_message is not None
    assert review.report is None


@pytest.mark.asyncio
async def test_run_review_fails_when_no_entries(db: AsyncSession):
    plan = await create_plan(db)
    await update_settings(db, plan_review_sample_size=1)

    review = await plan_review_service.run_plan_review(db, MockProvider(), plan.id)

    assert review.status == "FAILED"
    assert "No completed journal entries" in (review.error_message or "")


@pytest.mark.asyncio
async def test_run_review_win_rate_computed_correctly(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend Rule")
    await update_settings(db, plan_review_sample_size=4)

    # 2 wins (r > 0), 2 losses (r < 0) → win rate = 0.5
    for r in [1.0, 2.0, -0.5, -1.0]:
        await _create_completed_journal(db, plan.id, r_multiple=r)

    review = await plan_review_service.run_plan_review(db, MockProvider(), plan.id)

    assert review.status == "COMPLETED"
    assert review.report["win_rate"] == 0.5


# ── list / get ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_plan_reviews_empty(db: AsyncSession):
    plan = await create_plan(db)
    reviews = await plan_review_service.list_plan_reviews(db, plan.id)
    assert reviews == []


@pytest.mark.asyncio
async def test_list_plan_reviews_after_run(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend Rule")
    await update_settings(db, plan_review_sample_size=1)
    await _create_completed_journal(db, plan.id)

    await plan_review_service.run_plan_review(db, MockProvider(), plan.id)

    reviews = await plan_review_service.list_plan_reviews(db, plan.id)
    assert len(reviews) == 1


@pytest.mark.asyncio
async def test_get_plan_review_returns_none_for_unknown(db: AsyncSession):
    result = await plan_review_service.get_plan_review(db, uuid.uuid4())
    assert result is None
