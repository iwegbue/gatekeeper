import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.base import SuccessResponse
from app.schemas.instruments import InstrumentCreate, InstrumentResponse, InstrumentUpdate
from app.services import instrument_service

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("", response_model=list[InstrumentResponse])
async def list_instruments(
    enabled_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    if enabled_only:
        instruments = await instrument_service.get_enabled(db)
    else:
        instruments = await instrument_service.get_all(db)
    return [InstrumentResponse.model_validate(i) for i in instruments]


@router.post("", response_model=InstrumentResponse, status_code=201)
async def create_instrument(body: InstrumentCreate, db: AsyncSession = Depends(get_db)):
    instrument = await instrument_service.create(
        db,
        symbol=body.symbol,
        display_name=body.display_name,
        asset_class=body.asset_class,
        is_enabled=body.is_enabled,
        priority=body.priority,
        notes=body.notes,
    )
    return InstrumentResponse.model_validate(instrument)


@router.get("/{instrument_id}", response_model=InstrumentResponse)
async def get_instrument(instrument_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    instrument = await instrument_service.get_by_id(db, instrument_id)
    if instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return InstrumentResponse.model_validate(instrument)


@router.patch("/{instrument_id}", response_model=InstrumentResponse)
async def update_instrument(
    instrument_id: uuid.UUID,
    body: InstrumentUpdate,
    db: AsyncSession = Depends(get_db),
):
    update_data = body.model_dump(exclude_unset=True)
    instrument = await instrument_service.update_instrument(db, instrument_id, **update_data)
    if instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return InstrumentResponse.model_validate(instrument)


@router.delete("/{instrument_id}", response_model=SuccessResponse)
async def delete_instrument(instrument_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    deleted = await instrument_service.delete_instrument(db, instrument_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return SuccessResponse(message="Instrument deleted")
