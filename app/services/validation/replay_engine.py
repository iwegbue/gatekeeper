"""
Replay Engine — pure Python, no DB, no async.

Walks bars chronologically, applies layer-gated logic to simulate how a compiled
trading plan would have performed over historical data.

compiled_rules schema (each rule dict from rule_interpreter.py):
    {rule_id, layer, name, rule_type, status, proxy: {type, params}, feature_dependencies, ...}
"""

import logging
from datetime import datetime

from app.services.validation.feature_engine import compute_features
from app.services.validation.proxy_evaluator import (
    eval_atr_stop,
    eval_be_at_r,
    eval_fixed_rr,
    eval_partial_at_r,
    eval_swing_stop,
    eval_trailing_stop,
    evaluate_proxy,
)

logger = logging.getLogger(__name__)

# Layer evaluation order
LAYER_ORDER = ["CONTEXT", "SETUP", "CONFIRMATION", "ENTRY", "RISK", "MANAGEMENT"]

# 2% fallback stop when no RISK rule is testable
FALLBACK_STOP_PCT = 0.02


# ── Public entry point ─────────────────────────────────────────────────────────


def run_replay(
    compiled_rules: list[dict],
    bars: list[dict],
    settings: dict,
) -> dict:
    """
    Run a bar-by-bar replay of the compiled trading plan.

    settings keys:
        symbol      str
        timeframe   str
        start_date  str  (ISO date, informational only)
        end_date    str  (informational only)
        direction   "LONG" | "SHORT" | "BOTH"

    Returns a result dict with keys: trades, summary (partial), bars_evaluated, bars_with_signal.
    """
    direction = str(settings.get("direction", "BOTH")).upper()
    directions = ["LONG", "SHORT"] if direction == "BOTH" else [direction]

    replayable_rules = _extract_replayable_rules(compiled_rules)
    all_feature_keys = _collect_all_feature_keys(replayable_rules)

    has_testable_risk = any(
        r["layer"] == "RISK" and r["status"] in ("TESTABLE", "APPROXIMATED")
        for r in replayable_rules
    )
    fallback_stop_used = not has_testable_risk

    trades: list[dict] = []
    bars_with_signal = 0

    # One open trade per direction
    open_trades: dict[str, dict | None] = {d: None for d in directions}

    for bar_index in range(1, len(bars)):
        bar = bars[bar_index]
        prev_bar = bars[bar_index - 1]

        # Inject current close into features so proxies can reference it
        close = bar["close"]
        raw_features = compute_features(bars, bar_index, all_feature_keys)
        features = {**raw_features, "close": close}

        for dir_ in directions:
            open_trade = open_trades[dir_]

            if open_trade is not None:
                # ── Manage open trade ───────────────────────────────────────
                outcome = _manage_trade(
                    open_trade, bar, bar_index, features,
                    _get_layer_rules(replayable_rules, "MANAGEMENT"),
                )
                if outcome["closed"]:
                    trades.append(outcome["trade"])
                    open_trades[dir_] = None
                else:
                    open_trades[dir_] = outcome["trade"]
            else:
                # ── Seek new entry ──────────────────────────────────────────
                params_with_dir = {"direction": dir_}

                # Context layer
                context_rules = _get_layer_rules(replayable_rules, "CONTEXT")
                context_passed, _ = _evaluate_layer(
                    "CONTEXT", context_rules, features, bar, prev_bar,
                    0.0, 0.0, dir_,
                )
                if not context_passed:
                    continue

                # Setup layer
                setup_rules = _get_layer_rules(replayable_rules, "SETUP")
                setup_passed, _ = _evaluate_layer(
                    "SETUP", setup_rules, features, bar, prev_bar,
                    0.0, 0.0, dir_,
                )
                if not setup_passed:
                    continue

                # Confirmation layer
                conf_rules = _get_layer_rules(replayable_rules, "CONFIRMATION")
                conf_passed, _ = _evaluate_layer(
                    "CONFIRMATION", conf_rules, features, bar, prev_bar,
                    0.0, 0.0, dir_,
                )
                if not conf_passed:
                    continue

                # Entry layer
                entry_rules = _get_layer_rules(replayable_rules, "ENTRY")
                entry_passed, _ = _evaluate_layer(
                    "ENTRY", entry_rules, features, bar, prev_bar,
                    0.0, 0.0, dir_,
                )
                if not entry_passed:
                    continue

                bars_with_signal += 1
                entry_price = float(bar["close"])

                # Risk layer — determine stop and target
                risk_rules = _get_layer_rules(replayable_rules, "RISK")
                stop_price = _compute_stop(risk_rules, features, entry_price, dir_, fallback_stop_used)
                target_price = _compute_target(risk_rules, entry_price, stop_price)

                # Optional score (OPTIONAL + ADVISORY rules that fired)
                optional_score = _compute_optional_score(
                    replayable_rules, features, bar, prev_bar, entry_price, stop_price, dir_
                )

                open_trades[dir_] = {
                    "bar_index": bar_index,
                    "entry_date": bar["ts"].isoformat() if hasattr(bar["ts"], "isoformat") else str(bar["ts"]),
                    "exit_date": None,
                    "symbol": settings.get("symbol", ""),
                    "direction": dir_,
                    "entry_price": entry_price,
                    "exit_price": None,
                    "stop_price": stop_price,
                    "target_price": target_price,
                    "r_multiple": None,
                    "exit_reason": "OPEN",
                    "optional_score": optional_score,
                    "management_events": [],
                    "_current_stop": stop_price,
                    "_be_moved": False,
                    "_partial_taken": False,
                    "_trailing_active": False,
                }

    # Close any still-open trades at end of data
    for dir_, open_trade in open_trades.items():
        if open_trade is not None:
            last_bar = bars[-1]
            last_close = float(last_bar["close"])
            risk = abs(open_trade["entry_price"] - open_trade["stop_price"])
            r_multiple = (
                (last_close - open_trade["entry_price"]) / risk
                if dir_ == "LONG"
                else (open_trade["entry_price"] - last_close) / risk
            ) if risk > 0 else 0.0
            open_trade["exit_price"] = last_close
            open_trade["exit_date"] = last_bar["ts"].isoformat() if hasattr(last_bar["ts"], "isoformat") else str(last_bar["ts"])
            open_trade["r_multiple"] = round(r_multiple, 3)
            open_trade["exit_reason"] = "END_OF_DATA"
            trades.append(_clean_trade(open_trade))

    return {
        "trades": trades,
        "bars_evaluated": len(bars),
        "bars_with_signal": bars_with_signal,
        "fallback_stop_used": fallback_stop_used,
        "actual_start": bars[0]["ts"].isoformat() if bars else None,
        "actual_end": bars[-1]["ts"].isoformat() if bars else None,
        "bars_loaded": len(bars),
    }


# ── Layer evaluation ──────────────────────────────────────────────────────────


def _evaluate_layer(
    layer: str,
    rules: list[dict],
    features: dict,
    bar: dict,
    prev_bar: dict,
    entry_price: float,
    stop_price: float,
    direction: str,
) -> tuple[bool, dict]:
    """
    Evaluate all rules in a layer.
    REQUIRED rules: all must pass for layer_passed = True.
    OPTIONAL / ADVISORY: contribute to score only.
    Returns (layer_passed, scores_dict).
    """
    if not rules:
        # No rules for this layer → layer passes by default
        return True, {}

    required_results: list[bool] = []
    scores: dict[str, float] = {}

    for rule in rules:
        proxy = rule.get("proxy") or {}
        proxy_type = proxy.get("type") or rule.get("status")
        proxy_params = dict(proxy.get("params") or {})
        proxy_params.setdefault("direction", direction)

        result = _call_proxy_bool(
            proxy_type, features, proxy_params, bar, prev_bar,
            entry_price, stop_price, direction,
        )
        scores[rule["rule_id"]] = float(result)

        rule_type = str(rule.get("rule_type", "REQUIRED")).upper()
        if rule_type == "REQUIRED":
            required_results.append(result)

    layer_passed = all(required_results) if required_results else True
    return layer_passed, scores


def _call_proxy_bool(
    proxy_type: str | None,
    features: dict,
    params: dict,
    bar: dict,
    prev_bar: dict,
    entry_price: float,
    stop_price: float,
    direction: str,
) -> bool:
    """Call evaluate_proxy and coerce to bool."""
    if not proxy_type or proxy_type == "NOT_TESTABLE":
        return False
    try:
        result = evaluate_proxy(
            proxy_type,
            features,
            params,
            bar=bar,
            prev_bar=prev_bar,
            entry_price=entry_price,
            stop_price=stop_price,
            direction=direction,
        )
        return bool(result)
    except (ValueError, KeyError, TypeError) as exc:
        logger.debug("Proxy eval error (%s): %s", proxy_type, exc)
        return False


# ── Risk computation ───────────────────────────────────────────────────────────


def _compute_stop(
    risk_rules: list[dict],
    features: dict,
    entry_price: float,
    direction: str,
    fallback_stop_used: bool,
) -> float:
    """Compute stop loss from the first testable RISK rule, or fallback."""
    for rule in risk_rules:
        proxy = rule.get("proxy") or {}
        proxy_type = proxy.get("type", "")
        params = dict(proxy.get("params") or {})
        params.setdefault("direction", direction)

        if proxy_type == "atr_stop":
            return eval_atr_stop(features, params, entry_price, direction)
        if proxy_type == "swing_stop":
            return eval_swing_stop(features, params, direction)
        if proxy_type == "fixed_rr":
            # fixed_rr gives target, not stop — use fallback
            continue

    # Fallback: 2% of entry price
    if direction == "LONG":
        return entry_price * (1 - FALLBACK_STOP_PCT)
    return entry_price * (1 + FALLBACK_STOP_PCT)


def _compute_target(risk_rules: list[dict], entry_price: float, stop_price: float) -> float | None:
    """Compute take-profit target from fixed_rr rule, or None."""
    for rule in risk_rules:
        proxy = rule.get("proxy") or {}
        proxy_type = proxy.get("type", "")
        params = dict(proxy.get("params") or {})
        if proxy_type == "fixed_rr":
            return eval_fixed_rr(entry_price, stop_price, params)
    return None


# ── Trade management ──────────────────────────────────────────────────────────


def _manage_trade(
    trade: dict,
    bar: dict,
    bar_index: int,
    features: dict,
    management_rules: list[dict],
) -> dict:
    """
    Evaluate management rules for an open trade bar-by-bar.
    Returns {"closed": bool, "trade": dict}.
    """
    trade = dict(trade)  # shallow copy to avoid mutation of original
    direction = trade["direction"]
    entry_price = trade["entry_price"]
    current_stop = trade["_current_stop"]
    target_price = trade.get("target_price")

    high = float(bar["high"])
    low = float(bar["low"])
    close = float(bar["close"])

    # Check stop loss
    if direction == "LONG" and low <= current_stop:
        return _close_trade(trade, bar, current_stop, "SL_HIT")
    if direction == "SHORT" and high >= current_stop:
        return _close_trade(trade, bar, current_stop, "SL_HIT")

    # Check take profit
    if target_price is not None:
        if direction == "LONG" and high >= target_price:
            return _close_trade(trade, bar, target_price, "TP_HIT")
        if direction == "SHORT" and low <= target_price:
            return _close_trade(trade, bar, target_price, "TP_HIT")

    current_price = close
    risk = abs(entry_price - trade["stop_price"])

    # Apply management rules
    for rule in management_rules:
        proxy = rule.get("proxy") or {}
        proxy_type = proxy.get("type", "")
        params = dict(proxy.get("params") or {})

        if proxy_type == "be_at_r" and not trade["_be_moved"]:
            triggered = eval_be_at_r(entry_price, trade["stop_price"], current_price, params)
            if triggered:
                # Move stop to breakeven
                current_stop = entry_price
                trade["_be_moved"] = True
                trade["_current_stop"] = current_stop
                if "BE_MOVED" not in trade["management_events"]:
                    trade["management_events"] = list(trade["management_events"]) + ["BE_MOVED"]

        elif proxy_type == "trailing_stop":
            new_stop = eval_trailing_stop(features, params, current_stop, current_price, direction)
            if new_stop != current_stop:
                current_stop = new_stop
                trade["_current_stop"] = current_stop
                if not trade["_trailing_active"]:
                    trade["_trailing_active"] = True
                    trade["management_events"] = list(trade["management_events"]) + ["TRAILING_ACTIVATED"]

        elif proxy_type == "partial_at_r" and not trade["_partial_taken"]:
            triggered = eval_partial_at_r(entry_price, trade["stop_price"], current_price, params)
            if triggered:
                trade["_partial_taken"] = True
                trade["management_events"] = list(trade["management_events"]) + ["PARTIAL_TAKEN"]

    trade["_current_stop"] = current_stop
    return {"closed": False, "trade": trade}


def _close_trade(trade: dict, bar: dict, exit_price: float, exit_reason: str) -> dict:
    """Mark a trade as closed and compute R-multiple."""
    entry_price = trade["entry_price"]
    direction = trade["direction"]
    risk = abs(entry_price - trade["stop_price"])

    if risk > 0:
        pnl = (exit_price - entry_price) if direction == "LONG" else (entry_price - exit_price)
        r_multiple = round(pnl / risk, 3)
    else:
        r_multiple = 0.0

    ts = bar["ts"]
    exit_date = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

    closed = dict(trade)
    closed["exit_price"] = exit_price
    closed["exit_date"] = exit_date
    closed["r_multiple"] = r_multiple
    closed["exit_reason"] = exit_reason

    return {"closed": True, "trade": _clean_trade(closed)}


def _clean_trade(trade: dict) -> dict:
    """Remove internal underscore-prefixed tracking fields."""
    return {k: v for k, v in trade.items() if not k.startswith("_")}


# ── Helpers ────────────────────────────────────────────────────────────────────


def _extract_replayable_rules(compiled_rules: list[dict]) -> list[dict]:
    """Keep only TESTABLE + APPROXIMATED rules; exclude BEHAVIORAL layer."""
    return [
        r for r in compiled_rules
        if r.get("status") in ("TESTABLE", "APPROXIMATED")
        and r.get("layer") != "BEHAVIORAL"
    ]


def _collect_all_feature_keys(rules: list[dict]) -> list[str]:
    """Union of all feature_dependencies across all replayable rules."""
    keys: set[str] = set()
    for r in rules:
        for k in r.get("feature_dependencies", []):
            keys.add(k)
    return list(keys)


def _get_layer_rules(rules: list[dict], layer: str) -> list[dict]:
    return [r for r in rules if r.get("layer") == layer]


def _compute_optional_score(
    replayable_rules: list[dict],
    features: dict,
    bar: dict,
    prev_bar: dict,
    entry_price: float,
    stop_price: float,
    direction: str,
) -> float:
    """Fraction of OPTIONAL rules that fired across all layers."""
    optional_rules = [r for r in replayable_rules if str(r.get("rule_type", "")).upper() == "OPTIONAL"]
    if not optional_rules:
        return 0.0
    fired = sum(
        1 for r in optional_rules
        if _call_proxy_bool(
            (r.get("proxy") or {}).get("type"),
            features,
            {**((r.get("proxy") or {}).get("params") or {}), "direction": direction},
            bar, prev_bar, entry_price, stop_price, direction,
        )
    )
    return round(fired / len(optional_rules), 3)
