import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.base import SuccessResponse
from app.schemas.journal import JournalEntryResponse, JournalEntryUpdate
from app.services import journal_service

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("", response_model=list[JournalEntryResponse])
async def list_entries(db: AsyncSession = Depends(get_db)):
    entries = await journal_service.list_entries(db)
    return [JournalEntryResponse.model_validate(e) for e in entries]


@router.get("/{entry_id}", response_model=JournalEntryResponse)
async def get_entry(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    entry = await journal_service.get_entry(db, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return JournalEntryResponse.model_validate(entry)


@router.patch("/{entry_id}", response_model=JournalEntryResponse)
async def update_entry(
    entry_id: uuid.UUID,
    body: JournalEntryUpdate,
    db: AsyncSession = Depends(get_db),
):
    update_data = body.model_dump(exclude_unset=True)
    tags = update_data.pop("tags", None)

    entry = await journal_service.update_entry(db, entry_id, **update_data)
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    if tags is not None:
        await journal_service.set_entry_tags(db, entry_id, tags)
        # Re-fetch to get updated tags
        entry = await journal_service.get_entry(db, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")

    return JournalEntryResponse.model_validate(entry)


@router.post("/{entry_id}/complete", response_model=JournalEntryResponse)
async def complete_entry(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    entry = await journal_service.complete_entry(db, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return JournalEntryResponse.model_validate(entry)


@router.delete("/{entry_id}", response_model=SuccessResponse)
async def delete_entry(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    deleted = await journal_service.delete_entry(db, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return SuccessResponse(message="Journal entry deleted")
