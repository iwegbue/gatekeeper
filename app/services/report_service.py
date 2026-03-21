"""
Report service — discipline metrics, trade stats, rule analysis.

Queries run against journal_entries and trades to produce discipline
analytics for the reports page.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journal import JournalEntry
from app.models.trade import Trade
from app.models.enums import TradeState


async def get_trade_stats(db: AsyncSession) -> dict:
    """Basic trade stats: total, wins, losses, avg R, best/worst R."""
    result = await db.execute(
        select(Trade).where(Trade.state == TradeState.CLOSED.value)
    )
    trades = list(result.scalars().all())

    if not trades:
        return {
            "total": 0, "wins": 0, "losses": 0, "breakeven": 0,
            "win_rate": 0.0, "avg_r": 0.0, "best_r": None, "worst_r": None,
            "expectancy": 0.0,
        }

    r_values = [float(t.r_multiple) for t in trades if t.r_multiple is not None]
    wins = sum(1 for r in r_values if r > 0)
    losses = sum(1 for r in r_values if r < 0)
    breakeven = sum(1 for r in r_values if r == 0)
    total_with_r = len(r_values)

    avg_r = round(sum(r_values) / total_with_r, 2) if total_with_r else 0.0
    win_rate = round(wins / total_with_r * 100, 1) if total_with_r else 0.0

    # Expectancy = avg win × win_rate + avg loss × loss_rate
    avg_win = sum(r for r in r_values if r > 0) / wins if wins else 0
    avg_loss = sum(r for r in r_values if r < 0) / losses if losses else 0
    loss_rate = (losses / total_with_r) if total_with_r else 0
    expectancy = round(avg_win * (win_rate / 100) + avg_loss * loss_rate, 3)

    return {
        "total": len(trades),
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "win_rate": win_rate,
        "avg_r": avg_r,
        "best_r": round(max(r_values), 2) if r_values else None,
        "worst_r": round(min(r_values), 2) if r_values else None,
        "expectancy": expectancy,
    }


async def get_grade_distribution(db: AsyncSession) -> dict[str, int]:
    """Count of closed trades by grade."""
    result = await db.execute(
        select(Trade.grade, func.count(Trade.id).label("count"))
        .where(Trade.state == TradeState.CLOSED.value)
        .group_by(Trade.grade)
    )
    rows = result.all()
    dist: dict[str, int] = {"A": 0, "B": 0, "C": 0}
    for row in rows:
        if row.grade in dist:
            dist[row.grade] = row.count
    return dist


async def get_plan_adherence_stats(db: AsyncSession) -> dict:
    """Average and recent plan adherence from completed journal entries."""
    result = await db.execute(
        select(JournalEntry.plan_adherence_pct)
        .where(JournalEntry.plan_adherence_pct.is_not(None))
        .order_by(JournalEntry.created_at.desc())
    )
    values = [row[0] for row in result.all()]

    if not values:
        return {"avg": 0, "recent": [], "trend": 0}

    avg = round(sum(values) / len(values), 1)
    recent = values[:10]
    trend = (recent[0] - recent[-1]) if len(recent) >= 2 else 0

    return {"avg": avg, "recent": recent, "trend": trend}


async def get_rule_violation_frequency(db: AsyncSession, limit: int = 10) -> list[dict]:
    """
    Most frequently violated required rules (from journal entries).
    Returns list of {rule_name: str, count: int} sorted by count desc.
    """
    result = await db.execute(
        select(JournalEntry.rule_violations)
        .where(JournalEntry.rule_violations.is_not(None))
    )
    rows = result.scalars().all()

    counts: dict[str, int] = {}
    for violations_json in rows:
        if not violations_json:
            continue
        violated = violations_json.get("violated", [])
        for rule_name in violated:
            counts[rule_name] = counts.get(rule_name, 0) + 1

    sorted_violations = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [{"rule_name": name, "count": cnt} for name, cnt in sorted_violations[:limit]]


async def get_discipline_score(db: AsyncSession) -> float:
    """
    Composite discipline score (0–100):
    - 50% weight: average plan adherence
    - 30% weight: % of trades with grade A or B
    - 20% weight: recent improvement trend (capped at +/-10 pts)
    """
    adherence_stats = await get_plan_adherence_stats(db)
    grade_dist = await get_grade_distribution(db)

    adherence_component = adherence_stats["avg"] * 0.5

    total_graded = sum(grade_dist.values())
    ab_rate = (grade_dist["A"] + grade_dist["B"]) / total_graded * 100 if total_graded else 0
    grade_component = ab_rate * 0.3

    # Trend: normalize to 0–100
    trend = adherence_stats["trend"]
    trend_normalized = max(0, min(100, 50 + trend * 5))  # ±10 trend maps to ±50 pts
    trend_component = trend_normalized * 0.2

    score = adherence_component + grade_component + trend_component
    return round(min(100.0, max(0.0, score)), 1)


async def get_r_multiple_by_grade(db: AsyncSession) -> dict[str, list[float]]:
    """R-multiples grouped by setup grade, for scatter/box plots."""
    result = await db.execute(
        select(Trade.grade, Trade.r_multiple)
        .where(
            Trade.state == TradeState.CLOSED.value,
            Trade.r_multiple.is_not(None),
        )
    )
    buckets: dict[str, list[float]] = {"A": [], "B": [], "C": []}
    for row in result.all():
        if row.grade in buckets and row.r_multiple is not None:
            buckets[row.grade].append(float(row.r_multiple))
    return buckets


async def get_consistency_trend(db: AsyncSession, days: int = 30) -> list[dict]:
    """
    Daily discipline snapshots over the last N days.
    Returns list of {date: str, adherence: float} for Chart.js.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(JournalEntry.created_at, JournalEntry.plan_adherence_pct)
        .where(
            JournalEntry.created_at >= cutoff,
            JournalEntry.plan_adherence_pct.is_not(None),
        )
        .order_by(JournalEntry.created_at)
    )
    rows = result.all()
    return [
        {
            "date": row.created_at.strftime("%Y-%m-%d"),
            "adherence": row.plan_adherence_pct,
        }
        for row in rows
    ]
