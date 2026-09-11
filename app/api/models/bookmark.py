from pydantic import BaseModel


class BookmarkResponse(BaseModel):
    id: int
    symbol: str
    server: str


class BookmarkCreateRequest(BaseModel):
    symbol: str
    server: str