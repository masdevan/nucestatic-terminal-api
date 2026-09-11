from pydantic import BaseModel


class BridgeApiResponse(BaseModel):
    id: int
    name: str
    url: str
    active: bool
    mode: str


class BridgeApiRequest(BaseModel):
    name: str
    url: str
    mode: str = "static"


class BridgeApiUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    active: bool | None = None
    mode: str | None = None


class BridgeStatusResponse(BaseModel):
    id: int
    status: str