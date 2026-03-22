"""
AI service — builds prompts and dispatches to the active provider.

Four features:
  1. plan_builder  — converts plain-language strategy to structured rules
  2. idea_review   — analyzes an idea against plan rules, flags issues
  3. journal_coach — reviews a journal entry, identifies patterns
  4. rule_clarity  — pushes vague rules toward precision
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_analysis import AIAnalysis

if TYPE_CHECKING:
    from app.services.ai.base import AIProvider


# ── Prompt building ────────────────────────────────────────────────────────────


async def _build_plan_context(db: AsyncSession) -> str:
    """Summarize the trading plan and its rules for AI context."""
    from app.services.plan_service import get_plan, get_rules_by_layer

    plan = await get_plan(db)
    rules_by_layer = await get_rules_by_layer(db, plan.id)

    lines = [f"Trading Plan: {plan.name}"]
    if plan.description:
        lines.append(f"Description: {plan.description}")
    lines.append("")

    for layer, rules in rules_by_layer.items():
        if rules:
            lines.append(f"[{layer}]")
            for rule in rules:
                marker = "REQUIRED" if rule.rule_type == "REQUIRED" else rule.rule_type
                lines.append(f"  - ({marker}, weight={rule.weight}) {rule.name}")
                if rule.description:
                    lines.append(f"      {rule.description}")
    return "\n".join(lines)


async def _build_idea_context(db: AsyncSession, idea_id: uuid.UUID) -> str:
    """Summarize an idea and its current checklist state."""
    from app.services.checklist_service import compute_score, get_checks_with_rules
    from app.services.idea_service import get_idea

    idea = await get_idea(db, idea_id)
    if idea is None:
        return "Idea not found."

    checked_score, total_score = await compute_score(db, idea_id)
    pct = int(checked_score * 100 / total_score) if total_score > 0 else 0

    lines = [
        f"Idea: {idea.instrument} {idea.direction}",
        f"State: {idea.state}",
        f"Grade: {idea.grade or 'ungraded'}",
        f"Score: {pct}% ({checked_score}/{total_score})",
        "",
        "Checklist:",
    ]
    pairs = await get_checks_with_rules(db, idea_id)
    for check, rule in pairs:
        status = "✓" if check.checked else "✗"
        lines.append(f"  {status} [{rule.layer}] {rule.name} ({rule.rule_type})")
        if check.notes:
            lines.append(f"      Note: {check.notes}")

    return "\n".join(lines)


# ── AI features ────────────────────────────────────────────────────────────────


async def plan_builder_chat(
    db: AsyncSession,
    provider: "AIProvider",
    conversation: list[dict],
) -> str:
    """
    Multi-turn plan building wizard.
    conversation is a list of {"role": "user"|"assistant", "content": str}.
    Returns the assistant's next response.
    """
    system = (
        "You are a trading plan architect. Help the user define clear, "
        "testable trading rules organized into 7 layers: CONTEXT, SETUP, "
        "CONFIRMATION, ENTRY, RISK, MANAGEMENT, BEHAVIORAL.\n\n"
        "For each rule suggest:\n"
        "- Name (short, imperative)\n"
        "- Layer\n"
        "- Type: REQUIRED (must be met), OPTIONAL (improves score), ADVISORY (reminder)\n"
        "- Weight: 1–3 (how much it counts toward the grade)\n"
        "- Description: what exactly to check\n\n"
        "Ask clarifying questions to make rules precise and testable. "
        "Avoid vague criteria like 'good setup'. "
        "When the user has defined enough rules, offer to summarize them in a structured list."
    )
    response = await provider.chat(system=system, messages=conversation)
    await _save_analysis(db, trigger="plan_builder", reasoning=response)
    return response


async def idea_review(
    db: AsyncSession,
    provider: "AIProvider",
    idea_id: uuid.UUID,
) -> str:
    """
    Review an idea against the plan rules.
    Returns AI commentary as a string.
    """
    plan_ctx = await _build_plan_context(db)
    idea_ctx = await _build_idea_context(db, idea_id)

    system = (
        "You are a trading discipline coach. Review the idea against the trading plan. "
        "Identify: (1) which unchecked rules are most critical and why, "
        "(2) any inconsistencies or red flags, (3) what would strengthen this setup. "
        "Be concise and specific. Do not tell the user whether to take the trade."
    )
    messages = [{"role": "user", "content": f"{plan_ctx}\n\n---\n\n{idea_ctx}"}]
    response = await provider.chat(system=system, messages=messages)
    await _save_analysis(db, trigger="idea_review", idea_id=idea_id, reasoning=response)
    return response


async def journal_coach(
    db: AsyncSession,
    provider: "AIProvider",
    entry_id: uuid.UUID,
) -> str:
    """
    Review a journal entry and identify behavioral patterns.
    Returns AI coaching as a string.
    """
    from app.services.journal_service import get_entry

    entry = await get_entry(db, entry_id)
    if entry is None:
        return "Journal entry not found."

    ts = entry.trade_summary or {}
    violations = entry.rule_violations or {}
    violated = violations.get("violated", [])

    summary = [
        f"Trade: {ts.get('instrument', '?')} {ts.get('direction', '?')}",
        f"R-multiple: {ts.get('r_multiple', 'N/A')}",
        f"Grade: {ts.get('grade', 'N/A')}",
        f"Plan adherence: {entry.plan_adherence_pct}%",
        f"Unchecked required rules: {', '.join(violated) if violated else 'none'}",
        "",
        f"What went well: {entry.what_went_well or 'N/A'}",
        f"What went wrong: {entry.what_went_wrong or 'N/A'}",
        f"Lessons: {entry.lessons_learned or 'N/A'}",
        f"Emotions: {entry.emotions or 'N/A'}",
        f"Would take again: {entry.would_take_again}",
    ]

    system = (
        "You are a trading psychology coach. Review this post-trade journal entry. "
        "Identify behavioral patterns, emotional biases, and specific actions to improve. "
        "Focus on process adherence, not outcome. Be direct and constructive."
    )
    messages = [{"role": "user", "content": "\n".join(summary)}]
    response = await provider.chat(system=system, messages=messages)
    await _save_analysis(db, trigger="journal_coach", reasoning=response)
    return response


async def rule_clarity_check(
    db: AsyncSession,
    provider: "AIProvider",
    rule_name: str,
    rule_description: str | None,
    layer: str,
) -> str:
    """
    Analyze a single rule for clarity and suggest improvements.
    Returns AI feedback as a string.
    """
    rule_text = f"Rule: {rule_name}"
    if rule_description:
        rule_text += f"\nDescription: {rule_description}"
    rule_text += f"\nLayer: {layer}"

    system = (
        "You are a trading plan quality reviewer. Evaluate this trading rule for: "
        "(1) Precision — is it objectively verifiable? "
        "(2) Completeness — does it tell the trader exactly what to check? "
        "(3) Edge — does it describe a genuine edge? "
        "Suggest a rewrite if the rule is vague. Keep feedback concise (3–5 sentences)."
    )
    messages = [{"role": "user", "content": rule_text}]
    response = await provider.chat(system=system, messages=messages)
    await _save_analysis(db, trigger="rule_clarity", reasoning=response)
    return response


# ── Persistence ────────────────────────────────────────────────────────────────


async def _save_analysis(
    db: AsyncSession,
    *,
    trigger: str,
    idea_id: uuid.UUID | None = None,
    reasoning: str = "",
) -> AIAnalysis:
    analysis = AIAnalysis(
        idea_id=idea_id,
        trigger=trigger,
        status="COMPLETED",
        reasoning=reasoning,
    )
    db.add(analysis)
    await db.flush()
    return analysis
