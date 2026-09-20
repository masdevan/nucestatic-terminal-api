from pydantic import BaseModel


class BacktestSessionRequest(BaseModel):
    bridge_id: int = 0
    symbol: str
    master_timeframe: str
    start_date: str
    tick_ms: int
    cursor_time: int
    end_time: int | None = None
    playing: bool = False
    speed: float = 0.5


class BacktestSessionResponse(BaseModel):
    bridge_id: int
    symbol: str
    master_timeframe: str
    start_date: str
    tick_ms: int
    cursor_time: int
    end_time: int | None = None
    playing: bool
    speed: float


class BacktestCandleItem(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float


class BacktestCandleBatchRequest(BaseModel):
    bridge_id: int = 0
    symbol: str
    timeframe: str
    candles: list[BacktestCandleItem]


class BacktestCandleResponse(BaseModel):
    symbol: str
    time: str
    open: float
    high: float
    low: float
    close: float


class BacktestCandlesPageResponse(BaseModel):
    data: list[BacktestCandleResponse]
    has_next: bool
