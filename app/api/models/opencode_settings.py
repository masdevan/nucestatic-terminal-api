from pydantic import BaseModel


class OpenCodeSettingsRequest(BaseModel):
    api_key: str
    model: str = "kimi-k3"
    base_url: str = "https://opencode.ai/zen/go"


class OpenCodeSettingsUpdate(BaseModel):
    model: str | None = None
    base_url: str | None = None


class OpenCodeSettingsItem(BaseModel):
    id: int
    api_key_masked: str
    api_key: str | None = None
    model: str
    base_url: str
    active: bool
    has_key: bool
