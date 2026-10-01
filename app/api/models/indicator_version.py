from pydantic import BaseModel
from app.api.models.indicator import IndicatorFile


class IndicatorVersionCreateRequest(BaseModel):
    project_key: str = ""
    session_id: int
    label: str = ""
    name: str = ""
    folders: list[str] = []
    files: list[IndicatorFile]


class IndicatorVersionMeta(BaseModel):
    id: int
    label: str
    name: str
    file_count: int
    additions: int
    deletions: int
    created_at: str


class IndicatorVersionDetail(BaseModel):
    id: int
    project_key: str
    label: str
    name: str
    folders: list[str]
    files: list[IndicatorFile]
    additions: int
    deletions: int
    created_at: str
