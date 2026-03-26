"""
Curated starter trading plan templates.

Each template is a plain dict with a `name`, `description`, `icon`, and a list of `rules`.
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
    icon: str  # Lucide icon name
    rules: list[RuleDefinition]


TEMPLATES: dict[str, PlanTemplate] = {
    "trend_pullback": {
        "id": "trend_pullback",
        "name": "Trend Pullback",
        "description": (
            "The market is moving in one direction. "
            "You wait for a temporary dip back to a key level, "
            "then enter in the original direction when it bounces. "
            "The most common price action strategy."
        ),
        "icon": "trending-up",
        "rules": [
            # CONTEXT
            {
                "layer": "CONTEXT",
                "name": "Higher-timeframe trend direction identified",
                "description": (
                    "The daily or weekly chart shows consecutive higher swing highs and higher swing lows "
                    "(for longs), or lower swing highs and lower swing lows (for shorts). "
                    "No ranging or choppy conditions — the trend must be clear."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONTEXT",
                "name": "No high-impact news within 30 minutes of entry",
                "description": (
                    "Economic calendar checked. No red-flag events scheduled within 30 minutes "
                    "of the planned entry time. News spikes can invalidate otherwise clean setups."
                ),
                "rule_type": "REQUIRED",
                "weight": 1,
            },
            {
                "layer": "CONTEXT",
                "name": "Entry is during an active trading session",
                "description": (
                    "Entry is taken during London or New York session for FX, or regular market hours "
                    "for equities and indices. Avoid low-liquidity periods (Asian session for major FX pairs)."
                ),
                "rule_type": "ADVISORY",
                "weight": 1,
            },
            # SETUP
            {
                "layer": "SETUP",
                "name": "Pullback has reached a defined value zone",
                "description": (
                    "Price has retraced to a prior support/resistance zone, order block, or the 50–61.8% "
                    "retracement of the last impulse leg. The zone must have been identified before price arrived."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "SETUP",
                "name": "Trend structure remains intact during the pullback",
                "description": (
                    "The pullback has not broken the most recent swing low on the entry timeframe (for longs), "
                    "or the most recent swing high (for shorts). If structure is broken, the trend may have ended."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # CONFIRMATION
            {
                "layer": "CONFIRMATION",
                "name": "Rejection candle has formed at the value zone",
                "description": (
                    "A pin bar, engulfing candle, or outside bar has formed at or inside the value zone, "
                    "closing back in the trend direction. The candle body must close within the zone."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONFIRMATION",
                "name": "Lower-timeframe structure has shifted in the trend direction",
                "description": (
                    "On the timeframe one step below the entry timeframe, price has made a higher low "
                    "and broken above the most recent lower high (for longs), or the inverse for shorts. "
                    "Adds confidence that the pullback is ending."
                ),
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # ENTRY
            {
                "layer": "ENTRY",
                "name": "Entry taken on the close of the rejection candle or break of its extreme",
                "description": (
                    "Enter at the close of the confirmation candle, or on a break above its high (longs) / "
                    "below its low (shorts). Entry must not be more than 25% of the candle range beyond the extreme."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "ENTRY",
                "name": "Entry price is at or inside the value zone boundary",
                "description": (
                    "Price at entry is within the pre-identified zone — not extended beyond it. "
                    "Chasing past the zone invalidates the setup's risk/reward."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # RISK
            {
                "layer": "RISK",
                "name": "Stop loss placed beyond the value zone",
                "description": (
                    "Stop is positioned beyond the opposite side of the value zone, or below/above the pullback "
                    "extreme — not an arbitrary pip distance. A close beyond this level invalidates the setup."
                ),
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            {
                "layer": "RISK",
                "name": "Position size keeps total risk within 2% of account equity",
                "description": (
                    "Risk per trade (position size × stop distance) does not exceed 2% of total account equity. "
                    "Calculated and confirmed before placing the order."
                ),
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            # MANAGEMENT
            {
                "layer": "MANAGEMENT",
                "name": "Take-profit target defined at the next structural level",
                "description": (
                    "At least one TP level is a prior swing high (longs) or swing low (shorts) that offers "
                    "a minimum 1.5:1 reward-to-risk ratio. Defined before entry, not after."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "MANAGEMENT",
                "name": "Trailing stop or partial exit plan decided before entry",
                "description": (
                    "A rule for managing the position as it moves in your favour is decided before entry — "
                    "e.g., trail behind each new higher low, scale out at 1R and 2R, or move to breakeven at 1R."
                ),
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # BEHAVIORAL
            {
                "layer": "BEHAVIORAL",
                "name": "This trade was planned — not reactive",
                "description": (
                    "The setup was identified from a watchlist or pre-session scan, not from scrolling charts "
                    "reactively. Entry is not driven by FOMO, boredom, or frustration from a previous trade."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
        ],
    },

    "break_retest": {
        "id": "break_retest",
        "name": "Break & Retest",
        "description": (
            "A key price level gets broken. "
            "Instead of chasing, you wait for price to come back and test the level "
            "from the other side, then enter when it holds."
        ),
        "icon": "arrow-up-right",
        "rules": [
            # CONTEXT
            {
                "layer": "CONTEXT",
                "name": "Key horizontal level identified on higher timeframe",
                "description": (
                    "A clearly defined support or resistance level is visible on the daily or 4H chart "
                    "with at least 2 prior touches. The more times a level has been tested, the more "
                    "significant its break will be."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONTEXT",
                "name": "No high-impact news within 30 minutes of entry",
                "description": (
                    "Economic calendar checked. No red-flag events scheduled within 30 minutes of entry. "
                    "Breakout moves near news events are often false."
                ),
                "rule_type": "REQUIRED",
                "weight": 1,
            },
            # SETUP
            {
                "layer": "SETUP",
                "name": "Level broken by a candle body close — not just a wick",
                "description": (
                    "A candle has closed decisively beyond the level. The candle body (open-to-close) "
                    "must be above resistance (or below support) — a wick-only break does not qualify."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "SETUP",
                "name": "Price has returned to retest the broken level",
                "description": (
                    "After the breakout, price has pulled back to the level (or within one ATR of it) "
                    "from the other side — testing old resistance as new support, or vice versa."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "SETUP",
                "name": "Price has not closed back through the level on the retest",
                "description": (
                    "During the retest, no candle has closed back on the wrong side of the level. "
                    "A close-back reclaim means the breakout has failed and the setup is invalidated."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # CONFIRMATION
            {
                "layer": "CONFIRMATION",
                "name": "Rejection candle has formed at the retested level",
                "description": (
                    "A pin bar, engulfing candle, or outside bar has formed at the retested level, "
                    "closing back in the breakout direction. Confirms the level is holding as flipped support/resistance."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONFIRMATION",
                "name": "Breakout candle range was larger than the 3 preceding candles",
                "description": (
                    "The breakout candle's high-to-low range exceeds the range of the 3 candles before it. "
                    "A wide breakout candle indicates genuine momentum rather than a drift through the level."
                ),
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # ENTRY
            {
                "layer": "ENTRY",
                "name": "Entry on close of rejection candle or break of its extreme",
                "description": (
                    "Enter at the close of the rejection candle at the retest, or on a break above its high "
                    "(longs) / below its low (shorts). Do not enter before the candle closes."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # RISK
            {
                "layer": "RISK",
                "name": "Stop loss placed beyond the retested level and retest wick extreme",
                "description": (
                    "Stop is on the far side of the retested level, beyond the wick extreme of the retest candle. "
                    "A close back through the level is the trade's invalidation point."
                ),
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            {
                "layer": "RISK",
                "name": "Position size keeps total risk within 2% of account equity",
                "description": (
                    "Risk per trade (position size × stop distance) does not exceed 2% of total account equity. "
                    "Calculated and confirmed before placing the order."
                ),
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            # MANAGEMENT
            {
                "layer": "MANAGEMENT",
                "name": "First take-profit at the breakout candle's extreme — minimum 1.5:1 R:R",
                "description": (
                    "TP1 is at the high (longs) or low (shorts) of the initial breakout candle. "
                    "The distance to TP1 must be at least 1.5× the stop distance."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "MANAGEMENT",
                "name": "Move stop to breakeven once the trade reaches 1R profit",
                "description": (
                    "Once price has moved 1× the initial risk distance in your favour, "
                    "move the stop to the entry price to eliminate downside risk on the remaining position."
                ),
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # BEHAVIORAL
            {
                "layer": "BEHAVIORAL",
                "name": "Waited for the retest — did not chase the initial breakout",
                "description": (
                    "Entry is on the retest, not on the breakout candle itself. "
                    "Chasing breakouts produces poor entries and inflated risk. Patience was maintained."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
        ],
    },

    "range_reversal": {
        "id": "range_reversal",
        "name": "Range Reversal",
        "description": (
            "The market is bouncing between two levels. "
            "You trade at the edges — entering when price reaches a boundary "
            "and shows signs of turning back toward the middle."
        ),
        "icon": "arrow-left-right",
        "rules": [
            # CONTEXT
            {
                "layer": "CONTEXT",
                "name": "Trading range established on higher timeframe",
                "description": (
                    "Price has bounced between a clearly defined high and low at least twice on each side "
                    "within the last 20–50 candles on the daily or 4H chart. Both boundaries are visible and unambiguous."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONTEXT",
                "name": "No breakout of the range is in progress",
                "description": (
                    "Neither range boundary has been broken by a candle body close on the higher timeframe. "
                    "A genuine breakout makes this a different trade type — do not fade it as a range reversal."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONTEXT",
                "name": "No high-impact news within 30 minutes of entry",
                "description": (
                    "Calendar checked. Range reversals are especially vulnerable to news-driven breakouts. "
                    "Avoid entering near scheduled high-impact events."
                ),
                "rule_type": "REQUIRED",
                "weight": 1,
            },
            # SETUP
            {
                "layer": "SETUP",
                "name": "Price is at or within one ATR of the range boundary",
                "description": (
                    "Price has reached the upper or lower boundary of the established range, "
                    "within 1× the 14-period ATR. The boundary must be the pre-identified range extreme."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "SETUP",
                "name": "Price is extended from the range midpoint",
                "description": (
                    "The distance from the current price to the range midpoint is at least 40% of the total "
                    "range height. Reversal trades taken near the middle have poor reward-to-risk."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # CONFIRMATION
            {
                "layer": "CONFIRMATION",
                "name": "Rejection candle has closed back inside the range",
                "description": (
                    "A pin bar, engulfing candle, or outside bar has formed at the range extreme, "
                    "with its body closing back inside the range. Wick-only tests with inside-range closes count."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONFIRMATION",
                "name": "Current touch made a lower high or higher low than the prior touch",
                "description": (
                    "At the upper boundary: the current high is lower than the prior high at resistance "
                    "(diverging momentum). At the lower boundary: the current low is higher than the prior low. "
                    "Indicates fading pressure at the extreme."
                ),
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # ENTRY
            {
                "layer": "ENTRY",
                "name": "Entry on the close of the rejection candle",
                "description": (
                    "Enter at the close of the rejection candle. Do not enter if the rejection candle's "
                    "body has closed outside the range — that is a breakout, not a reversal."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "ENTRY",
                "name": "Limit order preferred to improve fill at the boundary",
                "description": (
                    "Where execution allows, use a limit order at the boundary level rather than a market order "
                    "on the candle close. Improves entry price and reduces slippage at extremes."
                ),
                "rule_type": "ADVISORY",
                "weight": 1,
            },
            # RISK
            {
                "layer": "RISK",
                "name": "Stop loss placed beyond the range boundary with a buffer",
                "description": (
                    "Stop is positioned beyond the range extreme, with at least 0.5× ATR of buffer space. "
                    "A candle body close beyond the boundary invalidates the range and the trade."
                ),
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            {
                "layer": "RISK",
                "name": "Distance to range midpoint gives minimum 1.5:1 reward-to-risk",
                "description": (
                    "The distance from entry to the range midpoint (first target) must be at least 1.5× the stop "
                    "distance. If it does not, the entry is too far inside the range and the setup is not viable."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # MANAGEMENT
            {
                "layer": "MANAGEMENT",
                "name": "Take at least half the position off at the range midpoint",
                "description": (
                    "Close at least 50% of the position at the midpoint of the range. "
                    "Let the remainder target the opposite boundary — but only after the midpoint profit is banked."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "MANAGEMENT",
                "name": "Move stop to breakeven once the trade reaches 1R profit",
                "description": (
                    "Once price has moved 1× the initial risk in your favour, move the stop to entry. "
                    "Protects against giving back profit if the range midpoint holds as resistance."
                ),
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # BEHAVIORAL
            {
                "layer": "BEHAVIORAL",
                "name": "Waited for full confirmation at the extreme — no early entry",
                "description": (
                    "Did not enter while price was approaching the boundary, anticipating the reversal. "
                    "All confirmation criteria — candle close and setup conditions — were met before entry."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
        ],
    },

    "failed_breakout": {
        "id": "failed_breakout",
        "name": "Failed Breakout",
        "description": (
            "Price breaks through a level but quickly snaps back — "
            "trapping traders who jumped in on the breakout. "
            "You trade the reversal back into the range."
        ),
        "icon": "shield-x",
        "rules": [
            # CONTEXT
            {
                "layer": "CONTEXT",
                "name": "Key level with visible prior touches and resting liquidity",
                "description": (
                    "A support or resistance level with at least 2–3 prior touches exists on the higher timeframe. "
                    "Multiple touches suggest clusters of stop-loss orders sitting just beyond the level — "
                    "the fuel for a liquidity sweep."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONTEXT",
                "name": "No strong directional trend is in progress near the level",
                "description": (
                    "Price has been consolidating or ranging near the level, not in a sustained impulse move. "
                    "A genuine trending breakout does not reverse — do not fade real momentum."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONTEXT",
                "name": "No high-impact news within 30 minutes of entry",
                "description": (
                    "Calendar checked. News events can trigger genuine breakouts that do not reverse. "
                    "Avoid this setup around scheduled high-impact releases."
                ),
                "rule_type": "REQUIRED",
                "weight": 1,
            },
            # SETUP
            {
                "layer": "SETUP",
                "name": "Price has moved beyond the key level (liquidity sweep)",
                "description": (
                    "A candle wick or brief price move has extended beyond the level, triggering breakout orders "
                    "and stop-losses resting there. This is the sweep — it must be visible on the chart."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "SETUP",
                "name": "Price has closed back inside the level within 1–3 candles",
                "description": (
                    "Within 1 to 3 candles of the sweep, price has closed back on the original side of the level. "
                    "The breakout has failed. A quick reclaim — not a slow drift back — is required."
                ),
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            # CONFIRMATION
            {
                "layer": "CONFIRMATION",
                "name": "A trapping candle pattern has formed at the reclaim",
                "description": (
                    "An engulfing candle, pin bar with a long wick beyond the level, or an outside bar "
                    "closing back inside the range. The candle body must close on the correct (reversal) side."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONFIRMATION",
                "name": "Reversal candle range is equal to or larger than the sweep candle",
                "description": (
                    "The candle that reclaims the level has a range (high to low) that is equal to or greater "
                    "than the sweep candle. Indicates aggressive counter-flow, not a weak drift back."
                ),
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # ENTRY
            {
                "layer": "ENTRY",
                "name": "Entry on the close of the candle that reclaimed the level",
                "description": (
                    "Enter at the close of the trapping candle — the one that closed back inside the level "
                    "in the reversal direction. Do not anticipate before the candle closes."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # RISK
            {
                "layer": "RISK",
                "name": "Stop loss placed beyond the false breakout wick extreme",
                "description": (
                    "Stop is positioned beyond the farthest point of the sweep — above the sweep high "
                    "(for shorts) or below the sweep low (for longs). A new push through that extreme means the "
                    "reversal has failed."
                ),
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            {
                "layer": "RISK",
                "name": "Position size keeps total risk within 2% of account equity",
                "description": (
                    "Risk per trade (position size × stop distance) does not exceed 2% of total account equity. "
                    "Calculated and confirmed before placing the order."
                ),
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            # MANAGEMENT
            {
                "layer": "MANAGEMENT",
                "name": "Take-profit at the opposite side of the range — minimum 2:1 R:R",
                "description": (
                    "Target is the far boundary of the consolidation range or the next significant structural level. "
                    "The trapped-trader momentum from the false breakout often drives a full range traverse."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "MANAGEMENT",
                "name": "Trail stop aggressively behind new swing lows/highs after 1.5R",
                "description": (
                    "Once the trade reaches 1.5× initial risk in profit, begin trailing the stop behind each "
                    "new swing. Trapped traders exiting their positions can accelerate the move significantly."
                ),
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # BEHAVIORAL
            {
                "layer": "BEHAVIORAL",
                "name": "This is a planned reversal — not frustration from missing the breakout",
                "description": (
                    "The trade is based on a clear failed-breakout pattern, not on regret or annoyance from "
                    "missing the initial move. Revenge-trading a missed breakout with the inverse setup is a "
                    "common emotional error."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
        ],
    },

    "inside_bar_breakout": {
        "id": "inside_bar_breakout",
        "name": "Inside Bar Breakout",
        "description": (
            "A candle forms entirely within the previous candle's range, "
            "signalling that the market is compressing. "
            "You trade the expansion when price breaks out of that tight range."
        ),
        "icon": "minimize-2",
        "rules": [
            # CONTEXT
            {
                "layer": "CONTEXT",
                "name": "A directional bias exists from higher-timeframe context",
                "description": (
                    "There is a higher-timeframe trend, a key level nearby, or a chart pattern that gives a "
                    "directional bias for the expected breakout. Inside bars without context produce low-quality setups."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONTEXT",
                "name": "No high-impact news within 30 minutes of entry",
                "description": (
                    "Calendar checked. News events can trigger erratic spikes through the inside bar "
                    "that reverse immediately — invalidating the pattern's edge."
                ),
                "rule_type": "REQUIRED",
                "weight": 1,
            },
            {
                "layer": "CONTEXT",
                "name": "Inside bar is part of a visible tightening of ranges",
                "description": (
                    "The inside bar is one of 2 or more progressively narrowing candles, not an isolated "
                    "inside bar in the middle of random choppy price action. A compression sequence improves reliability."
                ),
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # SETUP
            {
                "layer": "SETUP",
                "name": "A valid inside bar is confirmed",
                "description": (
                    "The current candle's high is strictly below the prior candle's high AND its low is strictly "
                    "above the prior candle's low. The inside bar is fully contained within the mother candle. "
                    "An equal high or low does not qualify."
                ),
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            {
                "layer": "SETUP",
                "name": "Mother candle range is not more than 2× the 14-period ATR",
                "description": (
                    "The prior candle (mother candle) range does not exceed 2× the average true range of the "
                    "last 14 candles. An outsized mother candle produces an inside bar with a stop that is "
                    "too large to offer viable risk/reward."
                ),
                "rule_type": "REQUIRED",
                "weight": 1,
            },
            # CONFIRMATION
            {
                "layer": "CONFIRMATION",
                "name": "A candle has closed beyond the inside bar high or low — not just a wick",
                "description": (
                    "The breakout candle's body (open-to-close) must close beyond the inside bar's high (for longs) "
                    "or low (for shorts). A wick-only extension that closes back inside the bar is not a confirmation."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "CONFIRMATION",
                "name": "Breakout direction aligns with the higher-timeframe directional bias",
                "description": (
                    "The breakout is in the same direction as the trend, key level, or pattern context identified "
                    "in the CONTEXT layer. Counter-trend inside bar breakouts have significantly lower win rates."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # ENTRY
            {
                "layer": "ENTRY",
                "name": "Entry on the close of the breakout candle, or retest of the inside bar range",
                "description": (
                    "Enter at the close of the candle that confirmed the breakout, or on a pullback to "
                    "the broken inside bar high (for longs) or low (for shorts). Both are valid — "
                    "the retest entry typically offers a tighter stop."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            # RISK
            {
                "layer": "RISK",
                "name": "Stop loss placed on the opposite side of the inside bar",
                "description": (
                    "For a long breakout, stop is below the inside bar low. For a short, stop is above the "
                    "inside bar high. The inside bar defines the compression zone — a break of its opposite "
                    "extreme invalidates the setup."
                ),
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            {
                "layer": "RISK",
                "name": "Position size keeps total risk within 2% of account equity",
                "description": (
                    "Risk per trade (position size × stop distance) does not exceed 2% of total account equity. "
                    "Calculated and confirmed before placing the order."
                ),
                "rule_type": "REQUIRED",
                "weight": 3,
            },
            # MANAGEMENT
            {
                "layer": "MANAGEMENT",
                "name": "First take-profit at 1.5× the mother candle range — measured from entry",
                "description": (
                    "TP1 is at 1.5× the height of the mother candle, measured from the breakout point. "
                    "This approximates the expansion target after the compression — a measured move."
                ),
                "rule_type": "REQUIRED",
                "weight": 2,
            },
            {
                "layer": "MANAGEMENT",
                "name": "Move stop to breakeven once the trade reaches 1R profit",
                "description": (
                    "Once price moves 1× initial risk in the breakout direction, move the stop to the entry price. "
                    "Compression breakouts can reverse quickly if the move lacks follow-through."
                ),
                "rule_type": "OPTIONAL",
                "weight": 1,
            },
            # BEHAVIORAL
            {
                "layer": "BEHAVIORAL",
                "name": "Entry was on the confirmed candle close — not an anticipatory entry",
                "description": (
                    "Did not place a buy/sell stop order inside the inside bar, nor enter before the breakout "
                    "candle closed. The entry is based on confirmed price action, not anticipation of the break."
                ),
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
