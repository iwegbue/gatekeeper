"""
Runtime settings service — singleton pattern.
"""
import hashlib
import hmac
import secrets

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


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def generate_api_token(db: AsyncSession) -> str:
    """Generate a gk_ prefixed API token, store SHA-256 hash, return raw token."""
    raw_token = "gk_" + secrets.token_hex(32)
    s = await get_settings(db)
    s.api_token_hash = _hash_token(raw_token)
    await db.flush()
    return raw_token


async def verify_api_token_hash(db: AsyncSession, raw_token: str) -> bool:
    """Compare SHA-256(raw_token) against stored hash using hmac.compare_digest."""
    s = await get_settings(db)
    if not s.api_token_hash:
        return False
    return hmac.compare_digest(_hash_token(raw_token), s.api_token_hash)
