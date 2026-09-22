import random
from datetime import datetime
from fastapi import HTTPException
from app.api.models.backtest import BacktestAlarmItem, BacktestOrderItem

MAX_BATCH = 5000
MAX_ORDERS = 500
MAX_ALARMS = 500
MAX_METRICS_CHARS = 100000
SIDES = {"buy", "sell"}
ORDER_TYPES = {"market", "limit", "stop"}
ORDER_STATUSES = {"pending", "open", "closed"}
CLOSE_REASONS = {"tp", "sl", "manual", "cancel", "margin", "partial"}


def _validate_symbol(symbol: str) -> str:
    value = symbol.strip()
    if not value or len(value) > 30:
        raise HTTPException(status_code=422, detail="Symbol must be 1-30 characters")
    return value


def _validate_timeframe(timeframe: str) -> str:
    value = timeframe.strip()
    if not value or len(value) > 10:
        raise HTTPException(status_code=422, detail="Timeframe must be 1-10 characters")
    return value


def _validate_provider(provider: str) -> str:
    value = provider.strip()
    if len(value) > 100:
        raise HTTPException(status_code=422, detail="Provider must be at most 100 characters")
    return value


def _parse_time(value: str) -> str:
    normalized = value.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise HTTPException(status_code=422, detail=f"Invalid candle time: {value}")


def _fmt_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _fmt_time_opt(value) -> str | None:
    return _fmt_time(value) if value is not None else None


def _validate_order(item: BacktestOrderItem) -> BacktestOrderItem:
    local_id = item.local_id.strip()
    if not local_id or len(local_id) > 40:
        raise HTTPException(status_code=422, detail="local_id must be 1-40 characters")
    if not (10000000000 <= item.ticket <= 99999999999):
        raise HTTPException(status_code=422, detail="ticket must be an 11 digit number")
    if item.side not in SIDES:
        raise HTTPException(status_code=422, detail="Invalid order side")
    if item.order_type not in ORDER_TYPES:
        raise HTTPException(status_code=422, detail="Invalid order type")
    if item.status not in ORDER_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid order status")
    if item.close_reason is not None and item.close_reason not in CLOSE_REASONS:
        raise HTTPException(status_code=422, detail="Invalid close reason")
    if not (item.lots > 0):
        raise HTTPException(status_code=422, detail="lots must be positive")
    if not (item.entry_price > 0):
        raise HTTPException(status_code=422, detail="entry_price must be positive")
    return BacktestOrderItem(
        local_id=local_id,
        ticket=item.ticket,
        symbol=_validate_symbol(item.symbol),
        side=item.side,
        order_type=item.order_type,
        lots=item.lots,
        entry_price=item.entry_price,
        tp_price=item.tp_price,
        sl_price=item.sl_price,
        status=item.status,
        open_price=item.open_price,
        close_price=item.close_price,
        pnl=item.pnl,
        close_reason=item.close_reason,
        opened_at=_parse_time(item.opened_at) if item.opened_at else None,
        closed_at=_parse_time(item.closed_at) if item.closed_at else None
    )


def _validate_alarm(item: BacktestAlarmItem) -> BacktestAlarmItem:
    entry_type = item.entry_type.strip().lower()
    if entry_type not in SIDES:
        raise HTTPException(status_code=422, detail="Invalid alarm entry type")
    if not (item.entry_price > 0):
        raise HTTPException(status_code=422, detail="entry_price must be positive")
    return BacktestAlarmItem(
        entry_type=entry_type,
        symbol=_validate_symbol(item.symbol),
        description=(item.description or "").strip()[:500] or None,
        entry_price=item.entry_price,
        tp_price=item.tp_price,
        sl_price=item.sl_price,
        timeframe=(item.timeframe or "").strip().upper()[:10] or None,
        sim_time=_parse_time(item.sim_time) if item.sim_time else None
    )


def _reroll_tickets(orders: list[BacktestOrderItem]) -> list[BacktestOrderItem]:
    used: set[int] = set()
    result: list[BacktestOrderItem] = []
    for order in orders:
        ticket = order.ticket
        if ticket in used:
            while True:
                candidate = random.randint(10000000000, 99999999999)
                if candidate not in used:
                    break
            ticket = candidate
            order = order.model_copy(update={"ticket": ticket})
        used.add(ticket)
        result.append(order)
    return result


def _order_response(row) -> BacktestOrderItem:
    return BacktestOrderItem(
        local_id=row[0],
        ticket=int(row[15]),
        symbol=row[1],
        side=row[2],
        order_type=row[3],
        lots=float(row[4]),
        entry_price=float(row[5]),
        tp_price=float(row[6]) if row[6] is not None else None,
        sl_price=float(row[7]) if row[7] is not None else None,
        status=row[8],
        open_price=float(row[9]) if row[9] is not None else None,
        close_price=float(row[10]) if row[10] is not None else None,
        pnl=float(row[11]) if row[11] is not None else None,
        close_reason=row[12],
        opened_at=_fmt_time_opt(row[13]),
        closed_at=_fmt_time_opt(row[14])
    )
