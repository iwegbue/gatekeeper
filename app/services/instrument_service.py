"""
Instrument (watchlist) CRUD service.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument


async def get_all(db: AsyncSession) -> list[Instrument]:
    result = await db.execute(select(Instrument).order_by(Instrument.priority.desc(), Instrument.symbol))
    return list(result.scalars().all())


async def get_enabled(db: AsyncSession) -> list[Instrument]:
    result = await db.execute(
        select(Instrument)
        .where(Instrument.is_enabled.is_(True))
        .order_by(Instrument.priority.desc(), Instrument.symbol)
    )
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, instrument_id: uuid.UUID) -> Instrument | None:
    result = await db.execute(select(Instrument).where(Instrument.id == instrument_id))
    return result.scalar_one_or_none()


async def get_by_symbol(db: AsyncSession, symbol: str) -> Instrument | None:
    result = await db.execute(select(Instrument).where(Instrument.symbol == symbol))
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    *,
    symbol: str,
    display_name: str,
    asset_class: str = "FX",
    is_enabled: bool = True,
    priority: int = 0,
    notes: str | None = None,
) -> Instrument:
    instrument = Instrument(
        symbol=symbol,
        display_name=display_name,
        asset_class=asset_class,
        is_enabled=is_enabled,
        priority=priority,
        notes=notes,
    )
    db.add(instrument)
    await db.flush()
    return instrument


async def update_instrument(db: AsyncSession, instrument_id: uuid.UUID, **kwargs) -> Instrument | None:
    inst = await get_by_id(db, instrument_id)
    if inst is None:
        return None
    for key, value in kwargs.items():
        if hasattr(inst, key) and key != "id":
            setattr(inst, key, value)
    await db.flush()
    return inst


async def delete_instrument(db: AsyncSession, instrument_id: uuid.UUID) -> bool:
    inst = await get_by_id(db, instrument_id)
    if inst is None:
        return False
    await db.delete(inst)
    await db.flush()
    return True
