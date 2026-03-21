"""
Runtime settings service — singleton pattern.
"""
import hashlib
import hmac
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import Settings

# scrypt parameters — deliberately conservative for a password hash
_SCRYPT_N = 2**14  # CPU/memory cost (16 384)
_SCRYPT_R = 8
_SCRYPT_P = 1


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


def _hash_password(password: str) -> str:
    """Return a storable scrypt hash string: '<hex-salt>$<hex-hash>'."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return salt.hex() + "$" + digest.hex()


def _verify_password(password: str, stored: str) -> bool:
    """Constant-time comparison of password against a stored scrypt hash string."""
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    candidate = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return hmac.compare_digest(candidate.hex(), hash_hex)


async def set_admin_password(db: AsyncSession, password: str) -> None:
    """Hash and store the admin password in the settings row."""
    s = await get_settings(db)
    s.admin_password_hash = _hash_password(password)
    await db.flush()


async def verify_admin_password(db: AsyncSession, password: str) -> bool:
    """Return True if password matches the stored scrypt hash."""
    s = await get_settings(db)
    if not s.admin_password_hash:
        return False
    return _verify_password(password, s.admin_password_hash)


async def admin_password_is_set(db: AsyncSession) -> bool:
    """Return True when an admin password hash exists in the DB."""
    s = await get_settings(db)
    return bool(s.admin_password_hash)
