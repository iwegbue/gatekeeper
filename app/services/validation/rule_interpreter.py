"""
Rule interpreter — classifies each trading rule by its data-source requirements.

Strategy: AI proposes, user confirms.
- Each rule is sent to the AI provider with a data-source classification prompt.
- The AI answers one question: "Can this rule be evaluated using only OHLC/volume data?"
- BEHAVIORAL rules are auto-classified as LIVE_ONLY (no AI call).
- Results are returned as CompiledRule dicts; persisted by plan_compiler.

Phase 1 statuses:
  OHLC_COMPUTABLE  — rule can be fully evaluated from OHLC + derived indicators
  OHLC_APPROXIMATE — rule can be partially captured from OHLC with some loss of fidelity
  LIVE_ONLY        — rule requires data or judgment that cannot be derived from OHLC bars

Note: The proxy vocabulary (fixed set of named proxy types used by the replay engine)
is Phase 2 infrastructure and does not belong here. Phase 1 only answers the
data-source question; Phase 2 maps computable rules to concrete replay computations.
"""

import json
import logging
import re
from typing import TYPE_CHECKING

from app.models.enums import InterpretationStatus, PlanLayer
from app.models.plan_rule import PlanRule

if TYPE_CHECKING:
    from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)

# ── Phase 1 classification prompt ─────────────────────────────────────────────
#
# The AI answers one question per rule:
#   "Does evaluating this rule require data that cannot be derived from OHLC bars?"
#
# OHLC-derivable data includes: open, high, low, close, volume, and any standard
# technical indicator computed solely from those fields (moving averages, RSI, MACD,
# Bollinger Bands, ATR, stochastics, swing highs/lows, candlestick patterns, etc.)
# as well as time/session metadata (timestamp, session name, day of week).
#
# NOT OHLC-derivable: order flow, depth of market, commitment of traders,
# news/sentiment feeds, broker-specific data, proprietary third-party signals,
# or any rule that requires human discretionary judgment in the moment.

_SYSTEM_PROMPT = """You are a trading rule classifier. Your job is to determine whether a single trading rule can be evaluated using only historical OHLC price data (open, high, low, close, volume).

A rule is OHLC-computable if it can be fully evaluated using:
- Raw OHLC bars and volume
- Any standard technical indicator derived from OHLC/volume (moving averages, RSI, MACD, Bollinger Bands, ATR, stochastics, ADX, etc.)
- Candlestick pattern recognition (pin bars, engulfing, inside bars, etc.)
- Price structure concepts (swing highs/lows, prior day high/low, consolidation ranges)
- Time and session metadata (timestamp, trading session name, day of week)

A rule is LIVE_ONLY if evaluating it requires:
- Order flow, tape reading, or depth of market
- Sentiment data, news feeds, or economic calendars
- Proprietary third-party signals or indicators not derivable from OHLC
- Real-time broker data (spread, slippage, liquidity)
- Discretionary human judgment that cannot be reduced to a formula

You must respond with a single JSON object only — no markdown code fences, no preamble — with these exact fields:
{
  "status": "OHLC_COMPUTABLE" | "OHLC_APPROXIMATE" | "LIVE_ONLY",
  "data_sources_required": ["<free-form description of each data stream needed, e.g. 'macd_histogram(12,26,9)', 'rsi(14)', 'swing_high(5 bars)'>"],
  "confidence": <float 0.0–1.0>,
  "interpretation_notes": "<1–2 sentences explaining your classification>"
}

Rules:
- Use "OHLC_COMPUTABLE" when the rule maps cleanly to a computation from OHLC data (confidence >= 0.7).
- Use "OHLC_APPROXIMATE" when the rule can be partially captured from OHLC but with some loss of fidelity (confidence 0.3–0.69), or when the rule is somewhat ambiguous but has an OHLC proxy.
- Use "LIVE_ONLY" when the rule requires data or judgment beyond what OHLC bars can provide.
- data_sources_required should list the specific indicators or data streams needed. Leave empty for LIVE_ONLY rules.
- Keep interpretation_notes to 1–2 sentences.
"""


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _parse_compiler_response(raw: str | None) -> dict:
    """
    Parse the model's reply into a dict. Models often wrap JSON in markdown fences
    or add a short preamble despite instructions; empty replies also occur when
    the provider drops content.
    """
    if raw is None:
        raise ValueError("The model returned no text.")
    text = raw.strip()
    if not text:
        raise ValueError("The model returned an empty response.")

    fence = _JSON_FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    if not text:
        raise ValueError("The model returned only empty markdown.")

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start == -1:
            raise ValueError(
                "The model response did not contain a JSON object."
            ) from None
        try:
            obj, _ = json.JSONDecoder().raw_decode(text, start)
        except json.JSONDecodeError as e:
            raise ValueError("The model returned invalid JSON.") from e

    if not isinstance(obj, dict):
        raise ValueError(
            "The model returned JSON that is not a single object "
            "(an object with status, data_sources_required, etc. was expected)."
        )
    return obj


def _build_rule_message(rule: PlanRule, plan_context: str) -> str:
    lines = [
        f"Plan context:\n{plan_context}\n",
        "Rule to classify:",
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
    Classify a single rule by its data-source requirements.
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
            "status": InterpretationStatus.LIVE_ONLY.value,
            "data_sources_required": [],
            "confidence": None,
            "interpretation_notes": (
                "Behavioral rules require live enforcement and journaling. "
                "They are excluded from historical replay but tracked in the interpretability report."
            ),
        }

    message = _build_rule_message(rule, plan_context)
    try:
        raw = await provider.chat(system=_SYSTEM_PROMPT, messages=[{"role": "user", "content": message}])
        parsed = _parse_compiler_response(raw)
    except ValueError as e:
        logger.warning("Rule interpretation failed for rule %s: %s", rule.id, e)
        return {
            **base,
            "status": InterpretationStatus.LIVE_ONLY.value,
            "data_sources_required": [],
            "confidence": None,
            "interpretation_notes": f"{e} Rule marked as live-only.",
        }
    except Exception as e:
        logger.warning("Rule interpretation failed for rule %s: %s", rule.id, e)
        return {
            **base,
            "status": InterpretationStatus.LIVE_ONLY.value,
            "data_sources_required": [],
            "confidence": None,
            "interpretation_notes": f"Interpretation failed: {e}. Rule marked as live-only.",
        }

    status = parsed.get("status", InterpretationStatus.LIVE_ONLY.value)
    data_sources = parsed.get("data_sources_required") or []
    confidence = float(parsed.get("confidence", 0.0))
    notes = parsed.get("interpretation_notes", "")

    # Validate status is one of the expected Phase 1 values
    valid_statuses = {
        InterpretationStatus.OHLC_COMPUTABLE.value,
        InterpretationStatus.OHLC_APPROXIMATE.value,
        InterpretationStatus.LIVE_ONLY.value,
    }
    if status not in valid_statuses:
        logger.warning("Unexpected status '%s' returned by AI for rule %s; defaulting to LIVE_ONLY", status, rule.id)
        status = InterpretationStatus.LIVE_ONLY.value

    if status == InterpretationStatus.LIVE_ONLY.value:
        data_sources = []

    return {
        **base,
        "status": status,
        "data_sources_required": data_sources if isinstance(data_sources, list) else [],
        "confidence": confidence,
        "interpretation_notes": notes,
    }


async def interpret_rules(
    rules: list[PlanRule],
    provider: "AIProvider",
    plan_context: str,
) -> list[dict]:
    """Classify all rules, returning a list of compiled rule dicts."""
    compiled = []
    for rule in rules:
        result = await interpret_rule(rule, provider, plan_context)
        compiled.append(result)
    return compiled
