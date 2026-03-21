import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TradeOpenRequest(BaseModel):
    idea_id: uuid.UUID
    entry_price: float
    sl_price: float
    tp_price: float | None = None
    lot_size: float | None = None
    risk_pct: float | None = None


class TradeCloseRequest(BaseModel):
    exit_price: float


class TradeUpdateSLRequest(BaseModel):
    sl_price: float


class TradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idea_id: uuid.UUID
    instrument: str
    direction: str
    entry_time: datetime
    entry_price: float
    sl_price: float
    initial_sl_price: float | None = None
    tp_price: float | None = None
    risk_pct: float
    lot_size: float | None = None
    grade: str
    state: str
    be_locked: bool
    partials_taken: bool
    exit_time: datetime | None = None
    exit_price: float | None = None
    r_multiple: float | None = None
    created_at: datetime
    updated_at: datetime
