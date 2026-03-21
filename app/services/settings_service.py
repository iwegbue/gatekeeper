"""
Runtime settings service — singleton pattern.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import Settings


async def get_settings(db: AsyncSession) -> Settings:
    result = await db.execute(select(Settings).limit(1))
    s = result.scalar_one_or_none()
    if s is None:
        s = Settings()
        db.add(s)
        await db.flush()
    return s


async def update_settings(db: AsyncSession, **kwargs) -> Settings:
    s = await get_settings(db)
    for key, value in kwargs.items():
        if hasattr(s, key) and key != "id":
            setattr(s, key, value)
    await db.flush()
    return s
