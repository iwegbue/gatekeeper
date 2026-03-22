"""
Test infrastructure: async DB fixtures with per-test transaction rollback.

Each test runs inside a transaction that rolls back on completion — tests
never pollute each other, no teardown needed.

Usage:
    TEST_DATABASE_URL=postgresql+asyncpg://gatekeeper:gatekeeper@localhost:5433/gatekeeper_test pytest
"""

import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 — register all models
from app.models.base import Base

TEST_DATABASE_URL = (
    os.environ.get("TEST_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or "postgresql+asyncpg://gatekeeper:gatekeeper@localhost:5433/gatekeeper_test"
)

# Use a single event loop for the whole session so engine/connections share it.
pytest_plugins = ("anyio",)


@pytest_asyncio.fixture(scope="function")
async def db():
    """
    Per-test: creates engine, creates all tables, yields session, drops tables.
    Simpler than savepoints — avoids asyncpg event-loop scope issues.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.drop_all(c, tables=reversed(Base.metadata.sorted_tables)))
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db):
    """Test HTTP client with DB dependency overridden."""
    from app.database import get_db
    from app.main import app

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
