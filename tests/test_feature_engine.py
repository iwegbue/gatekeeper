"""
Unit tests for feature_engine.py — no DB needed.
"""

from datetime import datetime, timezone

import pytest

from app.services.validation.feature_engine import (
    compute_atr,
    compute_ema,
    compute_features,
    compute_htf_bias,
    compute_rsi,
    compute_session,
    compute_sma,
    compute_swing_high,
    compute_swing_low,
)


def _bars(closes: list[float]) -> list[dict]:
    """Build minimal bar list from a list of close prices (open=high=low=close)."""
    ts_base = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
    return [
        {
            "ts": ts_base.replace(hour=ts_base.hour),
            "open": c,
            "high": c + 0.001,
            "low": c - 0.001,
            "close": c,
            "volume": 1000.0,
        }
        for c in closes
    ]


def _bars_with_highs_lows(data: list[tuple[float, float, float]]) -> list[dict]:
    """Build bars with explicit (close, high, low) tuples."""
    ts_base = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
    return [
        {
            "ts": ts_base,
            "open": c,
            "high": h,
            "low": l,
            "close": c,
            "volume": 1000.0,
        }
        for c, h, l in data
    ]


class TestSMA:
    def test_insufficient_bars(self):
        bars = _bars([1.0, 2.0, 3.0])
        assert compute_sma(bars, 2, 5) is None

    def test_exact_period(self):
        bars = _bars([1.0, 2.0, 3.0, 4.0, 5.0])
        result = compute_sma(bars, 4, 5)
        assert result == pytest.approx(3.0)

    def test_window_slides(self):
        bars = _bars([1.0, 2.0, 3.0, 4.0, 5.0, 10.0])
        result = compute_sma(bars, 5, 5)
        assert result == pytest.approx((2 + 3 + 4 + 5 + 10) / 5)


class TestEMA:
    def test_insufficient_bars(self):
        bars = _bars([1.0, 2.0])
        assert compute_ema(bars, 1, 5) is None

    def test_same_prices(self):
        bars = _bars([5.0] * 20)
        result = compute_ema(bars, 19, 10)
        assert result == pytest.approx(5.0, rel=1e-3)

    def test_trending_up(self):
        bars = _bars(list(range(1, 21)))  # 1..20
        result = compute_ema(bars, 19, 10)
        # EMA should be above SMA mid-point but below recent price
        assert result is not None
        assert 10 <= result <= 20


class TestATR:
    def test_insufficient_bars(self):
        bars = _bars([1.0])
        assert compute_atr(bars, 0, 14) is None

    def test_constant_bars_no_wick(self):
        # When open=high=low=close and no gaps, TR ≈ 0.002 (high-low = 0.002)
        bars = _bars([5.0] * 15)
        result = compute_atr(bars, 14, 14)
        assert result is not None
        assert result >= 0

    def test_wide_range_bar(self):
        # One very wide bar increases ATR
        data = [(5.0, 5.001, 4.999)] * 14 + [(5.0, 6.0, 4.0)]
        bars = _bars_with_highs_lows(data)
        result = compute_atr(bars, 14, 14)
        assert result is not None
        assert result > 0.05  # definitely larger than the default tiny bars


class TestRSI:
    def test_insufficient_bars(self):
        bars = _bars([1.0] * 5)
        assert compute_rsi(bars, 4, 14) is None

    def test_all_up(self):
        bars = _bars(list(range(1, 20)))
        result = compute_rsi(bars, 18, 14)
        assert result == pytest.approx(100.0)

    def test_all_down(self):
        bars = _bars(list(range(20, 1, -1)))
        result = compute_rsi(bars, 18, 14)
        assert result == pytest.approx(0.0)

    def test_midrange(self):
        # Alternating up/down → RSI near 50
        closes = []
        for i in range(20):
            closes.append(5.0 + (0.1 if i % 2 == 0 else -0.1))
        bars = _bars(closes)
        result = compute_rsi(bars, 19, 14)
        assert result is not None
        assert 30 < result < 70


class TestSwingHighLow:
    def test_swing_high(self):
        bars = _bars_with_highs_lows([(1.0, 1.1, 0.9)] * 5 + [(1.0, 1.1, 0.9)])
        result = compute_swing_high(bars, 5, 5)
        assert result == pytest.approx(1.1)

    def test_swing_low(self):
        bars = _bars_with_highs_lows([(1.0, 1.1, 0.9)] * 5 + [(1.0, 1.1, 0.9)])
        result = compute_swing_low(bars, 5, 5)
        assert result == pytest.approx(0.9)

    def test_insufficient_bars(self):
        bars = _bars([1.0, 2.0, 3.0])
        assert compute_swing_high(bars, 2, 5) is None
        assert compute_swing_low(bars, 2, 5) is None


class TestHTFBias:
    def test_bullish(self):
        # Close near top of range → bullish
        closes = [1.0] * 20 + [2.0]
        bars = _bars(closes)
        bars[-1]["high"] = 2.0
        bars[-1]["low"] = 2.0
        result = compute_htf_bias(bars, 20, 20)
        assert result == "bullish"

    def test_insufficient(self):
        bars = _bars([1.0, 2.0])
        assert compute_htf_bias(bars, 1, 5) is None


class TestSession:
    def test_london(self):
        ts = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        assert compute_session(ts) == "london"

    def test_london_ny_overlap(self):
        ts = datetime(2024, 1, 1, 14, 0, tzinfo=timezone.utc)
        assert compute_session(ts) == "london_ny_overlap"

    def test_new_york(self):
        ts = datetime(2024, 1, 1, 18, 0, tzinfo=timezone.utc)
        assert compute_session(ts) == "new_york"

    def test_asian(self):
        ts = datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc)
        assert compute_session(ts) == "asian"

    def test_off_hours(self):
        ts = datetime(2024, 1, 1, 23, 30, tzinfo=timezone.utc)
        assert compute_session(ts) == "off_hours"

    def test_naive_ts_treated_as_utc(self):
        ts = datetime(2024, 1, 1, 10, 0)  # no tzinfo
        assert compute_session(ts) == "london"


class TestComputeFeatures:
    def test_session_key(self):
        bars = _bars([1.0] * 5)
        bars[4]["ts"] = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        result = compute_features(bars, 4, ["session"])
        assert result["session"] == "london"

    def test_sma_key_parsed(self):
        bars = _bars([1.0, 2.0, 3.0, 4.0, 5.0])
        result = compute_features(bars, 4, ["sma_5"])
        assert result["sma_5"] == pytest.approx(3.0)

    def test_unknown_key_returns_none(self):
        bars = _bars([1.0] * 5)
        result = compute_features(bars, 4, ["unknown_feature_xyz"])
        assert result["unknown_feature_xyz"] is None

    def test_swing_highs_key(self):
        bars = _bars_with_highs_lows([(1.0, 2.0, 0.5)] * 6)
        result = compute_features(bars, 5, ["swing_highs"])
        assert result["swing_highs"] == pytest.approx(2.0)
