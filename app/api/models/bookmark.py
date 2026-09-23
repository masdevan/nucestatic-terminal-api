from pydantic import BaseModel


class BookmarkResponse(BaseModel):
    id: int
    symbol: str
    server: str
    bridge_id: int = 0


class BookmarkCreateRequest(BaseModel):
    symbol: str
    server: str
    bridge_id: int | None = None