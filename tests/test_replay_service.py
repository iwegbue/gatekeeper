"""
Integration tests for replay_service.py.

Uses a real Postgres test DB (via the `db` fixture) but mocks data_loader
so we don't need yfinance or network access during tests.
"""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.validation.compiled_plan import CompiledPlan
from app.models.validation.validation_run import ValidationRun
from app.services.validation.replay_service import (
    _compute_summary_metrics,
    _max_consecutive_losses,
    _max_drawdown,
    create_replay_run,
    run_replay_for_run,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_bars(n: int = 100) -> list[dict]:
    """Generate synthetic bars with a gentle uptrend."""
    bars = []
    price = 1.2000
    ts_base = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    for i in range(n):
        ts = ts_base.replace(day=1 + i % 28, month=1 + i // 28)
        bars.append({
            "ts": ts,
            "open": price,
            "high": price + 0.002,
            "low": price - 0.002,
            "close": price + 0.0001 * (i % 5 - 2),
            "volume": 10000.0,
        })
        price += 0.0001
    return bars


def _make_compiled_plan(db) -> CompiledPlan:
    """Create a minimal CompiledPlan with a market_entry rule."""
    plan = CompiledPlan(
        id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        plan_snapshot={"name": "Test Plan", "description": "", "rules": []},
        compiled_rules=[
            {
                "rule_id": str(uuid.uuid4()),
                "layer": "ENTRY",
                "name": "Market entry",
                "description": "",
                "rule_type": "REQUIRED",
                "weight": 1,
                "status": "TESTABLE",
                "proxy": {"type": "market_entry", "params": {}},
                "confidence": 1.0,
                "interpretation_notes": "Always enter at market",
                "feature_dependencies": [],
                "user_confirmed": True,
            }
        ],
        interpretability_score=80.0,
        coherence_warnings=[],
    )
    db.add(plan)
    return plan


# ── Unit tests (no DB) ────────────────────────────────────────────────────────


class TestMaxConsecutiveLosses:
    def test_no_trades(self):
        assert _max_consecutive_losses([]) == 0

    def test_all_wins(self):
        trades = [{"r_multiple": 1.0}] * 5
        assert _max_consecutive_losses(trades) == 0

    def test_streak_of_3(self):
        trades = [
            {"r_multiple": 1.0},
            {"r_multiple": -0.5},
            {"r_multiple": -0.5},
            {"r_multiple": -0.5},
            {"r_multiple": 1.0},
            {"r_multiple": -0.5},
            {"r_multiple": -0.5},
        ]
        assert _max_consecutive_losses(trades) == 3


class TestMaxDrawdown:
    def test_empty(self):
        assert _max_drawdown([]) == 0.0

    def test_all_wins(self):
        trades = [{"r_multiple": 1.0}] * 5
        assert _max_drawdown(trades) == 0.0

    def test_known_drawdown(self):
        # cumulative: 1, 0, -1, -2, -1 → peak at 1, trough at -2 → DD = -3
        trades = [
            {"r_multiple": 1.0},
            {"r_multiple": -1.0},
            {"r_multiple": -1.0},
            {"r_multiple": -1.0},
            {"r_multiple": 1.0},
        ]
        assert _max_drawdown(trades) == pytest.approx(-3.0)


class TestComputeSummaryMetrics:
    def test_basic_metrics(self):
        trades = [
            {"r_multiple": 2.0, "exit_reason": "TP_HIT", "optional_score": 0.8, "management_events": []},
            {"r_multiple": -1.0, "exit_reason": "SL_HIT", "optional_score": 0.4, "management_events": []},
            {"r_multiple": 1.5, "exit_reason": "TP_HIT", "optional_score": 0.7, "management_events": ["BE_MOVED"]},
        ]
        result_input = {
            "trades": trades,
            "bars_evaluated": 200,
            "bars_with_signal": 3,
            "fallback_stop_used": False,
            "actual_start": "2024-01-01T00:00:00+00:00",
            "actual_end": "2024-12-31T00:00:00+00:00",
            "bars_loaded": 250,
        }
        settings = {
            "symbol": "EURUSD",
            "timeframe": "1d",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "direction": "BOTH",
        }
        metrics = _compute_summary_metrics(result_input, settings, [], uuid.uuid4())

        assert metrics["total_trades"] == 3
        assert metrics["winning_trades"] == 2
        assert metrics["losing_trades"] == 1
        assert metrics["win_rate"] == pytest.approx(2 / 3, rel=1e-3)
        assert metrics["profit_factor"] == pytest.approx(3.5 / 1.0, rel=1e-3)
        assert metrics["total_r"] == pytest.approx(2.5, rel=1e-3)
        assert metrics["signal_rate"] == pytest.approx(3 / 200, rel=1e-3)
        assert metrics["exit_reasons"]["TP_HIT"] == 2
        assert metrics["exit_reasons"]["SL_HIT"] == 1
        assert metrics["management_events"]["BE_MOVED"] == 1

    def test_no_losing_trades_profit_factor_none(self):
        trades = [{"r_multiple": 1.0, "exit_reason": "TP_HIT", "optional_score": 0.5, "management_events": []}]
        result_input = {
            "trades": trades,
            "bars_evaluated": 10,
            "bars_with_signal": 1,
            "fallback_stop_used": False,
            "actual_start": None,
            "actual_end": None,
            "bars_loaded": 10,
        }
        metrics = _compute_summary_metrics(result_input, {}, [], uuid.uuid4())
        assert metrics["profit_factor"] is None


# ── Integration tests (require DB) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_replay_run(db):
    """create_replay_run inserts a PENDING REPLAY ValidationRun."""
    await db.flush()

    plan = _make_compiled_plan(db)
    await db.flush()

    run = await create_replay_run(
        db,
        compiled_plan_id=plan.id,
        symbol="EURUSD",
        timeframe="1d",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        direction="BOTH",
    )

    assert run.status == "PENDING"
    assert run.mode == "REPLAY"
    assert run.settings["symbol"] == "EURUSD"
    assert run.settings["timeframe"] == "1d"
    assert run.settings["direction"] == "BOTH"
    assert run.compiled_plan_id == plan.id


@pytest.mark.asyncio
async def test_run_replay_for_run_success(db):
    """run_replay_for_run completes successfully with mocked data_loader."""
    bars = _make_bars(50)
    plan = _make_compiled_plan(db)
    await db.flush()

    run = await create_replay_run(
        db,
        compiled_plan_id=plan.id,
        symbol="EURUSD",
        timeframe="1d",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 6, 30),
    )

    snapshot_id = uuid.uuid4()

    with (
        patch(
            "app.services.validation.replay_service.fetch_and_store_ohlc",
            new_callable=AsyncMock,
            return_value=snapshot_id,
        ),
        patch(
            "app.services.validation.replay_service.load_bars_for_snapshot",
            new_callable=AsyncMock,
            return_value=bars,
        ),
    ):
        completed = await run_replay_for_run(db, run.id)

    assert completed.status == "COMPLETED"
    assert completed.summary_metrics is not None
    assert completed.summary_metrics["total_trades"] >= 0
    assert completed.data_snapshot_id == snapshot_id


@pytest.mark.asyncio
async def test_run_replay_for_run_data_loader_error(db):
    """run_replay_for_run sets status=FAILED when data_loader raises."""
    from app.services.validation.data_loader import DataLoaderError

    plan = _make_compiled_plan(db)
    await db.flush()

    run = await create_replay_run(
        db,
        compiled_plan_id=plan.id,
        symbol="INVALID_SYMBOL",
        timeframe="1d",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 6, 30),
    )

    with patch(
        "app.services.validation.replay_service.fetch_and_store_ohlc",
        new_callable=AsyncMock,
        side_effect=DataLoaderError("yfinance returned 0 bars"),
    ):
        with pytest.raises(DataLoaderError):
            await run_replay_for_run(db, run.id)

    # Re-fetch to see updated status
    refreshed = await db.get(ValidationRun, run.id)
    assert refreshed.status == "FAILED"
    assert "yfinance returned 0 bars" in refreshed.error_message


@pytest.mark.asyncio
async def test_run_replay_populates_summary_metrics(db):
    """End-to-end: summary_metrics dict has expected keys."""
    bars = _make_bars(100)
    plan = _make_compiled_plan(db)
    await db.flush()

    run = await create_replay_run(
        db,
        compiled_plan_id=plan.id,
        symbol="EURUSD",
        timeframe="1d",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )

    snapshot_id = uuid.uuid4()
    with (
        patch(
            "app.services.validation.replay_service.fetch_and_store_ohlc",
            new_callable=AsyncMock,
            return_value=snapshot_id,
        ),
        patch(
            "app.services.validation.replay_service.load_bars_for_snapshot",
            new_callable=AsyncMock,
            return_value=bars,
        ),
    ):
        completed = await run_replay_for_run(db, run.id)

    m = completed.summary_metrics
    expected_keys = [
        "total_trades", "winning_trades", "losing_trades", "win_rate",
        "profit_factor", "total_r", "avg_r", "max_r", "min_r",
        "max_consecutive_losses", "max_drawdown_r",
        "avg_optional_score", "avg_optional_score_winners", "avg_optional_score_losers",
        "bars_evaluated", "bars_with_signal", "signal_rate",
        "symbol", "timeframe", "start_date", "end_date", "bars_loaded",
        "fallback_stop_used", "data_coverage_warning",
        "exit_reasons", "management_events",
    ]
    for key in expected_keys:
        assert key in m, f"Missing key in summary_metrics: {key}"
