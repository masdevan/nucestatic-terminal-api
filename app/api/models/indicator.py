from pydantic import BaseModel


class IndicatorFile(BaseModel):
    path: str
    content: str


class IndicatorResponse(BaseModel):
    id: int
    name: str
    folders: list[str]
    files: list[IndicatorFile]
    updated_at: str


class IndicatorCreateRequest(BaseModel):
    name: str
    folders: list[str] = []
    files: list[IndicatorFile]


class IndicatorUpdateRequest(BaseModel):
    name: str | None = None
    folders: list[str] | None = None
    files: list[IndicatorFile] | None = None
