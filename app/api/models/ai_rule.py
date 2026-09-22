from pydantic import BaseModel


class AiRuleCreateRequest(BaseModel):
    text: str


class AiRuleItem(BaseModel):
    id: int
    text: str
