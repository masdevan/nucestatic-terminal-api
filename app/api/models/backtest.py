from pydantic import BaseModel


class BacktestSessionRequest(BaseModel):
    bridge_id: int = 0
    account_id: int = 0
    symbol: str
    master_timeframe: str
    start_date: str
    tick_ms: int
    cursor_time: int
    end_time: int | None = None
    playing: bool = False
    speed: float = 0.5
    balance: float = 0


class BacktestSessionResponse(BaseModel):
    bridge_id: int
    account_id: int
    symbol: str
    master_timeframe: str
    start_date: str
    tick_ms: int
    cursor_time: int
    end_time: int | None = None
    playing: bool
    speed: float
    balance: float


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


class BacktestOrderItem(BaseModel):
    local_id: str
    symbol: str
    side: str
    order_type: str
    lots: float
    entry_price: float
    tp_price: float | None = None
    sl_price: float | None = None
    status: str
    open_price: float | None = None
    close_price: float | None = None
    pnl: float | None = None
    close_reason: str | None = None
    opened_at: str | None = None
    closed_at: str | None = None


class BacktestTradeStateRequest(BaseModel):
    balance: float
    orders: list[BacktestOrderItem] = []


class BacktestTradeStateResponse(BaseModel):
    balance: float
    orders: list[BacktestOrderItem] = []
