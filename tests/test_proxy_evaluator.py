"""
Unit tests for proxy_evaluator.py — no DB needed.
"""

import pytest

from app.services.validation.proxy_evaluator import (
    eval_atr_stop,
    eval_be_at_r,
    eval_candle_pattern,
    eval_ema_trend,
    eval_fixed_rr,
    eval_higher_tf_bias,
    eval_limit_entry,
    eval_market_entry,
    eval_momentum_confirm,
    eval_partial_at_r,
    eval_session_filter,
    eval_sma_trend,
    eval_swing_break,
    eval_swing_stop,
    eval_trailing_stop,
    eval_zone_proximity,
    evaluate_proxy,
)


class TestSmaTrend:
    def test_long_above_sma(self):
        features = {"close": 1.1, "sma_200": 1.0}
        assert eval_sma_trend(features, {"period": 200, "direction": "LONG"}) is True

    def test_long_below_sma(self):
        features = {"close": 0.9, "sma_200": 1.0}
        assert eval_sma_trend(features, {"period": 200, "direction": "LONG"}) is False

    def test_short_below_sma(self):
        features = {"close": 0.9, "sma_200": 1.0}
        assert eval_sma_trend(features, {"period": 200, "direction": "SHORT"}) is True

    def test_none_feature_returns_false(self):
        features = {"close": 1.1}  # no sma key
        assert eval_sma_trend(features, {"period": 200}) is False

    def test_timeframe_key(self):
        features = {"close": 1.1, "sma_200_1d": 1.0}
        assert eval_sma_trend(features, {"period": 200, "timeframe": "1d", "direction": "LONG"}) is True


class TestEmaTrend:
    def test_long_above_ema(self):
        features = {"close": 1.1, "ema_50": 1.0}
        assert eval_ema_trend(features, {"period": 50, "direction": "LONG"}) is True

    def test_none_ema(self):
        assert eval_ema_trend({}, {}) is False


class TestHigherTFBias:
    def test_bullish_long(self):
        features = {"htf_bias": "bullish"}
        assert eval_higher_tf_bias(features, {"direction": "LONG"}) is True

    def test_bearish_long(self):
        features = {"htf_bias": "bearish"}
        assert eval_higher_tf_bias(features, {"direction": "LONG"}) is False

    def test_bearish_short(self):
        features = {"htf_bias": "bearish"}
        assert eval_higher_tf_bias(features, {"direction": "SHORT"}) is True

    def test_none_bias(self):
        assert eval_higher_tf_bias({}, {"direction": "LONG"}) is False

    def test_timeframe_suffix(self):
        features = {"htf_bias_4h": "bullish"}
        assert eval_higher_tf_bias(features, {"direction": "LONG", "timeframe": "4h"}) is True


class TestSessionFilter:
    def test_allowed_session(self):
        features = {"session": "london"}
        assert eval_session_filter(features, {"allowed_sessions": ["london"]}) is True

    def test_not_allowed(self):
        features = {"session": "asian"}
        assert eval_session_filter(features, {"allowed_sessions": ["london", "london_ny_overlap"]}) is False

    def test_none_session(self):
        assert eval_session_filter({}, {}) is False


class TestSwingBreak:
    def test_long_breaks_above(self):
        features = {"close": 1.1, "swing_highs": 1.05}
        assert eval_swing_break(features, {"direction": "LONG"}) is True

    def test_long_no_break(self):
        features = {"close": 1.0, "swing_highs": 1.05}
        assert eval_swing_break(features, {"direction": "LONG"}) is False

    def test_short_breaks_below(self):
        features = {"close": 0.9, "swing_lows": 0.95}
        assert eval_swing_break(features, {"direction": "SHORT"}) is True

    def test_none_swing_high(self):
        features = {"close": 1.1}
        assert eval_swing_break(features, {"direction": "LONG"}) is False


class TestZoneProximity:
    def test_within_zone(self):
        features = {"close": 1.01, "swing_lows": 1.0, "atr_14": 0.05}
        assert eval_zone_proximity(features, {"direction": "LONG", "atr_multiple": 0.5}) is True

    def test_too_far(self):
        features = {"close": 1.1, "swing_lows": 1.0, "atr_14": 0.05}
        assert eval_zone_proximity(features, {"direction": "LONG", "atr_multiple": 0.5}) is False

    def test_zero_atr(self):
        features = {"close": 1.01, "swing_lows": 1.0, "atr_14": 0.0}
        assert eval_zone_proximity(features, {"direction": "LONG"}) is False


class TestCandlePattern:
    def _bar(self, o, h, l, c):
        return {"open": o, "high": h, "low": l, "close": c}

    def test_doji(self):
        bar = self._bar(1.0, 1.005, 0.995, 1.0001)
        assert eval_candle_pattern({}, {"pattern": "doji"}, bar, None) is True

    def test_not_doji(self):
        bar = self._bar(1.0, 1.1, 0.9, 1.1)
        assert eval_candle_pattern({}, {"pattern": "doji"}, bar, None) is False

    def test_bullish_pin_bar(self):
        bar = self._bar(1.05, 1.06, 0.9, 1.05)
        assert eval_candle_pattern({}, {"pattern": "pin_bar", "direction": "LONG"}, bar, None) is True

    def test_bearish_engulfing(self):
        prev = self._bar(0.95, 1.0, 0.95, 1.0)  # bullish prev
        bar = self._bar(1.05, 1.05, 0.9, 0.9)   # bearish engulfs
        assert eval_candle_pattern({}, {"pattern": "engulfing", "direction": "SHORT"}, bar, prev) is True

    def test_inside_bar(self):
        prev = self._bar(1.0, 1.1, 0.9, 1.0)
        bar = self._bar(1.0, 1.05, 0.95, 1.0)
        assert eval_candle_pattern({}, {"pattern": "inside_bar"}, bar, prev) is True

    def test_empty_bar(self):
        assert eval_candle_pattern({}, {"pattern": "engulfing"}, {}, None) is False


class TestMomentumConfirm:
    def test_long_rsi_above(self):
        features = {"rsi_14": 60}
        assert eval_momentum_confirm(features, {"direction": "LONG", "threshold": 50}) is True

    def test_long_rsi_below(self):
        features = {"rsi_14": 40}
        assert eval_momentum_confirm(features, {"direction": "LONG", "threshold": 50}) is False

    def test_short_rsi_below(self):
        features = {"rsi_14": 35}
        assert eval_momentum_confirm(features, {"direction": "SHORT", "threshold": 50}) is True


class TestLimitEntry:
    def test_near_zone(self):
        features = {"close": 1.01, "swing_lows": 1.0, "atr_14": 0.05}
        assert eval_limit_entry(features, {"direction": "LONG", "atr_multiple": 0.3}) is True

    def test_far_from_zone(self):
        features = {"close": 1.2, "swing_lows": 1.0, "atr_14": 0.05}
        assert eval_limit_entry(features, {"direction": "LONG", "atr_multiple": 0.3}) is False


class TestMarketEntry:
    def test_always_true(self):
        assert eval_market_entry({}, {}) is True


class TestAtrStop:
    def test_long_stop_below_entry(self):
        features = {"atr_14": 0.1}
        stop = eval_atr_stop(features, {"multiplier": 1.5}, 1.2, "LONG")
        assert stop == pytest.approx(1.2 - 1.5 * 0.1)

    def test_short_stop_above_entry(self):
        features = {"atr_14": 0.1}
        stop = eval_atr_stop(features, {"multiplier": 1.5}, 1.2, "SHORT")
        assert stop == pytest.approx(1.2 + 1.5 * 0.1)

    def test_fallback_when_no_atr(self):
        stop = eval_atr_stop({}, {}, 1.2, "LONG")
        assert stop == pytest.approx(1.2 * 0.98)


class TestSwingStop:
    def test_long_stop(self):
        features = {"swing_lows": 1.0, "atr_14": 0.05}
        stop = eval_swing_stop(features, {"buffer_atr": 0.2}, "LONG")
        assert stop == pytest.approx(1.0 - 0.2 * 0.05)

    def test_short_stop(self):
        features = {"swing_highs": 1.1, "atr_14": 0.05}
        stop = eval_swing_stop(features, {"buffer_atr": 0.2}, "SHORT")
        assert stop == pytest.approx(1.1 + 0.2 * 0.05)


class TestFixedRR:
    def test_long_target(self):
        # entry=1.2, stop=1.1 → risk=0.1, rr=2 → target=1.4
        target = eval_fixed_rr(1.2, 1.1, {"rr": 2.0})
        assert target == pytest.approx(1.4)

    def test_short_target(self):
        target = eval_fixed_rr(1.2, 1.3, {"rr": 2.0})
        assert target == pytest.approx(1.0)


class TestTrailingStop:
    def test_long_trails_up(self):
        features = {"atr_14": 0.1}
        # New trail = 1.5 - 0.1 = 1.4 > current_stop 1.2 → moves up
        new_stop = eval_trailing_stop(features, {"atr_multiple": 1.0}, 1.2, 1.5, "LONG")
        assert new_stop == pytest.approx(1.4)

    def test_long_does_not_trail_down(self):
        features = {"atr_14": 0.1}
        # New trail = 1.3 - 0.1 = 1.2 — not better than current 1.35
        new_stop = eval_trailing_stop(features, {"atr_multiple": 1.0}, 1.35, 1.3, "LONG")
        assert new_stop == pytest.approx(1.35)

    def test_no_atr_returns_current(self):
        new_stop = eval_trailing_stop({}, {}, 1.2, 1.5, "LONG")
        assert new_stop == pytest.approx(1.2)


class TestPartialAtR:
    def test_triggered(self):
        assert eval_partial_at_r(1.2, 1.1, 1.3, {"r_trigger": 1.0}) is True

    def test_not_triggered(self):
        assert eval_partial_at_r(1.2, 1.1, 1.25, {"r_trigger": 1.0}) is False

    def test_zero_risk(self):
        assert eval_partial_at_r(1.2, 1.2, 1.3, {"r_trigger": 1.0}) is False


class TestBeAtR:
    def test_triggered(self):
        assert eval_be_at_r(1.2, 1.1, 1.3, {"r_trigger": 1.0}) is True

    def test_not_triggered(self):
        assert eval_be_at_r(1.2, 1.1, 1.25, {"r_trigger": 1.0}) is False


class TestEvaluateProxy:
    def test_dispatcher_sma_trend(self):
        features = {"close": 1.1, "sma_200": 1.0}
        result = evaluate_proxy("sma_trend", features, {"period": 200, "direction": "LONG"})
        assert result is True

    def test_dispatcher_market_entry(self):
        assert evaluate_proxy("market_entry", {}, {}) is True

    def test_dispatcher_not_testable(self):
        assert evaluate_proxy("not_testable", {}, {}) is False

    def test_dispatcher_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown proxy_type"):
            evaluate_proxy("made_up_type", {}, {})

    def test_dispatcher_atr_stop_returns_float(self):
        features = {"atr_14": 0.1}
        result = evaluate_proxy(
            "atr_stop", features, {"multiplier": 1.5},
            entry_price=1.2, direction="LONG",
        )
        assert isinstance(result, float)
        assert result == pytest.approx(1.2 - 0.15)
