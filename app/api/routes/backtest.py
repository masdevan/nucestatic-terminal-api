import json
from datetime import datetime
from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text
from app.api.models.backtest import (
    BacktestCandleBatchRequest,
    BacktestCandlesPageResponse,
    BacktestCandleResponse,
    BacktestHistoryDetailResponse,
    BacktestHistoryRequest,
    BacktestHistoryResponse,
    BacktestOrderItem,
    BacktestSessionRequest,
    BacktestSessionResponse,
    BacktestTradeStateRequest,
    BacktestTradeStateResponse
)
from app.api.controllers.auth import require_user

router = APIRouter()
MAX_BATCH = 5000
MAX_ORDERS = 500
SIDES = {"buy", "sell"}
ORDER_TYPES = {"market", "limit", "stop"}
ORDER_STATUSES = {"pending", "open", "closed"}
CLOSE_REASONS = {"tp", "sl", "manual", "cancel"}


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


def _order_response(row) -> BacktestOrderItem:
    return BacktestOrderItem(
        local_id=row[0],
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


def _session_response(row) -> BacktestSessionResponse:
    return BacktestSessionResponse(
        bridge_id=row[0],
        account_id=row[1],
        symbol=row[2],
        master_timeframe=row[3],
        start_date=row[4],
        tick_ms=int(row[5]),
        cursor_time=int(row[6]),
        end_time=int(row[7]) if row[7] is not None else None,
        playing=bool(row[8]),
        speed=float(row[9]),
        balance=float(row[10])
    )


@router.get("/session", response_model=BacktestSessionResponse | None)
def get_session(authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        row = db.execute(
            text("""
                SELECT bridge_id, account_id, symbol, master_timeframe, start_date, tick_ms,
                       cursor_time, end_time, playing, speed, balance
                FROM backtest_sessions WHERE user_id = :user_id
            """),
            {"user_id": user[0]}
        ).fetchone()
        return _session_response(row) if row else None
    finally:
        db.close()


@router.put("/session", response_model=BacktestSessionResponse)
def save_session(req: BacktestSessionRequest, authorization: str = Header(None)):
    symbol = _validate_symbol(req.symbol)
    timeframe = _validate_timeframe(req.master_timeframe)
    start_date = req.start_date.strip()
    if len(start_date) != 10:
        raise HTTPException(status_code=422, detail="start_date must use YYYY-MM-DD")
    if req.tick_ms <= 0:
        raise HTTPException(status_code=422, detail="tick_ms must be positive")
    if req.speed <= 0:
        raise HTTPException(status_code=422, detail="speed must be positive")

    db, user = require_user(authorization)
    try:
        params = {
            "user_id": user[0],
            "bridge_id": req.bridge_id,
            "account_id": req.account_id,
            "symbol": symbol,
            "master_timeframe": timeframe,
            "start_date": start_date,
            "tick_ms": req.tick_ms,
            "cursor_time": req.cursor_time,
            "end_time": req.end_time,
            "playing": 1 if req.playing else 0,
            "speed": req.speed,
            "balance": req.balance
        }
        db.execute(
            text("""
                INSERT INTO backtest_sessions
                    (user_id, bridge_id, account_id, symbol, master_timeframe, start_date, tick_ms,
                     cursor_time, end_time, playing, speed, balance)
                VALUES
                    (:user_id, :bridge_id, :account_id, :symbol, :master_timeframe, :start_date, :tick_ms,
                     :cursor_time, :end_time, :playing, :speed, :balance)
                ON DUPLICATE KEY UPDATE
                    bridge_id = VALUES(bridge_id),
                    account_id = VALUES(account_id),
                    symbol = VALUES(symbol),
                    master_timeframe = VALUES(master_timeframe),
                    start_date = VALUES(start_date),
                    tick_ms = VALUES(tick_ms),
                    cursor_time = VALUES(cursor_time),
                    end_time = VALUES(end_time),
                    playing = VALUES(playing),
                    speed = VALUES(speed),
                    balance = VALUES(balance)
            """),
            params
        )
        db.commit()
        return BacktestSessionResponse(
            bridge_id=req.bridge_id,
            account_id=req.account_id,
            symbol=symbol,
            master_timeframe=timeframe,
            start_date=start_date,
            tick_ms=req.tick_ms,
            cursor_time=req.cursor_time,
            end_time=req.end_time,
            playing=req.playing,
            speed=req.speed,
            balance=req.balance
        )
    finally:
        db.close()


@router.delete("/session")
def delete_session(authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        db.execute(
            text("DELETE FROM backtest_candles WHERE user_id = :user_id"),
            {"user_id": user[0]}
        )
        db.execute(
            text("DELETE FROM backtest_orders WHERE user_id = :user_id"),
            {"user_id": user[0]}
        )
        db.execute(text("DELETE FROM backtest_sessions WHERE user_id = :user_id"), {"user_id": user[0]})
        db.commit()
        return {"detail": "Backtest session deleted"}
    finally:
        db.close()


@router.get("/candles", response_model=BacktestCandlesPageResponse)
def list_candles(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    bridge_id: int = Query(0),
    after: str | None = Query(None),
    limit: int = Query(5000, ge=1, le=5000),
    authorization: str = Header(None)
):
    params = {
        "user_id": 0,
        "bridge_id": bridge_id,
        "symbol": _validate_symbol(symbol),
        "timeframe": _validate_timeframe(timeframe),
        "limit": limit
    }
    db, user = require_user(authorization)
    params["user_id"] = user[0]
    try:
        query = """
            SELECT symbol, time, open, high, low, close
            FROM backtest_candles
            WHERE user_id = :user_id AND bridge_id = :bridge_id
              AND symbol = :symbol AND timeframe = :timeframe
        """
        if after:
            query += " AND time > :after"
            params["after"] = _parse_time(after)
        query += " ORDER BY time ASC LIMIT :limit"

        rows = db.execute(text(query), params).fetchall()
        data = [
            BacktestCandleResponse(
                symbol=r[0],
                time=_fmt_time(r[1]),
                open=float(r[2]),
                high=float(r[3]),
                low=float(r[4]),
                close=float(r[5])
            )
            for r in rows
        ]
        return BacktestCandlesPageResponse(data=data, has_next=len(data) == limit)
    finally:
        db.close()


@router.post("/candles")
def save_candles(req: BacktestCandleBatchRequest, authorization: str = Header(None)):
    symbol = _validate_symbol(req.symbol)
    timeframe = _validate_timeframe(req.timeframe)
    if not req.candles:
        raise HTTPException(status_code=422, detail="Candles must not be empty")
    if len(req.candles) > MAX_BATCH:
        raise HTTPException(status_code=422, detail=f"Batch limited to {MAX_BATCH} candles")

    db, user = require_user(authorization)
    try:
        rows = []
        for candle in req.candles:
            rows.append({
                "user_id": user[0],
                "bridge_id": req.bridge_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "time": _parse_time(candle.time),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close
            })
        db.execute(
            text("""
                INSERT INTO backtest_candles
                    (user_id, bridge_id, symbol, timeframe, time, open, high, low, close)
                VALUES
                    (:user_id, :bridge_id, :symbol, :timeframe, :time, :open, :high, :low, :close)
                ON DUPLICATE KEY UPDATE
                    open = VALUES(open),
                    high = VALUES(high),
                    low = VALUES(low),
                    close = VALUES(close)
            """),
            rows
        )
        db.commit()
        return {"detail": "Candles saved", "count": len(rows)}
    finally:
        db.close()


@router.get("/trade-state", response_model=BacktestTradeStateResponse)
def get_trade_state(authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        session_row = db.execute(
            text("SELECT balance FROM backtest_sessions WHERE user_id = :user_id"),
            {"user_id": user[0]}
        ).fetchone()
        rows = db.execute(
            text("""
                SELECT local_id, symbol, side, order_type, lots, entry_price, tp_price, sl_price,
                       status, open_price, close_price, pnl, close_reason, opened_at, closed_at
                FROM backtest_orders WHERE user_id = :user_id ORDER BY id
            """),
            {"user_id": user[0]}
        ).fetchall()
        return BacktestTradeStateResponse(
            balance=float(session_row[0]) if session_row else 0,
            orders=[_order_response(row) for row in rows]
        )
    finally:
        db.close()


@router.put("/trade-state", response_model=BacktestTradeStateResponse)
def save_trade_state(req: BacktestTradeStateRequest, authorization: str = Header(None)):
    if len(req.orders) > MAX_ORDERS:
        raise HTTPException(status_code=422, detail=f"Orders limited to {MAX_ORDERS}")
    orders = [_validate_order(item) for item in req.orders]

    db, user = require_user(authorization)
    try:
        db.execute(
            text("DELETE FROM backtest_orders WHERE user_id = :user_id"),
            {"user_id": user[0]}
        )
        if orders:
            db.execute(
                text("""
                    INSERT INTO backtest_orders
                        (user_id, local_id, symbol, side, order_type, lots, entry_price,
                         tp_price, sl_price, status, open_price, close_price, pnl, close_reason,
                         opened_at, closed_at)
                    VALUES
                        (:user_id, :local_id, :symbol, :side, :order_type, :lots, :entry_price,
                         :tp_price, :sl_price, :status, :open_price, :close_price, :pnl, :close_reason,
                         :opened_at, :closed_at)
                """),
                [{**order.model_dump(), "user_id": user[0]} for order in orders]
            )
        db.execute(
            text("UPDATE backtest_sessions SET balance = :balance WHERE user_id = :user_id"),
            {"balance": req.balance, "user_id": user[0]}
        )
        db.commit()
        return BacktestTradeStateResponse(balance=req.balance, orders=orders)
    finally:
        db.close()


def _history_response(row, session_number: int = 0) -> BacktestHistoryResponse:
    return BacktestHistoryResponse(
        id=int(row[0]),
        session_number=session_number,
        symbol=row[1],
        master_timeframe=row[2],
        account_id=int(row[3]),
        bridge_id=int(row[4]),
        start_date=row[5],
        initial_balance=float(row[6]),
        final_balance=float(row[7]),
        first_trade_at=_fmt_time_opt(row[8]),
        last_trade_at=_fmt_time_opt(row[9]),
        created_at=_fmt_time(row[10])
    )


@router.post("/history", response_model=BacktestHistoryResponse)
def save_history(req: BacktestHistoryRequest, authorization: str = Header(None)):
    symbol = _validate_symbol(req.symbol)
    timeframe = _validate_timeframe(req.master_timeframe)
    start_date = req.start_date.strip()
    if len(start_date) != 10:
        raise HTTPException(status_code=422, detail="start_date must use YYYY-MM-DD")
    if len(req.orders) > MAX_ORDERS:
        raise HTTPException(status_code=422, detail=f"Orders limited to {MAX_ORDERS}")
    orders = [_validate_order(item) for item in req.orders]
    trade_times = sorted(order.opened_at for order in orders if order.opened_at)

    db, user = require_user(authorization)
    try:
        session_number = db.execute(
            text("SELECT COALESCE(MAX(session_number), 0) + 1 FROM backtest_history WHERE user_id = :user_id"),
            {"user_id": user[0]}
        ).scalar()
        result = db.execute(
            text("""
                INSERT INTO backtest_history
                    (user_id, symbol, master_timeframe, account_id, bridge_id, start_date,
                     session_number, initial_balance, final_balance, orders, first_trade_at, last_trade_at)
                VALUES
                    (:user_id, :symbol, :master_timeframe, :account_id, :bridge_id, :start_date,
                     :session_number, :initial_balance, :final_balance, :orders, :first_trade_at, :last_trade_at)
            """),
            {
                "user_id": user[0],
                "symbol": symbol,
                "master_timeframe": timeframe,
                "account_id": req.account_id,
                "bridge_id": req.bridge_id,
                "start_date": start_date,
                "session_number": int(session_number),
                "initial_balance": req.initial_balance,
                "final_balance": req.final_balance,
                "orders": json.dumps([order.model_dump() for order in orders]),
                "first_trade_at": trade_times[0] if trade_times else None,
                "last_trade_at": trade_times[-1] if trade_times else None
            }
        )
        db.commit()
        saved = db.execute(
            text("""
                SELECT id, symbol, master_timeframe, account_id, bridge_id, start_date,
                       initial_balance, final_balance, first_trade_at, last_trade_at, created_at,
                       session_number
                FROM backtest_history WHERE id = :history_id
            """),
            {"history_id": result.lastrowid}
        ).fetchone()
        return _history_response(saved, int(saved[11]))
    finally:
        db.close()


@router.get("/history", response_model=list[BacktestHistoryResponse])
def list_history(authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        rows = db.execute(
            text("""
                SELECT id, symbol, master_timeframe, account_id, bridge_id, start_date,
                       initial_balance, final_balance, first_trade_at, last_trade_at, created_at,
                       session_number
                FROM backtest_history WHERE user_id = :user_id ORDER BY id DESC LIMIT 100
            """),
            {"user_id": user[0]}
        ).fetchall()
        return [_history_response(row, int(row[11])) for row in rows]
    finally:
        db.close()


@router.get("/history/{history_id}", response_model=BacktestHistoryDetailResponse)
def get_history(history_id: int, authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        row = db.execute(
            text("""
                SELECT id, symbol, master_timeframe, account_id, bridge_id, start_date,
                       initial_balance, final_balance, first_trade_at, last_trade_at, created_at,
                       session_number,
                       orders
                FROM backtest_history WHERE id = :history_id AND user_id = :user_id
            """),
            {"history_id": history_id, "user_id": user[0]}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="History not found")
        header = _history_response(row, int(row[11]))
        stored = json.loads(row[12])
        return BacktestHistoryDetailResponse(
            **header.model_dump(),
            orders=[BacktestOrderItem(**item) for item in stored]
        )
    finally:
        db.close()


@router.delete("/history/{history_id}")
def delete_history(history_id: int, authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        result = db.execute(
            text("DELETE FROM backtest_history WHERE id = :history_id AND user_id = :user_id"),
            {"history_id": history_id, "user_id": user[0]}
        )
        db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="History not found")
        return {"detail": "History deleted"}
    finally:
        db.close()
