import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlanRuleCreate(BaseModel):
    layer: str
    name: str
    description: str | None = None
    rule_type: str = "REQUIRED"
    weight: int = 1
    parameters: dict | None = None


class PlanRuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    rule_type: str | None = None
    weight: int | None = None
    is_active: bool | None = None
    parameters: dict | None = None


class PlanRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    layer: str
    name: str
    description: str | None = None
    rule_type: str
    weight: int
    order: int
    is_active: bool
    parameters: dict | None = None
    created_at: datetime
    updated_at: datetime


class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    rules_by_layer: dict[str, list[PlanRuleResponse]] = {}
