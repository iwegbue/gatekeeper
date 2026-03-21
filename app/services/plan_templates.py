"""
Curated starter trading plan templates.

Each template is a plain dict with a `name`, `description`, and a list of `rules`.
Rules are applied via `plan_service.create_rule()` during the setup wizard.
Templates are starting points — users can edit, add, or remove rules at any time.
"""

from typing import TypedDict


class RuleDefinition(TypedDict):
    layer: str
    name: str
    description: str
    rule_type: str
    weight: int


class PlanTemplate(TypedDict):
    id: str
    name: str
    description: str
    rules: list[RuleDefinition]


TEMPLATES: dict[str, PlanTemplate] = {
    "trend_following": {
        "id": "trend_following",
        "name": "Trend Following",
        "description": (
            "A disciplined trend-following framework. "
            "Entries are taken only in the direction of the higher-timeframe trend, "
            "with confirmation from momentum and a well-defined risk plan."
        ),
        "rules": [
            # CONTEXT
            {
                "layer": "CONTEXT",
                "name": "Higher timeframe trend direction identified",
                "description": "The trend on the daily/weekly chart is clearly up or down — no ranging/choppy conditions.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONTEXT",
                "name": "No high-impact news within entry window",
                "description": "Check the economic calendar. Avoid entering within 30 minutes of major scheduled events.",
                "rule_type": "REQUIRED",
                "weight": 1,
            },
            {
                "layer": "CONTEXT",
                "name": "Session is active and liquid",
                "description": "Entry is taken during the relevant session (London/NY for FX, regular hours for equities).",
                "rule_type": "ADVISORY",
                "weight": 1,
            },
            # SETUP
            {
                "layer": "SETUP",
                "name": "Key support or resistance level identified",
                "description": "A clear structural level (prior swing, round number, or zone) is defining the setup.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "SETUP",
                "name": "Price structure supports trade direction",
                "description": "Higher highs/higher lows for longs; lower highs/lower lows for shorts — structure is intact.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # CONFIRMATION
            {
                "layer": "CONFIRMATION",
                "name": "Momentum indicator aligned",
                "description": "MACD, RSI, or equivalent confirms directional momentum in the trade direction.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONFIRMATION",
                "name": "Volume or relative strength supports move",
                "description": "Volume is above average on the trigger candle, or relative strength vs market is positive.",
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # ENTRY
            {
                "layer": "ENTRY",
                "name": "Entry trigger signal present",
                "description": "A specific trigger has fired: breakout candle, pullback to level with rejection, or pattern completion.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "ENTRY",
                "name": "Entry is within the planned zone",
                "description": "Price is at or near the pre-identified entry zone — not chasing a move already extended.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # RISK
            {
                "layer": "RISK",
                "name": "Stop loss at a logical structural level",
                "description": "The stop is placed beyond a swing point, key level, or volatility-based level — not arbitrary.",
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            {
                "layer": "RISK",
                "name": "Position size within 2% account risk",
                "description": "Risk per trade does not exceed 2% of total account equity after sizing for the stop distance.",
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            # MANAGEMENT
            {
                "layer": "MANAGEMENT",
                "name": "Take-profit targets defined before entry",
                "description": "At least one TP level is identified (prior swing, measured move, or key resistance/support).",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "MANAGEMENT",
                "name": "Trailing stop or partial exit plan in place",
                "description": "A plan exists for how to manage the position as it moves in your favour (trail, scale out, breakeven).",
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # BEHAVIORAL
            {
                "layer": "BEHAVIORAL",
                "name": "Emotional state check — calm and focused",
                "description": "Not trading out of boredom, FOMO, or frustration. The setup meets the criteria on its own merits.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
        ],
    },
    "mean_reversion": {
        "id": "mean_reversion",
        "name": "Mean Reversion",
        "description": (
            "A mean reversion framework for range-bound markets. "
            "Entries are taken at extremes of a defined range with confirmation of exhaustion, "
            "targeting a return to the mean or the opposite boundary."
        ),
        "rules": [
            # CONTEXT
            {
                "layer": "CONTEXT",
                "name": "Range-bound market confirmed",
                "description": "Price has been oscillating between defined highs and lows — no impulsive trend breakout in progress.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONTEXT",
                "name": "No trending breakout in progress",
                "description": "Verify the range has not been violated on the higher timeframe. Avoid fading genuine breakouts.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONTEXT",
                "name": "No high-impact news within entry window",
                "description": "Mean reversion trades are especially vulnerable to news-driven gaps. Check the calendar.",
                "rule_type": "REQUIRED",
                "weight": 1,
            },
            # SETUP
            {
                "layer": "SETUP",
                "name": "Overextension from mean identified",
                "description": "Price is significantly stretched from the range midpoint, VWAP, or moving average (e.g. 2+ ATRs).",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "SETUP",
                "name": "Range boundary or key level tested",
                "description": "Price has reached or is testing the upper/lower boundary of the established range.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # CONFIRMATION
            {
                "layer": "CONFIRMATION",
                "name": "Oscillator divergence present",
                "description": "RSI, Stochastic, or CCI shows divergence at the extreme — a sign of fading momentum.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONFIRMATION",
                "name": "Rejection candle pattern",
                "description": "A pin bar, engulfing candle, or doji confirms rejection at the boundary level.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # ENTRY
            {
                "layer": "ENTRY",
                "name": "Entry at boundary with confirmation",
                "description": "Entry is taken at or just inside the boundary after the confirmation candle closes.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "ENTRY",
                "name": "Limit order preferred over market order",
                "description": "Where possible, use a limit order to improve entry price at the level rather than chasing.",
                "rule_type": "ADVISORY",
                "weight": 1,
            },
            # RISK
            {
                "layer": "RISK",
                "name": "Stop loss placed beyond the range boundary",
                "description": "Stop is positioned outside the range extreme — a close beyond the boundary invalidates the trade.",
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            {
                "layer": "RISK",
                "name": "Risk-reward minimum 1.5:1",
                "description": "The distance to the range midpoint (first target) must be at least 1.5× the stop distance.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # MANAGEMENT
            {
                "layer": "MANAGEMENT",
                "name": "Scale out at the range midpoint",
                "description": "Take partial profits at the mean/midpoint; let remaining position run to the opposite boundary.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "MANAGEMENT",
                "name": "Move stop to breakeven at 1R",
                "description": "Once the trade has moved 1× the initial risk in your favour, move stop to entry.",
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # BEHAVIORAL
            {
                "layer": "BEHAVIORAL",
                "name": "Patience check — waited for full setup",
                "description": "Did not enter early out of impatience. All confirmation criteria were met before entry.",
                "rule_type": "REQUIRED",
                "weight": 2,
            },
        ],
    },
}


def get_template(template_id: str) -> PlanTemplate | None:
    return TEMPLATES.get(template_id)


def list_templates() -> list[PlanTemplate]:
    return list(TEMPLATES.values())
