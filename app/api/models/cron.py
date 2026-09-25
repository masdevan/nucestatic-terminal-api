from datetime import datetime
from pydantic import BaseModel


class CronJobResponse(BaseModel):
    id: int
    indicator_id: int
    indicator_name: str
    bridge_id: int
    bridge_name: str
    symbol: str
    timeframe: str
    interval_seconds: int
    webhook_url: str | None = None
    values: dict | None = None
    enabled: bool = True
    last_run_at: datetime | None = None
    last_alert_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime | None = None


class CronJobCreateRequest(BaseModel):
    indicator_id: int
    bridge_id: int
    symbol: str
    timeframe: str
    interval_seconds: int
    webhook: str | None = None
    values: dict | None = None
    enabled: bool = True


class CronJobUpdateRequest(BaseModel):
    interval_seconds: int | None = None
    webhook: str | None = None
    values: dict | None = None
    enabled: bool | None = None
