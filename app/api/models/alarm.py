from datetime import datetime
from pydantic import BaseModel


class AlarmResponse(BaseModel):
    id: int
    symbol: str
    description: str | None = None
    entry_type: str
    entry_price: float
    tp_price: float | None = None
    sl_price: float | None = None
    timeframe: str | None = None
    is_read: bool = False
    created_at: datetime | None = None
    webhook_url: str | None = None


class AlarmCreateRequest(BaseModel):
    symbol: str
    description: str | None = None
    entry_type: str
    entry_price: float
    tp_price: float | None = None
    sl_price: float | None = None
    timeframe: str | None = None
    webhook: str | None = None
