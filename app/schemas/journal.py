import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JournalEntryUpdate(BaseModel):
    what_went_well: str | None = None
    what_went_wrong: str | None = None
    lessons_learned: str | None = None
    emotions: str | None = None
    would_take_again: bool | None = None
    rating: int | None = None
    tags: list[str] | None = None


class JournalTagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trade_id: uuid.UUID
    idea_id: uuid.UUID
    status: str
    trade_summary: dict | None = None
    plan_adherence_pct: int | None = None
    rule_violations: dict | None = None
    what_went_well: str | None = None
    what_went_wrong: str | None = None
    lessons_learned: str | None = None
    emotions: str | None = None
    would_take_again: bool | None = None
    rating: int | None = None
    tags: list[JournalTagResponse] = []
    created_at: datetime
    updated_at: datetime
