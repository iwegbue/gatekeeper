"""
Feature Engine — pure Python, no DB, no async.

Computes technical indicator features from a list of OHLCV bar dicts.
All functions return None if there are insufficient bars for the warm-up period.

Bar dict shape: {"ts": datetime, "open": float, "high": float, "low": float, "close": float, "volume": float | None}
"""

import math
import re
from datetime import datetime, timezone


# ── Individual indicators ─────────────────────────────────────────────────────


def compute_sma(bars: list[dict], bar_index: int, period: int) -> float | None:
    """Simple moving average of close prices."""
    if bar_index < period - 1:
        return None
    window = bars[bar_index - period + 1 : bar_index + 1]
    return sum(float(b["close"]) for b in window) / period


def compute_ema(bars: list[dict], bar_index: int, period: int) -> float | None:
    """Exponential moving average (Wilder smoothing: alpha = 1/period)."""
    if bar_index < period - 1:
        return None
    alpha = 1.0 / period
    # seed with SMA of first `period` bars
    seed_start = bar_index - period + 1
    ema = sum(float(bars[i]["close"]) for i in range(seed_start, seed_start + period)) / period
    for i in range(seed_start + period, bar_index + 1):
        ema = alpha * float(bars[i]["close"]) + (1 - alpha) * ema
    return ema


def compute_atr(bars: list[dict], bar_index: int, period: int) -> float | None:
    """Average True Range using Wilder smoothing."""
    if bar_index < period:
        return None
    tr_values: list[float] = []
    for i in range(bar_index - period + 1, bar_index + 1):
        h = float(bars[i]["high"])
        l = float(bars[i]["low"])
        prev_c = float(bars[i - 1]["close"])
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        tr_values.append(tr)
    return sum(tr_values) / period


def compute_rsi(bars: list[dict], bar_index: int, period: int) -> float | None:
    """Wilder RSI."""
    if bar_index < period:
        return None
    gains = []
    losses = []
    start = bar_index - period + 1
    for i in range(start, bar_index + 1):
        delta = float(bars[i]["close"]) - float(bars[i - 1]["close"])
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def compute_swing_high(bars: list[dict], bar_index: int, lookback: int = 5) -> float | None:
    """Maximum high price over the prior `lookback` bars (not including current bar)."""
    if bar_index < lookback:
        return None
    return max(float(bars[i]["high"]) for i in range(bar_index - lookback, bar_index))


def compute_swing_low(bars: list[dict], bar_index: int, lookback: int = 5) -> float | None:
    """Minimum low price over the prior `lookback` bars (not including current bar)."""
    if bar_index < lookback:
        return None
    return min(float(bars[i]["low"]) for i in range(bar_index - lookback, bar_index))


def compute_htf_bias(bars: list[dict], bar_index: int, lookback: int = 20) -> str | None:
    """Higher-timeframe bias: bullish/bearish/neutral based on close vs lookback midpoint."""
    if bar_index < lookback:
        return None
    period_high = max(float(bars[i]["high"]) for i in range(bar_index - lookback, bar_index + 1))
    period_low = min(float(bars[i]["low"]) for i in range(bar_index - lookback, bar_index + 1))
    current_close = float(bars[bar_index]["close"])
    midpoint = (period_high + period_low) / 2
    if current_close > midpoint * 1.01:
        return "bullish"
    if current_close < midpoint * 0.99:
        return "bearish"
    return "neutral"


def compute_session(ts: datetime) -> str:
    """Classify bar timestamp into a trading session."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    hour = ts.hour
    if 8 <= hour < 12:
        return "london"
    if 12 <= hour < 17:
        return "london_ny_overlap"
    if 17 <= hour < 22:
        return "new_york"
    if 0 <= hour < 8:
        return "asian"
    return "off_hours"


# ── Feature key dispatcher ────────────────────────────────────────────────────

# Patterns for parsing feature keys
_SMA_RE = re.compile(r"^sma_(\d+)(?:_\w+)?$")
_EMA_RE = re.compile(r"^ema_(\d+)(?:_\w+)?$")
_ATR_RE = re.compile(r"^atr_(\d+)(?:_\w+)?$")
_RSI_RE = re.compile(r"^rsi_(\d+)(?:_\w+)?$")
_HTF_BIAS_RE = re.compile(r"^htf_bias(?:_(\w+))?$")


def compute_features(bars: list[dict], bar_index: int, feature_keys: list[str]) -> dict:
    """
    Compute a dict of named features for the given bar.

    Key format examples:
        "sma_200_1d"        → SMA(200)
        "ema_50"            → EMA(50)
        "atr_14"            → ATR(14)
        "rsi_14"            → RSI(14)
        "swing_highs"       → swing high, lookback 5
        "swing_lows"        → swing low, lookback 5
        "htf_bias"          → HTF bias, lookback 20
        "htf_bias_4h"       → same (timeframe suffix ignored — caller manages multi-tf bars)
        "session"           → session string
    """
    result: dict = {}
    for key in feature_keys:
        key_lower = key.lower()

        if key_lower == "session":
            ts = bars[bar_index]["ts"]
            result[key] = compute_session(ts)
            continue

        if key_lower in ("swing_highs", "swing_high"):
            result[key] = compute_swing_high(bars, bar_index, 5)
            continue

        if key_lower in ("swing_lows", "swing_low"):
            result[key] = compute_swing_low(bars, bar_index, 5)
            continue

        m = _SMA_RE.match(key_lower)
        if m:
            result[key] = compute_sma(bars, bar_index, int(m.group(1)))
            continue

        m = _EMA_RE.match(key_lower)
        if m:
            result[key] = compute_ema(bars, bar_index, int(m.group(1)))
            continue

        m = _ATR_RE.match(key_lower)
        if m:
            result[key] = compute_atr(bars, bar_index, int(m.group(1)))
            continue

        m = _RSI_RE.match(key_lower)
        if m:
            result[key] = compute_rsi(bars, bar_index, int(m.group(1)))
            continue

        m = _HTF_BIAS_RE.match(key_lower)
        if m:
            result[key] = compute_htf_bias(bars, bar_index, 20)
            continue

        # Unknown key — return None so proxies degrade gracefully
        result[key] = None

    return result
