from pydantic import BaseModel


class BrokerPairRequest(BaseModel):
    pair: str
    spread_type: str
    spread_value: float
    lot: float = 0.01


class BrokerPairResponse(BaseModel):
    pair: str
    spread_type: str
    spread_value: float
    lot: float


class BrokerAccountRequest(BaseModel):
    name: str
    balance: float = 0
    leverage: int = 100


class BrokerAccountUpdate(BaseModel):
    name: str | None = None
    balance: float | None = None
    leverage: int | None = None


class BrokerAccountResponse(BaseModel):
    id: int
    name: str
    balance: float
    leverage: int


class BrokerOrderResponse(BaseModel):
    id: int
    symbol: str
    side: str
    lots: float
    entry_price: float
    tp_price: float | None = None
    sl_price: float | None = None
    status: str
    close_price: float | None = None
    pnl: float | None = None
    opened_at: str
    closed_at: str | None = None


class BrokerCreateRequest(BaseModel):
    name: str
    pairs: list[BrokerPairRequest] = []


class BrokerUpdateRequest(BaseModel):
    name: str | None = None
    pairs: list[BrokerPairRequest] | None = None


class BrokerResponse(BaseModel):
    id: int
    name: str
    pairs: list[BrokerPairResponse]
    accounts: list[BrokerAccountResponse] = []
    updated_at: str
