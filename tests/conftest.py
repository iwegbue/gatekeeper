"""
Test infrastructure: async DB fixtures with per-test transaction rollback.

Each test runs inside a transaction that rolls back on completion — tests
never pollute each other, no teardown needed.

Usage:
    TEST_DATABASE_URL=postgresql+asyncpg://gatekeeper:gatekeeper@localhost:5432/gatekeeper_test pytest
"""
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
import app.models  # noqa: F401 — register all models

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://gatekeeper:gatekeeper@localhost:5432/gatekeeper_test",
)


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create all tables once per test session, drop on teardown."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine):
    """
    Per-test AsyncSession wrapped in a savepoint that rolls back after the test.
    This means each test starts with a clean slate without recreating tables.
    """
    async with db_engine.connect() as conn:
        await conn.begin()
        session_factory = async_sessionmaker(
            bind=conn, class_=AsyncSession, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        async with session_factory() as session:
            yield session
        await conn.rollback()


@pytest_asyncio.fixture
async def client(db):
    """Test HTTP client with DB dependency overridden."""
    from app.main import app
    from app.database import get_db

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
