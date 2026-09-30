from typing import Any
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
    builtin: str | None = None


class IndicatorCreateRequest(BaseModel):
    name: str
    folders: list[str] = []
    files: list[IndicatorFile]


class IndicatorBuiltinItem(BaseModel):
    key: str
    name: str
    files: list[IndicatorFile]


class IndicatorBuiltinSyncRequest(BaseModel):
    builtins: list[IndicatorBuiltinItem]


class IndicatorUpdateRequest(BaseModel):
    name: str | None = None
    folders: list[str] | None = None
    files: list[IndicatorFile] | None = None


class IndicatorSettingsResponse(BaseModel):
    indicator_key: str
    values: dict[str, Any]


class IndicatorSettingsRequest(BaseModel):
    values: dict[str, Any]
