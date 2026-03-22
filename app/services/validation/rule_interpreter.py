"""
Rule interpreter — maps human-readable plan rules to machine-testable proxies.

Strategy: AI proposes, user confirms.
- Each rule is sent to the AI provider with the proxy vocabulary as context.
- The AI selects from a fixed set of proxy types and fills in parameters.
- BEHAVIORAL rules are auto-classified as NOT_TESTABLE (no AI call).
- Results are returned as CompiledRule dicts; persisted by plan_compiler.
"""
import json
import logging
from typing import TYPE_CHECKING

from app.models.enums import InterpretationStatus, PlanLayer
from app.models.plan_rule import PlanRule

if TYPE_CHECKING:
    from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)

# ── Proxy vocabulary ──────────────────────────────────────────────────────────
#
# This is the complete set of proxy types the AI may assign.
# Each entry describes the type, its valid layer, and required/optional params.

PROXY_VOCABULARY: dict[str, dict] = {
    "sma_trend": {
        "layer": "CONTEXT",
        "description": "Price is above (bullish) or below (bearish) a simple moving average.",
        "params": {"period": "int (e.g. 200)", "timeframe": "str (e.g. '1d', '4h', '1h')", "direction_match": "bool"},
        "feature_dependencies": ["sma_{period}_{timeframe}"],
    },
    "ema_trend": {
        "layer": "CONTEXT",
        "description": "Price is above (bullish) or below (bearish) an exponential moving average.",
        "params": {"period": "int (e.g. 21)", "timeframe": "str", "direction_match": "bool"},
        "feature_dependencies": ["ema_{period}_{timeframe}"],
    },
    "higher_tf_bias": {
        "layer": "CONTEXT",
        "description": "Higher timeframe candle closes in the direction of the trade.",
        "params": {"timeframe": "str (e.g. '1d', '1w')", "lookback": "int (number of candles, e.g. 3)"},
        "feature_dependencies": ["htf_bias_{timeframe}"],
    },
    "session_filter": {
        "layer": "CONTEXT",
        "description": "Trade only during a specific market session (London, New York, Asian).",
        "params": {"session": "str ('london', 'new_york', 'asian', 'london_ny_overlap')"},
        "feature_dependencies": ["session"],
    },
    "swing_break": {
        "layer": "SETUP",
        "description": "Price breaks above a recent swing high (long) or below a swing low (short).",
        "params": {"swing_lookback": "int (bars to define swing, e.g. 5)", "direction": "str ('high' or 'low')"},
        "feature_dependencies": ["swing_highs", "swing_lows"],
    },
    "zone_proximity": {
        "layer": "SETUP",
        "description": "Price is within a defined distance of a support/resistance zone.",
        "params": {"zone_atr_multiple": "float (ATR multiples defining zone width, e.g. 0.5)"},
        "feature_dependencies": ["atr_14", "swing_highs", "swing_lows"],
    },
    "candle_pattern": {
        "layer": "CONFIRMATION",
        "description": "A specific candlestick pattern is present (e.g. engulfing, pin bar, inside bar).",
        "params": {"pattern": "str ('engulfing', 'pin_bar', 'inside_bar', 'doji')"},
        "feature_dependencies": [],
    },
    "momentum_confirm": {
        "layer": "CONFIRMATION",
        "description": "A momentum indicator confirms trade direction (RSI above/below threshold).",
        "params": {"indicator": "str ('rsi')", "period": "int (e.g. 14)", "threshold": "float (e.g. 50)", "direction": "str ('above' or 'below')"},
        "feature_dependencies": ["rsi_{period}"],
    },
    "limit_entry": {
        "layer": "ENTRY",
        "description": "Entry is placed as a limit order at a defined price level.",
        "params": {"level_type": "str ('swing_high', 'swing_low', 'zone_midpoint', 'zone_edge')"},
        "feature_dependencies": ["swing_highs", "swing_lows"],
    },
    "market_entry": {
        "layer": "ENTRY",
        "description": "Entry is taken at the open of the next bar after setup qualifies.",
        "params": {},
        "feature_dependencies": [],
    },
    "atr_stop": {
        "layer": "RISK",
        "description": "Stop loss is placed at N x ATR from entry.",
        "params": {"atr_period": "int (e.g. 14)", "atr_multiple": "float (e.g. 1.5)"},
        "feature_dependencies": ["atr_{atr_period}"],
    },
    "swing_stop": {
        "layer": "RISK",
        "description": "Stop loss is placed beyond the most recent swing high/low.",
        "params": {"swing_lookback": "int (bars, e.g. 5)", "buffer_atr_multiple": "float (e.g. 0.1)"},
        "feature_dependencies": ["swing_highs", "swing_lows", "atr_14"],
    },
    "fixed_rr": {
        "layer": "RISK",
        "description": "Take profit is set at a fixed risk:reward ratio from entry.",
        "params": {"rr_ratio": "float (e.g. 2.0 for 1:2 R:R)"},
        "feature_dependencies": [],
    },
    "trailing_stop": {
        "layer": "MANAGEMENT",
        "description": "Stop loss trails price by a fixed ATR distance once trade is in profit.",
        "params": {"atr_period": "int (e.g. 14)", "atr_multiple": "float (e.g. 1.0)", "activate_at_r": "float (e.g. 1.0)"},
        "feature_dependencies": ["atr_{atr_period}"],
    },
    "partial_at_r": {
        "layer": "MANAGEMENT",
        "description": "Take partial profits when trade reaches N R.",
        "params": {"r_level": "float (e.g. 1.0)", "partial_pct": "float (e.g. 50.0)"},
        "feature_dependencies": [],
    },
    "be_at_r": {
        "layer": "MANAGEMENT",
        "description": "Move stop loss to breakeven when trade reaches N R.",
        "params": {"r_level": "float (e.g. 1.0)"},
        "feature_dependencies": [],
    },
    "not_testable": {
        "layer": "ANY",
        "description": "Rule cannot be expressed as a machine-testable proxy.",
        "params": {},
        "feature_dependencies": [],
    },
}

_VOCAB_SUMMARY = "\n".join(
    f"  - {name}: {meta['description']} (layer: {meta['layer']}, params: {list(meta['params'].keys())})"
    for name, meta in PROXY_VOCABULARY.items()
    if name != "not_testable"
)

_SYSTEM_PROMPT = f"""You are a trading rule compiler. Your job is to map a single human-readable trading rule to a machine-testable proxy from a fixed vocabulary.

Available proxy types:
{_VOCAB_SUMMARY}
  - not_testable: Use when no proxy in the vocabulary fits the rule.

You must respond with a single JSON object (no markdown, no explanation outside JSON) with these exact fields:
{{
  "status": "TESTABLE" | "APPROXIMATED" | "NOT_TESTABLE",
  "proxy_type": "<one of the proxy type names above, or not_testable>",
  "proxy_params": {{...}},
  "confidence": <float 0.0–1.0>,
  "interpretation_notes": "<brief explanation of how you interpreted this rule>"
}}

Rules:
- Use "TESTABLE" when the rule maps directly to a proxy with high confidence (confidence >= 0.7).
- Use "APPROXIMATED" when the rule can only be partially captured (confidence 0.3–0.69).
- Use "NOT_TESTABLE" when the rule is too discretionary, behavioral, or vague (confidence < 0.3 or no proxy fits).
- Always fill proxy_params with valid values from the proxy type's parameter schema.
- If status is NOT_TESTABLE, set proxy_type to "not_testable" and proxy_params to {{}}.
- Keep interpretation_notes to 1–2 sentences.
"""


def _resolve_feature_dependencies(proxy_type: str, proxy_params: dict) -> list[str]:
    """Resolve feature dependency template strings with actual param values."""
    if proxy_type not in PROXY_VOCABULARY:
        return []
    deps = []
    for dep_template in PROXY_VOCABULARY[proxy_type]["feature_dependencies"]:
        try:
            dep = dep_template.format(**proxy_params)
        except KeyError:
            dep = dep_template
        deps.append(dep)
    return deps


def _build_rule_message(rule: PlanRule, plan_context: str) -> str:
    lines = [
        f"Plan context:\n{plan_context}\n",
        f"Rule to compile:",
        f"  Layer: {rule.layer}",
        f"  Name: {rule.name}",
        f"  Type: {rule.rule_type}",
        f"  Weight: {rule.weight}",
    ]
    if rule.description:
        lines.append(f"  Description: {rule.description}")
    return "\n".join(lines)


async def interpret_rule(
    rule: PlanRule,
    provider: "AIProvider",
    plan_context: str,
) -> dict:
    """
    Interpret a single rule using the AI provider.
    Returns a compiled rule dict ready for storage in CompiledPlan.compiled_rules.
    BEHAVIORAL rules are classified immediately without an AI call.
    """
    base = {
        "rule_id": str(rule.id),
        "layer": rule.layer,
        "name": rule.name,
        "description": rule.description,
        "rule_type": rule.rule_type,
        "weight": rule.weight,
        "user_confirmed": False,
    }

    if rule.layer == PlanLayer.BEHAVIORAL.value:
        return {
            **base,
            "status": InterpretationStatus.NOT_TESTABLE.value,
            "proxy": None,
            "confidence": None,
            "interpretation_notes": (
                "Behavioral rules require live enforcement and journaling. "
                "They are excluded from historical replay but tracked in the interpretability report."
            ),
            "feature_dependencies": [],
        }

    message = _build_rule_message(rule, plan_context)
    try:
        raw = await provider.chat(system=_SYSTEM_PROMPT, messages=[{"role": "user", "content": message}])
        parsed = json.loads(raw.strip())
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Rule interpretation failed for rule %s: %s", rule.id, e)
        return {
            **base,
            "status": InterpretationStatus.NOT_TESTABLE.value,
            "proxy": None,
            "confidence": None,
            "interpretation_notes": f"Interpretation failed: {e}. Rule marked as not testable.",
            "feature_dependencies": [],
        }

    proxy_type = parsed.get("proxy_type", "not_testable")
    proxy_params = parsed.get("proxy_params") or {}
    confidence = float(parsed.get("confidence", 0.0))
    status = parsed.get("status", InterpretationStatus.NOT_TESTABLE.value)
    notes = parsed.get("interpretation_notes", "")

    # Validate proxy_type against vocabulary
    if proxy_type not in PROXY_VOCABULARY:
        logger.warning("Unknown proxy type '%s' returned by AI for rule %s", proxy_type, rule.id)
        proxy_type = "not_testable"
        status = InterpretationStatus.NOT_TESTABLE.value
        proxy_params = {}
        confidence = 0.0

    # If status is NOT_TESTABLE, ensure proxy is cleared regardless of what the AI returned
    if status == InterpretationStatus.NOT_TESTABLE.value:
        proxy_type = "not_testable"
        proxy_params = {}

    proxy = None if proxy_type == "not_testable" else {"type": proxy_type, "params": proxy_params}
    feature_deps = _resolve_feature_dependencies(proxy_type, proxy_params)

    return {
        **base,
        "status": status,
        "proxy": proxy,
        "confidence": confidence,
        "interpretation_notes": notes,
        "feature_dependencies": feature_deps,
    }


async def interpret_rules(
    rules: list[PlanRule],
    provider: "AIProvider",
    plan_context: str,
) -> list[dict]:
    """Interpret all rules, returning a list of compiled rule dicts."""
    compiled = []
    for rule in rules:
        result = await interpret_rule(rule, provider, plan_context)
        compiled.append(result)
    return compiled
