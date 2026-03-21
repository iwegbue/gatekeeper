import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID
    rule_name: str
    rule_layer: str
    rule_type: str
    rule_weight: int
    checked: bool
    checked_at: datetime | None = None
    notes: str | None = None


class CheckToggleRequest(BaseModel):
    checked: bool
    notes: str | None = None
