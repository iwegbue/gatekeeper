"""
Journal service — post-mortem CRUD and plan adherence calculation.

Journal entries are auto-created when a trade is closed. The user
fills in the structured review (what_went_well, lessons_learned, etc.)
and can add tags.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journal import JournalEntry, JournalTag
from app.models.trade import Trade

# ── Journal entries ────────────────────────────────────────────────────────────


async def get_entry(db: AsyncSession, entry_id: uuid.UUID) -> JournalEntry | None:
    result = await db.execute(select(JournalEntry).where(JournalEntry.id == entry_id))
    return result.scalar_one_or_none()


async def get_entry_for_trade(db: AsyncSession, trade_id: uuid.UUID) -> JournalEntry | None:
    result = await db.execute(select(JournalEntry).where(JournalEntry.trade_id == trade_id))
    return result.scalar_one_or_none()


async def list_entries(db: AsyncSession) -> list[JournalEntry]:
    result = await db.execute(select(JournalEntry).order_by(JournalEntry.created_at.desc()))
    return list(result.scalars().all())


async def create_draft(
    db: AsyncSession,
    trade: Trade,
    *,
    plan_adherence_pct: int = 100,
    rule_violations: list[str] | None = None,
) -> JournalEntry:
    """
    Auto-create a DRAFT journal entry for a closed trade.
    Captures trade summary and plan adherence at the time of close.
    """
    trade_summary = {
        "instrument": trade.instrument,
        "direction": trade.direction,
        "entry_price": float(trade.entry_price),
        "exit_price": float(trade.exit_price) if trade.exit_price else None,
        "sl_price": float(trade.sl_price),
        "risk_pct": float(trade.risk_pct),
        "r_multiple": float(trade.r_multiple) if trade.r_multiple is not None else None,
        "grade": trade.grade,
        "be_locked": trade.be_locked,
        "partials_taken": trade.partials_taken,
    }

    entry = JournalEntry(
        trade_id=trade.id,
        idea_id=trade.idea_id,
        status="DRAFT",
        trade_summary=trade_summary,
        plan_adherence_pct=plan_adherence_pct,
        rule_violations={"violated": rule_violations or []},
    )
    db.add(entry)
    await db.flush()
    return entry


async def update_entry(
    db: AsyncSession,
    entry_id: uuid.UUID,
    **kwargs,
) -> JournalEntry | None:
    entry = await get_entry(db, entry_id)
    if entry is None:
        return None
    protected = ("id", "trade_id", "idea_id", "trade_summary", "plan_adherence_pct", "rule_violations", "created_at")
    for key, value in kwargs.items():
        if hasattr(entry, key) and key not in protected:
            setattr(entry, key, value)
    await db.flush()
    return entry


async def complete_entry(db: AsyncSession, entry_id: uuid.UUID) -> JournalEntry | None:
    """Mark a draft journal entry as completed."""
    entry = await get_entry(db, entry_id)
    if entry is None:
        return None
    entry.status = "COMPLETED"
    await db.flush()
    return entry


async def delete_entry(db: AsyncSession, entry_id: uuid.UUID) -> bool:
    entry = await get_entry(db, entry_id)
    if entry is None:
        return False
    await db.delete(entry)
    await db.flush()
    return True


# ── Tags ───────────────────────────────────────────────────────────────────────


async def get_all_tags(db: AsyncSession) -> list[JournalTag]:
    result = await db.execute(select(JournalTag).order_by(JournalTag.name))
    return list(result.scalars().all())


async def get_or_create_tag(db: AsyncSession, name: str) -> JournalTag:
    name = name.strip().lower()
    result = await db.execute(select(JournalTag).where(JournalTag.name == name))
    tag = result.scalar_one_or_none()
    if tag is None:
        tag = JournalTag(name=name)
        db.add(tag)
        await db.flush()
    return tag


async def set_entry_tags(db: AsyncSession, entry_id: uuid.UUID, tag_names: list[str]) -> JournalEntry | None:
    """Replace all tags on an entry with the given tag names."""
    entry = await get_entry(db, entry_id)
    if entry is None:
        return None
    tags = []
    for name in tag_names:
        if name.strip():
            tag = await get_or_create_tag(db, name)
            tags.append(tag)
    entry.tags = tags
    await db.flush()
    return entry
