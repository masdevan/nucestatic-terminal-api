from pydantic import BaseModel


class BacktestSessionRequest(BaseModel):
    bridge_id: int = 0
    account_id: int = 0
    broker_id: int = 0
    broker_name: str = ""
    account_name: str = ""
    symbol: str
    provider: str = ""
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
    broker_id: int = 0
    broker_name: str = ""
    account_name: str = ""
    symbol: str
    provider: str = ""
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
    ticket: int = 0
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


class BacktestAlarmItem(BaseModel):
    entry_type: str
    symbol: str
    description: str | None = None
    entry_price: float
    tp_price: float | None = None
    sl_price: float | None = None
    timeframe: str | None = None
    sim_time: str | None = None


class BacktestHistoryRequest(BaseModel):
    symbol: str
    master_timeframe: str
    account_id: int = 0
    broker_id: int = 0
    broker_name: str = ""
    account_name: str = ""
    bridge_id: int = 0
    start_date: str
    initial_balance: float
    final_balance: float
    orders: list[BacktestOrderItem] = []
    alarms: list[BacktestAlarmItem] = []
    metrics: dict | None = None


class BacktestHistoryResponse(BaseModel):
    id: int
    session_number: int = 0
    symbol: str
    master_timeframe: str
    account_id: int
    broker_id: int = 0
    broker_name: str = ""
    account_name: str = ""
    bridge_id: int
    start_date: str
    initial_balance: float
    final_balance: float
    first_trade_at: str | None = None
    last_trade_at: str | None = None
    created_at: str
    alarm_count: int = 0


class BacktestHistoryDetailResponse(BacktestHistoryResponse):
    orders: list[BacktestOrderItem] = []
    alarms: list[BacktestAlarmItem] = []
    metrics: dict | None = None
