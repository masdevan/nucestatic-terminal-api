from pydantic import BaseModel


class AiSessionCreateRequest(BaseModel):
    project: str = ""
    title: str = "New session"


class AiSessionSaveRequest(BaseModel):
    title: str | None = None
    messages: list | None = None
    reverted: list | None = None
    usage: dict | None = None


class AiSessionMeta(BaseModel):
    id: int
    title: str
    message_count: int
    updated_at: str


class AiSessionDetail(BaseModel):
    id: int
    title: str
    messages: list
    reverted: list = []
    usage: dict | None = None
    updated_at: str
