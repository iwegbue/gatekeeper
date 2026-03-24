"""
Plan Review service — AI-powered analysis of a trading plan based on a sample
of real trades and journal entries.

Strategy:
  1. Check eligibility: count completed journal entries for the active plan.
  2. On run: fetch the last N completed journal entries, compute per-rule stats,
     build a structured AI prompt, and persist the resulting report.

The review operates on the active plan. Each review is plan-scoped and
stored as a PlanReview record.
"""

import json
import logging
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journal import JournalEntry
from app.models.plan_review import PlanReview
from app.services import plan_service, settings_service

if TYPE_CHECKING:
    from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

# ── System prompt ──────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a trading plan analyst. You are given:
1. A trader's plan rules (layer, name, description, rule type)
2. Per-rule statistics: how often the rule was followed, and win rates when followed vs. skipped
3. A sample of individual trade summaries including grade, R-multiple, rule violations, and journal notes

Your job is to produce a structured review of whether the plan is working and what should change.

You must respond with a single JSON object only — no markdown code fences, no preamble — with these exact fields:
{
  "summary": "<2-3 sentence overall assessment>",
  "rule_performance": [
    {
      "rule_name": "<exact rule name>",
      "layer": "<layer>",
      "adherence_pct": <float 0-100>,
      "win_rate_when_followed": <float 0-1 or null if insufficient data>,
      "win_rate_when_skipped": <float 0-1 or null if insufficient data>,
      "verdict": "keep" | "review" | "remove",
      "notes": "<1-2 sentences explaining verdict>"
    }
  ],
  "assumptions_held": ["<plain-language statement of an assumption the data supports>"],
  "assumptions_challenged": ["<plain-language statement of an assumption the data calls into question>"],
  "suggested_changes": ["<specific, actionable suggestion>"],
  "overall_verdict": "keep" | "refine" | "overhaul"
}

Rules:
- "keep": plan is working well; no major changes needed
- "refine": specific rules or parameters need adjustment
- "overhaul": the plan's core assumptions are not holding up; significant rework needed
- For rule verdicts: "keep" = performing as expected, "review" = unclear or borderline, "remove" = consistently not contributing or correlated with worse outcomes
- Be direct and specific. Vague suggestions ("trade better") are not useful.
- If a rule has insufficient data to assess (e.g. always followed, never skipped), note this in the notes field and use "keep" as the verdict.
- Keep interpretation_notes to 1-2 sentences per rule.
"""


# ── Data assembly ──────────────────────────────────────────────────────────────


def _compute_rule_stats(entries: list[JournalEntry], rule_names: list[str]) -> dict[str, dict]:
    """
    Compute per-rule adherence and win rates from a list of completed journal entries.

    Returns a dict keyed by rule name with:
      - followed_count: int
      - skipped_count: int
      - adherence_pct: float
      - wins_when_followed: int
      - trades_when_followed: int
      - wins_when_skipped: int
      - trades_when_skipped: int
    """
    stats: dict[str, dict] = {
        name: {
            "followed_count": 0,
            "skipped_count": 0,
            "wins_when_followed": 0,
            "trades_when_followed": 0,
            "wins_when_skipped": 0,
            "trades_when_skipped": 0,
        }
        for name in rule_names
    }

    for entry in entries:
        violations = set((entry.rule_violations or {}).get("violated", []))
        r_multiple = (entry.trade_summary or {}).get("r_multiple")
        is_win = r_multiple is not None and r_multiple > 0

        for name in rule_names:
            skipped = name in violations
            if skipped:
                stats[name]["skipped_count"] += 1
                stats[name]["trades_when_skipped"] += 1
                if is_win:
                    stats[name]["wins_when_skipped"] += 1
            else:
                stats[name]["followed_count"] += 1
                stats[name]["trades_when_followed"] += 1
                if is_win:
                    stats[name]["wins_when_followed"] += 1

    # Compute adherence_pct
    n = len(entries)
    for name in rule_names:
        s = stats[name]
        s["adherence_pct"] = round(s["followed_count"] * 100 / n, 1) if n > 0 else 100.0

    return stats


def _build_review_context(plan, rules_by_layer: dict, entries: list[JournalEntry], rule_stats: dict) -> str:
    """Build the human-readable context sent to the AI as the user message."""
    lines = [
        f"Trading Plan: {plan.name}",
    ]
    if plan.description:
        lines.append(f"Description: {plan.description}")

    lines.append("\n=== PLAN RULES ===")
    for layer, layer_rules in rules_by_layer.items():
        for r in layer_rules:
            lines.append(f"[{layer}] {r.name} ({r.rule_type})")
            if r.description:
                lines.append(f"  {r.description}")

    lines.append("\n=== PER-RULE STATISTICS ===")
    lines.append(f"Sample size: {len(entries)} completed trades")
    for name, s in rule_stats.items():
        followed_wr = (
            round(s["wins_when_followed"] / s["trades_when_followed"], 2)
            if s["trades_when_followed"] > 0 else None
        )
        skipped_wr = (
            round(s["wins_when_skipped"] / s["trades_when_skipped"], 2)
            if s["trades_when_skipped"] > 0 else None
        )
        lines.append(
            f"  {name}: adherence={s['adherence_pct']}%, "
            f"win_rate_followed={followed_wr}, win_rate_skipped={skipped_wr}"
        )

    lines.append("\n=== TRADE SUMMARIES ===")
    for i, entry in enumerate(entries, 1):
        ts = entry.trade_summary or {}
        violations = (entry.rule_violations or {}).get("violated", [])
        lines.append(
            f"Trade {i}: {ts.get('instrument', '?')} {ts.get('direction', '?')} | "
            f"grade={ts.get('grade', '?')} | R={ts.get('r_multiple', '?')} | "
            f"violations={violations or 'none'}"
        )
        if entry.what_went_well:
            lines.append(f"  Well: {entry.what_went_well[:200]}")
        if entry.what_went_wrong:
            lines.append(f"  Wrong: {entry.what_went_wrong[:200]}")
        if entry.lessons_learned:
            lines.append(f"  Lesson: {entry.lessons_learned[:200]}")

    return "\n".join(lines)


def _parse_review_response(raw: str | None) -> dict:
    if raw is None:
        raise ValueError("The model returned no text.")
    text = raw.strip()
    if not text:
        raise ValueError("The model returned an empty response.")

    fence = _JSON_FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start == -1:
            raise ValueError("The model response did not contain a JSON object.") from None
        try:
            obj, _ = json.JSONDecoder().raw_decode(text, start)
        except json.JSONDecodeError as e:
            raise ValueError("The model returned invalid JSON.") from e

    if not isinstance(obj, dict):
        raise ValueError("The model returned JSON that is not a single object.")
    return obj


# ── Public API ─────────────────────────────────────────────────────────────────


async def get_review_eligibility(db: AsyncSession, plan_id: uuid.UUID) -> dict:
    """
    Check whether a plan review can be run for the given plan.

    Returns:
        eligible: bool
        completed_count: int — number of completed journal entries for this plan
        required: int — configured sample size
        last_review_at: datetime | None — when the most recent review was run
    """
    settings = await settings_service.get_settings(db)
    required = settings.plan_review_sample_size

    # Count completed journal entries linked to ideas under this plan
    from app.models.idea import Idea

    result = await db.execute(
        select(JournalEntry)
        .join(Idea, JournalEntry.idea_id == Idea.id)
        .where(Idea.plan_id == plan_id)
        .where(JournalEntry.status == "COMPLETED")
    )
    entries = list(result.scalars().all())
    completed_count = len(entries)

    # Last review date
    last_review_result = await db.execute(
        select(PlanReview)
        .where(PlanReview.plan_id == plan_id)
        .where(PlanReview.status == "COMPLETED")
        .order_by(PlanReview.completed_at.desc())
        .limit(1)
    )
    last_review = last_review_result.scalar_one_or_none()

    return {
        "eligible": completed_count >= required,
        "completed_count": completed_count,
        "required": required,
        "last_review_at": last_review.completed_at if last_review else None,
    }


async def run_plan_review(
    db: AsyncSession,
    provider: "AIProvider",
    plan_id: uuid.UUID,
) -> PlanReview:
    """
    Run a plan review for the given plan.

    Fetches the last N completed journal entries, computes per-rule stats,
    calls the AI provider, and persists the resulting PlanReview.
    """
    settings = await settings_service.get_settings(db)
    n = settings.plan_review_sample_size

    plan = await plan_service.get_plan_by_id(db, plan_id)
    rules_by_layer = await plan_service.get_rules_by_layer(db, plan_id, active_only=True)
    all_rules = [r for rules in rules_by_layer.values() for r in rules]
    rule_names = [r.name for r in all_rules]

    # Fetch last N completed journal entries for this plan, ordered by most recent
    from app.models.idea import Idea

    result = await db.execute(
        select(JournalEntry)
        .join(Idea, JournalEntry.idea_id == Idea.id)
        .where(Idea.plan_id == plan_id)
        .where(JournalEntry.status == "COMPLETED")
        .order_by(JournalEntry.created_at.desc())
        .limit(n)
    )
    entries = list(result.scalars().all())

    now = datetime.now(timezone.utc)

    if not entries:
        review = PlanReview(
            plan_id=plan_id,
            trade_window_start=now,
            trade_window_end=now,
            trade_count=0,
            status="FAILED",
            error_message="No completed journal entries found for this plan.",
        )
        db.add(review)
        await db.flush()
        return review

    trade_window_start = min(e.created_at for e in entries)
    trade_window_end = max(e.created_at for e in entries)

    rule_stats = _compute_rule_stats(entries, rule_names)
    context = _build_review_context(plan, rules_by_layer, entries, rule_stats)

    # Compute aggregate stats for the report
    r_multiples = [
        (e.trade_summary or {}).get("r_multiple")
        for e in entries
        if (e.trade_summary or {}).get("r_multiple") is not None
    ]
    win_rate = round(sum(1 for r in r_multiples if r > 0) / len(r_multiples), 3) if r_multiples else 0.0
    avg_r = round(sum(r_multiples) / len(r_multiples), 3) if r_multiples else None

    try:
        raw = await provider.chat(system=_SYSTEM_PROMPT, messages=[{"role": "user", "content": context}])
        parsed = _parse_review_response(raw)
    except Exception as e:
        logger.warning("Plan review AI call failed for plan %s: %s", plan_id, e)
        review = PlanReview(
            plan_id=plan_id,
            trade_window_start=trade_window_start,
            trade_window_end=trade_window_end,
            trade_count=len(entries),
            status="FAILED",
            error_message=str(e),
        )
        db.add(review)
        await db.flush()
        return review

    report = {
        "summary": parsed.get("summary", ""),
        "sample_size": len(entries),
        "win_rate": win_rate,
        "avg_r": avg_r,
        "rule_performance": parsed.get("rule_performance", []),
        "assumptions_held": parsed.get("assumptions_held", []),
        "assumptions_challenged": parsed.get("assumptions_challenged", []),
        "suggested_changes": parsed.get("suggested_changes", []),
        "overall_verdict": parsed.get("overall_verdict", "refine"),
    }

    review = PlanReview(
        plan_id=plan_id,
        trade_window_start=trade_window_start,
        trade_window_end=trade_window_end,
        trade_count=len(entries),
        status="COMPLETED",
        report=report,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(review)
    await db.flush()
    return review


async def list_plan_reviews(db: AsyncSession, plan_id: uuid.UUID) -> list[PlanReview]:
    result = await db.execute(
        select(PlanReview)
        .where(PlanReview.plan_id == plan_id)
        .order_by(PlanReview.created_at.desc())
    )
    return list(result.scalars().all())


async def get_plan_review(db: AsyncSession, review_id: uuid.UUID) -> PlanReview | None:
    result = await db.execute(select(PlanReview).where(PlanReview.id == review_id))
    return result.scalar_one_or_none()
