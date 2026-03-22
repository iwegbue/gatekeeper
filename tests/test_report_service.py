"""
Tests for report_service — trade stats, grade distribution, adherence, violations, discipline score.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TradeState
from app.services import journal_service, report_service
from tests.factories import create_idea, create_trade


async def _closed_trade(db, instrument="EURUSD", direction="LONG", entry=1.1000, sl=1.0950, exit_=1.1100, grade="A"):
    """Helper: create a closed trade directly."""
    idea = await create_idea(db, instrument=instrument, direction=direction)
    trade = await create_trade(
        db,
        idea.id,
        instrument=instrument,
        direction=direction,
        entry_price=entry,
        sl_price=sl,
        grade=grade,
        state=TradeState.CLOSED.value,
    )
    # Set exit fields
    from datetime import datetime, timezone

    from app.services.trade_service import _compute_r_multiple

    trade.exit_price = exit_
    trade.exit_time = datetime.now(timezone.utc)
    trade.r_multiple = _compute_r_multiple(direction, entry, exit_, sl)
    await db.flush()
    return idea, trade


# ── get_trade_stats ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trade_stats_empty_database(db: AsyncSession):
    stats = await report_service.get_trade_stats(db)
    assert stats["total"] == 0
    assert stats["win_rate"] == 0.0
    assert stats["avg_r"] == 0.0
    assert stats["best_r"] is None
    assert stats["worst_r"] is None


@pytest.mark.asyncio
async def test_trade_stats_win_rate(db: AsyncSession):
    # 3 wins, 1 loss
    await _closed_trade(db, instrument="EURUSD", entry=1.1000, sl=1.0950, exit_=1.1100)
    await _closed_trade(db, instrument="GBPUSD", entry=1.2000, sl=1.1950, exit_=1.2100)
    await _closed_trade(db, instrument="USDJPY", entry=130.0, sl=129.5, exit_=130.5)
    await _closed_trade(db, instrument="AUDUSD", entry=0.7000, sl=0.6950, exit_=0.6970)

    stats = await report_service.get_trade_stats(db)
    assert stats["total"] == 4
    assert stats["wins"] == 3
    assert stats["losses"] == 1
    assert stats["win_rate"] == 75.0


@pytest.mark.asyncio
async def test_trade_stats_avg_r(db: AsyncSession):
    # 2R win + (-1R) loss = 1R avg / 2 = 0.5R avg
    await _closed_trade(db, instrument="EURUSD", entry=1.1000, sl=1.0900, exit_=1.1200)  # 2R
    await _closed_trade(db, instrument="GBPUSD", entry=1.2000, sl=1.1900, exit_=1.1900)  # -1R
    stats = await report_service.get_trade_stats(db)
    assert stats["avg_r"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_trade_stats_excludes_open_trades(db: AsyncSession):
    idea = await create_idea(db)
    await create_trade(db, idea.id, state=TradeState.OPEN.value)
    stats = await report_service.get_trade_stats(db)
    assert stats["total"] == 0


# ── get_grade_distribution ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_grade_distribution_empty(db: AsyncSession):
    dist = await report_service.get_grade_distribution(db)
    assert dist == {"A": 0, "B": 0, "C": 0}


@pytest.mark.asyncio
async def test_grade_distribution_counts(db: AsyncSession):
    await _closed_trade(db, instrument="EURUSD", grade="A")
    await _closed_trade(db, instrument="GBPUSD", grade="A")
    await _closed_trade(db, instrument="USDJPY", grade="B")
    await _closed_trade(db, instrument="AUDUSD", grade="C")

    dist = await report_service.get_grade_distribution(db)
    assert dist["A"] == 2
    assert dist["B"] == 1
    assert dist["C"] == 1


# ── get_plan_adherence_stats ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_adherence_stats_empty(db: AsyncSession):
    stats = await report_service.get_plan_adherence_stats(db)
    assert stats["avg"] == 0
    assert stats["recent"] == []


@pytest.mark.asyncio
async def test_adherence_stats_average(db: AsyncSession):
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id, state=TradeState.CLOSED.value)
    await journal_service.create_draft(db, trade, plan_adherence_pct=80)

    idea2 = await create_idea(db)
    trade2 = await create_trade(db, idea2.id, state=TradeState.CLOSED.value)
    await journal_service.create_draft(db, trade2, plan_adherence_pct=60)

    stats = await report_service.get_plan_adherence_stats(db)
    assert stats["avg"] == 70.0


# ── get_rule_violation_frequency ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_violation_frequency_empty(db: AsyncSession):
    violations = await report_service.get_rule_violation_frequency(db)
    assert violations == []


@pytest.mark.asyncio
async def test_violation_frequency_counts(db: AsyncSession):
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id, state=TradeState.CLOSED.value)
    await journal_service.create_draft(
        db,
        trade,
        rule_violations=["Rule A", "Rule B", "Rule A"],
    )

    idea2 = await create_idea(db)
    trade2 = await create_trade(db, idea2.id, state=TradeState.CLOSED.value)
    await journal_service.create_draft(
        db,
        trade2,
        rule_violations=["Rule A"],
    )

    violations = await report_service.get_rule_violation_frequency(db)
    # Service counts total occurrences across all entries: 2 (first entry) + 1 (second) = 3
    rule_a = next((v for v in violations if v["rule_name"] == "Rule A"), None)
    assert rule_a is not None
    assert rule_a["count"] == 3


@pytest.mark.asyncio
async def test_violation_frequency_sorted_desc(db: AsyncSession):
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id, state=TradeState.CLOSED.value)
    await journal_service.create_draft(
        db,
        trade,
        rule_violations=["Rule Z"],
    )
    for i in range(3):
        idea_i = await create_idea(db)
        trade_i = await create_trade(db, idea_i.id, state=TradeState.CLOSED.value)
        await journal_service.create_draft(
            db,
            trade_i,
            rule_violations=["Rule A"],
        )

    violations = await report_service.get_rule_violation_frequency(db)
    assert violations[0]["rule_name"] == "Rule A"
    assert violations[0]["count"] == 3


# ── get_discipline_score ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discipline_score_no_data(db: AsyncSession):
    """With no data, adherence=0, grade_component=0, trend contributes 10 (neutral: 50*0.2)."""
    score = await report_service.get_discipline_score(db)
    assert score == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_discipline_score_high_with_good_adherence(db: AsyncSession):
    """100% adherence + all A trades → high score."""
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id, grade="A", state=TradeState.CLOSED.value)
    await journal_service.create_draft(db, trade, plan_adherence_pct=100)

    score = await report_service.get_discipline_score(db)
    # 50% from adherence (100 * 0.5 = 50) + 30% from grade (100 * 0.3 = 30) + trend ≈ 10
    assert score > 70


@pytest.mark.asyncio
async def test_discipline_score_bounded_0_100(db: AsyncSession):
    score = await report_service.get_discipline_score(db)
    assert 0.0 <= score <= 100.0


# ── get_consistency_trend ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consistency_trend_empty(db: AsyncSession):
    trend = await report_service.get_consistency_trend(db)
    assert trend == []


@pytest.mark.asyncio
async def test_consistency_trend_format(db: AsyncSession):
    idea = await create_idea(db)
    trade = await create_trade(db, idea.id, state=TradeState.CLOSED.value)
    await journal_service.create_draft(db, trade, plan_adherence_pct=75)

    trend = await report_service.get_consistency_trend(db)
    assert len(trend) == 1
    assert "date" in trend[0]
    assert "adherence" in trend[0]
    assert trend[0]["adherence"] == 75


# ── get_r_multiple_by_grade ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_r_by_grade_empty(db: AsyncSession):
    r_by_grade = await report_service.get_r_multiple_by_grade(db)
    assert r_by_grade == {"A": [], "B": [], "C": []}


@pytest.mark.asyncio
async def test_r_by_grade_groups_correctly(db: AsyncSession):
    await _closed_trade(db, instrument="EURUSD", grade="A", entry=1.1000, sl=1.0950, exit_=1.1100)
    await _closed_trade(db, instrument="GBPUSD", grade="B", entry=1.2000, sl=1.1950, exit_=1.2100)

    r_by_grade = await report_service.get_r_multiple_by_grade(db)
    assert len(r_by_grade["A"]) == 1
    assert len(r_by_grade["B"]) == 1
    assert len(r_by_grade["C"]) == 0
    assert r_by_grade["A"][0] == pytest.approx(2.0)
