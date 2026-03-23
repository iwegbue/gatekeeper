"""
Replay Service — orchestration layer.

Ties together data_loader (async, DB) and replay_engine (pure Python)
to produce a completed ValidationRun with summary_metrics populated.
"""

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.validation.validation_run import ValidationRun
from app.services.validation.data_loader import DataLoaderError, fetch_and_store_ohlc, load_bars_for_snapshot
from app.services.validation.replay_engine import run_replay

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────


async def create_replay_run(
    db: AsyncSession,
    compiled_plan_id: uuid.UUID,
    symbol: str,
    timeframe: str,
    start_date: date,
    end_date: date,
    direction: str = "BOTH",
) -> ValidationRun:
    """Create a PENDING ValidationRun in REPLAY mode and flush to DB."""
    run = ValidationRun(
        id=uuid.uuid4(),
        compiled_plan_id=compiled_plan_id,
        status="PENDING",
        mode="REPLAY",
        settings={
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "direction": direction.upper(),
        },
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()
    return run


async def run_replay_for_run(db: AsyncSession, run_id: uuid.UUID) -> ValidationRun:
    """
    Execute the full replay pipeline for an existing PENDING replay run.

    Steps:
      1. Fetch run + compiled_plan
      2. Mark status = REPLAYING
      3. Fetch + store OHLC data
      4. Load bars from DB
      5. Run replay engine (sync)
      6. Compute and store summary_metrics
      7. Mark status = COMPLETED

    On any error: status = FAILED, error_message populated, then re-raise.
    """
    from app.models.validation.compiled_plan import CompiledPlan

    run = await db.get(ValidationRun, run_id)
    if run is None:
        raise ValueError(f"ValidationRun {run_id} not found")

    compiled_plan = await db.get(CompiledPlan, run.compiled_plan_id)
    if compiled_plan is None:
        raise ValueError(f"CompiledPlan {run.compiled_plan_id} not found")

    settings = run.settings or {}
    symbol = settings.get("symbol", "EURUSD")
    timeframe = settings.get("timeframe", "1d")
    direction = settings.get("direction", "BOTH")
    start_date = date.fromisoformat(settings["start_date"])
    end_date = date.fromisoformat(settings["end_date"])

    run.status = "REPLAYING"
    await db.flush()

    try:
        # Fetch + store market data
        data_snapshot_id = await fetch_and_store_ohlc(db, symbol, timeframe, start_date, end_date)

        # Load plain dicts for the engine
        bars = await load_bars_for_snapshot(db, data_snapshot_id)

        if not bars:
            raise DataLoaderError(f"No bars loaded from snapshot {data_snapshot_id}")

        compiled_rules = compiled_plan.compiled_rules or []
        result = run_replay(compiled_rules, bars, settings)

        run.summary_metrics = _compute_summary_metrics(result, settings, bars, data_snapshot_id)
        run.data_snapshot_id = data_snapshot_id
        run.status = "COMPLETED"
        run.completed_at = datetime.now(timezone.utc)
        await db.flush()

        logger.info(
            "Replay run %s completed: %d trades, win_rate=%.1f%%",
            run_id,
            run.summary_metrics.get("total_trades", 0),
            (run.summary_metrics.get("win_rate") or 0) * 100,
        )

    except Exception as exc:
        logger.exception("Replay run %s failed: %s", run_id, exc)
        run.status = "FAILED"
        run.error_message = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        await db.flush()
        raise

    return run


# ── Private helpers ────────────────────────────────────────────────────────────


def _compute_summary_metrics(
    result: dict,
    settings: dict,
    bars: list[dict],
    data_snapshot_id: uuid.UUID,
) -> dict:
    """Produce the full summary_metrics JSONB dict from the replay result."""
    trades: list[dict] = result.get("trades", [])

    total = len(trades)
    winning = [t for t in trades if (t.get("r_multiple") or 0) > 0]
    losing = [t for t in trades if (t.get("r_multiple") or 0) < 0]

    win_count = len(winning)
    loss_count = len(losing)

    win_rate = win_count / total if total > 0 else 0.0

    gross_profit = sum(t["r_multiple"] for t in winning)
    gross_loss = abs(sum(t["r_multiple"] for t in losing))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    total_r = sum(t.get("r_multiple") or 0 for t in trades)
    avg_r = total_r / total if total > 0 else None

    r_values = [t.get("r_multiple") or 0 for t in trades]
    max_r = max(r_values) if r_values else 0.0
    min_r = min(r_values) if r_values else 0.0

    max_consec_losses = _max_consecutive_losses(trades)
    max_drawdown_r = _max_drawdown(trades)

    # Optional score averages
    all_scores = [t.get("optional_score") or 0 for t in trades]
    win_scores = [t.get("optional_score") or 0 for t in winning]
    loss_scores = [t.get("optional_score") or 0 for t in losing]

    avg_optional = sum(all_scores) / len(all_scores) if all_scores else 0.0
    avg_optional_winners = sum(win_scores) / len(win_scores) if win_scores else 0.0
    avg_optional_losers = sum(loss_scores) / len(loss_scores) if loss_scores else 0.0

    bars_evaluated = result.get("bars_evaluated", len(bars))
    bars_with_signal = result.get("bars_with_signal", 0)
    signal_rate = bars_with_signal / bars_evaluated if bars_evaluated > 0 else 0.0

    # Exit reason and management event tallies
    exit_reasons: dict[str, int] = {"TP_HIT": 0, "SL_HIT": 0, "TRAILING_STOP": 0, "END_OF_DATA": 0}
    mgmt_events: dict[str, int] = {"PARTIAL_TAKEN": 0, "BE_MOVED": 0, "TRAILING_ACTIVATED": 0}
    for t in trades:
        reason = str(t.get("exit_reason", "")).upper()
        if reason in exit_reasons:
            exit_reasons[reason] += 1
        for event in t.get("management_events", []):
            ev = str(event).upper()
            if ev in mgmt_events:
                mgmt_events[ev] += 1

    # Data coverage warning
    actual_start = result.get("actual_start")
    actual_end = result.get("actual_end")
    bars_loaded = result.get("bars_loaded", len(bars))

    start_date_str = settings.get("start_date", "")
    end_date_str = settings.get("end_date", "")
    days_requested = 0
    if start_date_str and end_date_str:
        try:
            d_start = date.fromisoformat(start_date_str)
            d_end = date.fromisoformat(end_date_str)
            days_requested = (d_end - d_start).days
        except ValueError:
            pass

    data_coverage_warning: str | None = None
    if days_requested > 0 and bars_loaded < days_requested * 0.80 * 0.5:
        data_coverage_warning = (
            f"Only {bars_loaded} bars loaded for {days_requested} requested days "
            f"({settings.get('symbol')}/{settings.get('timeframe')}). "
            "Coverage may be below 80% of expectation."
        )

    return {
        "total_trades": total,
        "winning_trades": win_count,
        "losing_trades": loss_count,
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
        "total_r": round(total_r, 3),
        "avg_r": round(avg_r, 3) if avg_r is not None else None,
        "max_r": round(max_r, 3),
        "min_r": round(min_r, 3),
        "max_consecutive_losses": max_consec_losses,
        "max_drawdown_r": round(max_drawdown_r, 3),
        "avg_optional_score": round(avg_optional, 3),
        "avg_optional_score_winners": round(avg_optional_winners, 3),
        "avg_optional_score_losers": round(avg_optional_losers, 3),
        "bars_evaluated": bars_evaluated,
        "bars_with_signal": bars_with_signal,
        "signal_rate": round(signal_rate, 4),
        "symbol": settings.get("symbol", ""),
        "timeframe": settings.get("timeframe", ""),
        "start_date": actual_start or start_date_str,
        "end_date": actual_end or end_date_str,
        "bars_loaded": bars_loaded,
        "fallback_stop_used": result.get("fallback_stop_used", False),
        "data_coverage_warning": data_coverage_warning,
        "exit_reasons": exit_reasons,
        "management_events": mgmt_events,
    }


def _max_consecutive_losses(trades: list[dict]) -> int:
    max_streak = 0
    streak = 0
    for t in trades:
        r = t.get("r_multiple") or 0
        if r < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def _max_drawdown(trades: list[dict]) -> float:
    """Peak-to-trough cumulative R drawdown (≤ 0)."""
    if not trades:
        return 0.0
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        r = t.get("r_multiple") or 0
        cumulative += r
        if cumulative > peak:
            peak = cumulative
        dd = cumulative - peak
        if dd < max_dd:
            max_dd = dd
    return max_dd
