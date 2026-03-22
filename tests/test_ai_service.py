"""
Tests for ai_service — prompt building and feature dispatching.
Uses a mock provider; no real API calls in CI.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import ai_service, checklist_service
from tests.factories import create_idea, create_plan, create_rule


class MockProvider:
    """Mock AI provider that echoes back a canned response."""

    def __init__(self, response: str = "AI response"):
        self._response = response
        self.model = "mock-model"
        self.last_system = None
        self.last_messages = None

    async def chat(self, system: str, messages: list[dict]) -> str:
        self.last_system = system
        self.last_messages = messages
        return self._response


# ── _build_plan_context ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_plan_context_includes_rule_names(db: AsyncSession):
    plan = await create_plan(db, name="My Strategy")
    await create_rule(db, plan.id, layer="CONTEXT", name="Trend aligned", rule_type="REQUIRED")
    await create_rule(db, plan.id, layer="SETUP", name="Order block present", rule_type="REQUIRED")

    context = await ai_service._build_plan_context(db)
    assert "My Strategy" in context
    assert "Trend aligned" in context
    assert "Order block present" in context
    assert "CONTEXT" in context
    assert "SETUP" in context


@pytest.mark.asyncio
async def test_build_plan_context_includes_rule_types(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, name="Must check", rule_type="REQUIRED")
    await create_rule(db, plan.id, name="Advisory note", rule_type="ADVISORY")

    context = await ai_service._build_plan_context(db)
    assert "REQUIRED" in context
    assert "ADVISORY" in context


# ── _build_idea_context ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_idea_context_includes_idea_fields(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, name="Checked rule", layer="CONTEXT", rule_type="REQUIRED")
    idea = await create_idea(db, instrument="GBPUSD", direction="SHORT")
    checks = await checklist_service.initialize_checks(db, idea.id, plan.id)
    await checklist_service.toggle_check(db, checks[0].id, True)

    context = await ai_service._build_idea_context(db, idea.id)
    assert "GBPUSD" in context
    assert "SHORT" in context
    assert "✓" in context  # checked rule


@pytest.mark.asyncio
async def test_build_idea_context_unchecked_rules(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, name="Unchecked", layer="CONTEXT", rule_type="REQUIRED")
    idea = await create_idea(db)
    await checklist_service.initialize_checks(db, idea.id, plan.id)

    context = await ai_service._build_idea_context(db, idea.id)
    assert "✗" in context


# ── idea_review ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idea_review_calls_provider(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, name="Trend check", layer="CONTEXT")
    idea = await create_idea(db)
    await checklist_service.initialize_checks(db, idea.id, plan.id)

    provider = MockProvider("Good analysis of the setup.")
    result = await ai_service.idea_review(db, provider, idea.id)
    assert result == "Good analysis of the setup."
    assert provider.last_system is not None
    assert provider.last_messages is not None


@pytest.mark.asyncio
async def test_idea_review_saves_analysis(db: AsyncSession):
    plan = await create_plan(db)
    await create_rule(db, plan.id, name="Rule", layer="CONTEXT")
    idea = await create_idea(db)
    await checklist_service.initialize_checks(db, idea.id, plan.id)

    provider = MockProvider("Analysis saved.")
    await ai_service.idea_review(db, provider, idea.id)

    from sqlalchemy import select

    from app.models.ai_analysis import AIAnalysis
    result = await db.execute(select(AIAnalysis).where(AIAnalysis.trigger == "idea_review"))
    analyses = list(result.scalars().all())
    assert len(analyses) == 1
    assert analyses[0].reasoning == "Analysis saved."
    assert analyses[0].idea_id == idea.id


# ── journal_coach ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_journal_coach_handles_missing_entry(db: AsyncSession):
    import uuid
    provider = MockProvider("coaching")
    result = await ai_service.journal_coach(db, provider, uuid.uuid4())
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_journal_coach_calls_provider_with_trade_data(db: AsyncSession):
    from app.models.enums import IdeaState
    from app.services import journal_service, trade_service

    idea = await create_idea(db, state=IdeaState.ENTRY_PERMITTED.value)
    trade = await trade_service.open_trade(db, idea, entry_price=1.1000, sl_price=1.0950)
    await trade_service.close_trade(db, trade, exit_price=1.1100)
    entry = await journal_service.create_draft(db, trade, plan_adherence_pct=75)

    provider = MockProvider("Great discipline shown.")
    result = await ai_service.journal_coach(db, provider, entry.id)
    assert result == "Great discipline shown."
    # The message sent to provider should include trade info
    content = provider.last_messages[0]["content"]
    assert "1.10" in content or "EURUSD" in content.upper() or "75" in content


# ── plan_builder_chat ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_plan_builder_chat_returns_response(db: AsyncSession):
    provider = MockProvider("Let's define your CONTEXT rules first.")
    conversation = [{"role": "user", "content": "I trade breakouts on EURUSD"}]
    result = await ai_service.plan_builder_chat(db, provider, conversation)
    assert result == "Let's define your CONTEXT rules first."


@pytest.mark.asyncio
async def test_plan_builder_chat_passes_conversation(db: AsyncSession):
    provider = MockProvider("Follow-up response.")
    conversation = [
        {"role": "user", "content": "I trade ICT"},
        {"role": "assistant", "content": "Tell me more"},
        {"role": "user", "content": "I look for order blocks"},
    ]
    await ai_service.plan_builder_chat(db, provider, conversation)
    # All 3 messages should be passed to provider
    assert len(provider.last_messages) == 3


# ── rule_clarity_check ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rule_clarity_check_returns_feedback(db: AsyncSession):
    provider = MockProvider("This rule is vague. Suggest: price must close above the 50 SMA on H4.")
    result = await ai_service.rule_clarity_check(
        db, provider,
        rule_name="Good trend",
        rule_description=None,
        layer="CONTEXT",
    )
    assert "vague" in result


@pytest.mark.asyncio
async def test_rule_clarity_includes_description_in_prompt(db: AsyncSession):
    provider = MockProvider("feedback")
    await ai_service.rule_clarity_check(
        db, provider,
        rule_name="Zone touch",
        rule_description="Price must be near a key level",
        layer="SETUP",
    )
    content = provider.last_messages[0]["content"]
    assert "near a key level" in content
    assert "SETUP" in content
