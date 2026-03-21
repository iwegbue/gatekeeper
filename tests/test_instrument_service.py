"""Tests for instrument_service."""
import pytest

from app.services import instrument_service
from tests.factories import create_instrument


@pytest.mark.asyncio
async def test_create_instrument(db):
    inst = await instrument_service.create(db, symbol="EURUSD", display_name="EUR/USD")
    assert inst.id is not None
    assert inst.symbol == "EURUSD"
    assert inst.display_name == "EUR/USD"
    assert inst.is_enabled is True


@pytest.mark.asyncio
async def test_get_all(db):
    await create_instrument(db, symbol="EURUSD", display_name="EUR/USD")
    await create_instrument(db, symbol="GBPUSD", display_name="GBP/USD")
    instruments = await instrument_service.get_all(db)
    symbols = {i.symbol for i in instruments}
    assert "EURUSD" in symbols
    assert "GBPUSD" in symbols


@pytest.mark.asyncio
async def test_get_enabled_only(db):
    await create_instrument(db, symbol="EURUSD", display_name="EUR/USD", is_enabled=True)
    await create_instrument(db, symbol="GBPUSD", display_name="GBP/USD", is_enabled=False)
    enabled = await instrument_service.get_enabled(db)
    symbols = {i.symbol for i in enabled}
    assert "EURUSD" in symbols
    assert "GBPUSD" not in symbols


@pytest.mark.asyncio
async def test_get_by_symbol(db):
    await create_instrument(db, symbol="XAUUSD", display_name="Gold")
    found = await instrument_service.get_by_symbol(db, "XAUUSD")
    assert found is not None
    assert found.display_name == "Gold"


@pytest.mark.asyncio
async def test_get_by_symbol_not_found(db):
    result = await instrument_service.get_by_symbol(db, "NONEXISTENT")
    assert result is None


@pytest.mark.asyncio
async def test_update_instrument(db):
    inst = await create_instrument(db, symbol="USDJPY", display_name="USD/JPY")
    updated = await instrument_service.update_instrument(db, inst.id, display_name="Dollar Yen", priority=5)
    assert updated.display_name == "Dollar Yen"
    assert updated.priority == 5


@pytest.mark.asyncio
async def test_delete_instrument(db):
    inst = await create_instrument(db, symbol="AUDUSD", display_name="AUD/USD")
    result = await instrument_service.delete_instrument(db, inst.id)
    assert result is True
    deleted = await instrument_service.get_by_id(db, inst.id)
    assert deleted is None


@pytest.mark.asyncio
async def test_delete_nonexistent(db):
    import uuid
    result = await instrument_service.delete_instrument(db, uuid.uuid4())
    assert result is False
