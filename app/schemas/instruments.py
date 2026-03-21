import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InstrumentCreate(BaseModel):
    symbol: str
    display_name: str
    asset_class: str = "FX"
    is_enabled: bool = True
    priority: int = 0
    notes: str | None = None


class InstrumentUpdate(BaseModel):
    display_name: str | None = None
    asset_class: str | None = None
    is_enabled: bool | None = None
    priority: int | None = None
    notes: str | None = None


class InstrumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    display_name: str
    asset_class: str
    is_enabled: bool
    priority: int
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
