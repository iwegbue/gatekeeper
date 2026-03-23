"""
Proxy Evaluator — pure Python, no DB, no async.

One eval_* function per proxy type from the PROXY_VOCABULARY.
None features → False (safe default: gate not passed).
"""


# ── Context layer proxies ─────────────────────────────────────────────────────


def eval_sma_trend(features: dict, params: dict) -> bool:
    """Price above/below SMA indicates trend direction."""
    period = params.get("period", 200)
    timeframe = params.get("timeframe", "1d")
    direction = str(params.get("direction", "LONG")).upper()

    # Try exact key first, then period-only fallback
    sma_key = f"sma_{period}_{timeframe}"
    sma = features.get(sma_key) or features.get(f"sma_{period}")
    close = features.get("close")

    if sma is None or close is None:
        return False
    if direction == "LONG":
        return float(close) > float(sma)
    return float(close) < float(sma)


def eval_ema_trend(features: dict, params: dict) -> bool:
    """Price above/below EMA indicates trend direction."""
    period = params.get("period", 50)
    timeframe = params.get("timeframe", "1d")
    direction = str(params.get("direction", "LONG")).upper()

    ema_key = f"ema_{period}_{timeframe}"
    ema = features.get(ema_key) or features.get(f"ema_{period}")
    close = features.get("close")

    if ema is None or close is None:
        return False
    if direction == "LONG":
        return float(close) > float(ema)
    return float(close) < float(ema)


def eval_higher_tf_bias(features: dict, params: dict) -> bool:
    """Higher-timeframe bias matches required direction."""
    direction = str(params.get("direction", "LONG")).upper()
    timeframe = params.get("timeframe", "")

    bias_key = f"htf_bias_{timeframe}" if timeframe else "htf_bias"
    bias = features.get(bias_key) or features.get("htf_bias")

    if bias is None:
        return False
    if direction == "LONG":
        return str(bias).lower() == "bullish"
    return str(bias).lower() == "bearish"


def eval_session_filter(features: dict, params: dict) -> bool:
    """Bar session is in the allowed sessions list."""
    allowed = [s.lower() for s in params.get("allowed_sessions", ["london", "london_ny_overlap"])]
    session = features.get("session")
    if session is None:
        return False
    return str(session).lower() in allowed


# ── Setup layer proxies ───────────────────────────────────────────────────────


def eval_swing_break(features: dict, params: dict) -> bool:
    """Close breaks above swing high (LONG) or below swing low (SHORT)."""
    direction = str(params.get("direction", "LONG")).upper()
    close = features.get("close")

    if direction == "LONG":
        swing_high = features.get("swing_highs") or features.get("swing_high")
        if close is None or swing_high is None:
            return False
        return float(close) > float(swing_high)
    else:
        swing_low = features.get("swing_lows") or features.get("swing_low")
        if close is None or swing_low is None:
            return False
        return float(close) < float(swing_low)


def eval_zone_proximity(features: dict, params: dict) -> bool:
    """Price is within atr_multiple * ATR of the nearest swing level."""
    direction = str(params.get("direction", "LONG")).upper()
    atr_multiple = float(params.get("atr_multiple", 0.5))

    close = features.get("close")
    atr = features.get("atr_14") or features.get("atr")

    if close is None or atr is None or float(atr) == 0:
        return False

    if direction == "LONG":
        swing = features.get("swing_lows") or features.get("swing_low")
    else:
        swing = features.get("swing_highs") or features.get("swing_high")

    if swing is None:
        return False

    distance = abs(float(close) - float(swing))
    return distance <= atr_multiple * float(atr)


# ── Confirmation layer proxies ────────────────────────────────────────────────


def eval_candle_pattern(features: dict, params: dict, bar: dict, prev_bar: dict | None) -> bool:
    """
    Detect common candle patterns.
    Supported patterns: engulfing, pin_bar, inside_bar, doji.
    """
    pattern = str(params.get("pattern", "engulfing")).lower()
    direction = str(params.get("direction", "LONG")).upper()

    if not bar:
        return False

    o = float(bar.get("open", 0))
    h = float(bar.get("high", 0))
    l = float(bar.get("low", 0))
    c = float(bar.get("close", 0))
    body = abs(c - o)
    candle_range = h - l

    if candle_range == 0:
        return False

    if pattern == "doji":
        return body / candle_range < 0.1

    if pattern == "pin_bar":
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l
        if direction == "LONG":
            return lower_wick > body * 2 and lower_wick > upper_wick * 2
        return upper_wick > body * 2 and upper_wick > lower_wick * 2

    if pattern == "inside_bar":
        if prev_bar is None:
            return False
        prev_h = float(prev_bar.get("high", 0))
        prev_l = float(prev_bar.get("low", 0))
        return h < prev_h and l > prev_l

    if pattern == "engulfing":
        if prev_bar is None:
            return False
        prev_o = float(prev_bar.get("open", 0))
        prev_c = float(prev_bar.get("close", 0))
        if direction == "LONG":
            # Bullish engulfing: prev bar bearish, current bar bullish and engulfs
            return prev_c < prev_o and c > o and c > prev_o and o < prev_c
        else:
            # Bearish engulfing
            return prev_c > prev_o and c < o and c < prev_o and o > prev_c

    return False


def eval_momentum_confirm(features: dict, params: dict) -> bool:
    """RSI confirms momentum direction."""
    direction = str(params.get("direction", "LONG")).upper()
    threshold = float(params.get("threshold", 50.0))

    rsi = features.get("rsi_14") or features.get("rsi")
    if rsi is None:
        return False

    if direction == "LONG":
        return float(rsi) > threshold
    return float(rsi) < (100.0 - threshold)


# ── Entry layer proxies ───────────────────────────────────────────────────────


def eval_limit_entry(features: dict, params: dict) -> bool:
    """Price is near the computed zone level for a limit order."""
    direction = str(params.get("direction", "LONG")).upper()
    atr_multiple = float(params.get("atr_multiple", 0.3))

    close = features.get("close")
    atr = features.get("atr_14") or features.get("atr")

    if close is None or atr is None or float(atr) == 0:
        return False

    if direction == "LONG":
        zone = features.get("swing_lows") or features.get("swing_low")
    else:
        zone = features.get("swing_highs") or features.get("swing_high")

    if zone is None:
        return False

    distance = abs(float(close) - float(zone))
    return distance <= atr_multiple * float(atr)


def eval_market_entry(features: dict, params: dict) -> bool:
    """Market entry — always True when all prior gates pass."""
    return True


# ── Risk layer proxies (return stop price, not bool) ─────────────────────────


def eval_atr_stop(features: dict, params: dict, entry_price: float, direction: str) -> float:
    """ATR-based stop loss distance from entry."""
    multiplier = float(params.get("multiplier", 1.5))
    atr = features.get("atr_14") or features.get("atr")
    if atr is None:
        return _fallback_stop(entry_price, direction)
    stop_distance = multiplier * float(atr)
    if direction.upper() == "LONG":
        return entry_price - stop_distance
    return entry_price + stop_distance


def eval_swing_stop(features: dict, params: dict, direction: str) -> float:
    """Stop loss at nearest swing level."""
    buffer_atr = float(params.get("buffer_atr", 0.1))
    atr = features.get("atr_14") or features.get("atr")
    atr_val = float(atr) if atr is not None else 0.0

    if direction.upper() == "LONG":
        swing = features.get("swing_lows") or features.get("swing_low")
        if swing is None:
            return 0.0
        return float(swing) - buffer_atr * atr_val
    else:
        swing = features.get("swing_highs") or features.get("swing_high")
        if swing is None:
            return 0.0
        return float(swing) + buffer_atr * atr_val


def eval_fixed_rr(entry_price: float, stop_price: float, params: dict) -> float:
    """Fixed risk:reward target price."""
    rr = float(params.get("rr", 2.0))
    risk = abs(entry_price - stop_price)
    if entry_price > stop_price:
        return entry_price + risk * rr
    return entry_price - risk * rr


# ── Management layer proxies ──────────────────────────────────────────────────


def eval_trailing_stop(
    features: dict,
    params: dict,
    current_stop: float,
    current_price: float,
    direction: str,
) -> float:
    """Trail stop by ATR multiple, only moving in trade's favour."""
    atr_multiple = float(params.get("atr_multiple", 1.0))
    atr = features.get("atr_14") or features.get("atr")
    if atr is None:
        return current_stop

    trail_distance = atr_multiple * float(atr)
    if direction.upper() == "LONG":
        new_stop = current_price - trail_distance
        return max(new_stop, current_stop)
    else:
        new_stop = current_price + trail_distance
        return min(new_stop, current_stop)


def eval_partial_at_r(
    entry_price: float,
    stop_price: float,
    current_price: float,
    params: dict,
) -> bool:
    """Trigger partial close when price reaches N:1 R multiple."""
    r_trigger = float(params.get("r_trigger", 1.0))
    risk = abs(entry_price - stop_price)
    if risk == 0:
        return False
    r_achieved = (current_price - entry_price) / risk if current_price > entry_price else (entry_price - current_price) / risk
    return r_achieved >= r_trigger


def eval_be_at_r(
    entry_price: float,
    stop_price: float,
    current_price: float,
    params: dict,
) -> bool:
    """Move stop to breakeven when price reaches N:1 R multiple."""
    r_trigger = float(params.get("r_trigger", 1.0))
    risk = abs(entry_price - stop_price)
    if risk == 0:
        return False
    r_achieved = abs(current_price - entry_price) / risk
    return r_achieved >= r_trigger


# ── Dispatcher ────────────────────────────────────────────────────────────────


def evaluate_proxy(
    proxy_type: str,
    features: dict,
    params: dict,
    **kwargs,
) -> bool | float:
    """
    Dispatch to the appropriate eval_* function.

    kwargs used for context-specific args:
        bar         — current bar dict (for candle_pattern)
        prev_bar    — previous bar dict (for candle_pattern)
        entry_price — float (for risk/management proxies)
        stop_price  — float (for management proxies)
        direction   — "LONG" | "SHORT"
        current_stop — float (for trailing_stop)
        current_price — float (for trailing_stop / management)
    """
    bar = kwargs.get("bar")
    prev_bar = kwargs.get("prev_bar")
    entry_price = float(kwargs.get("entry_price", 0.0))
    stop_price = float(kwargs.get("stop_price", 0.0))
    direction = str(kwargs.get("direction", params.get("direction", "LONG"))).upper()
    current_stop = float(kwargs.get("current_stop", stop_price))
    current_price = float(kwargs.get("current_price", entry_price))

    match proxy_type:
        case "sma_trend":
            return eval_sma_trend(features, params)
        case "ema_trend":
            return eval_ema_trend(features, params)
        case "higher_tf_bias":
            return eval_higher_tf_bias(features, params)
        case "session_filter":
            return eval_session_filter(features, params)
        case "swing_break":
            return eval_swing_break(features, params)
        case "zone_proximity":
            return eval_zone_proximity(features, params)
        case "candle_pattern":
            return eval_candle_pattern(features, params, bar or {}, prev_bar)
        case "momentum_confirm":
            return eval_momentum_confirm(features, params)
        case "limit_entry":
            return eval_limit_entry(features, params)
        case "market_entry":
            return eval_market_entry(features, params)
        case "atr_stop":
            return eval_atr_stop(features, params, entry_price, direction)
        case "swing_stop":
            return eval_swing_stop(features, params, direction)
        case "fixed_rr":
            return eval_fixed_rr(entry_price, stop_price, params)
        case "trailing_stop":
            return eval_trailing_stop(features, params, current_stop, current_price, direction)
        case "partial_at_r":
            return eval_partial_at_r(entry_price, stop_price, current_price, params)
        case "be_at_r":
            return eval_be_at_r(entry_price, stop_price, current_price, params)
        case "not_testable":
            return False
        case _:
            raise ValueError(f"Unknown proxy_type: {proxy_type!r}")


# ── Internal helpers ──────────────────────────────────────────────────────────


def _fallback_stop(entry_price: float, direction: str, pct: float = 0.02) -> float:
    if direction.upper() == "LONG":
        return entry_price * (1 - pct)
    return entry_price * (1 + pct)
