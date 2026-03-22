import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IdeaCreate(BaseModel):
    instrument: str
    direction: str
    risk_pct: float | None = None
    notes: str | None = None
    plan_id: uuid.UUID | None = None


class IdeaUpdate(BaseModel):
    notes: str | None = None
    risk_pct: float | None = None


class IdeaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instrument: str
    direction: str
    state: str
    plan_id: uuid.UUID | None = None
    checklist_score: int | None = None
    grade: str | None = None
    risk_pct: float | None = None
    entry_window_expires_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class IdeaDetailResponse(IdeaResponse):
    checklist: list["ChecklistItemResponse"] = []
    layer_completion: dict[str, bool] = {}
    available_actions: dict[str, bool] = {}


class StateChangeRequest(BaseModel):
    reason: str | None = None


# Avoid circular import at definition time
from app.schemas.checklist import ChecklistItemResponse  # noqa: E402

IdeaDetailResponse.model_rebuild()
