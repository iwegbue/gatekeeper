from pydantic import BaseModel


class AIReviewResponse(BaseModel):
    content: str


class RuleClarityRequest(BaseModel):
    rule_name: str
    rule_description: str | None = None
    layer: str
