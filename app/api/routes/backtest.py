from datetime import datetime
from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text
from app.api.models.backtest import (
    BacktestCandleBatchRequest,
    BacktestCandlesPageResponse,
    BacktestCandleResponse,
    BacktestSessionRequest,
    BacktestSessionResponse
)
from app.api.controllers.auth import require_user

router = APIRouter()
MAX_BATCH = 5000


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


def _session_response(row) -> BacktestSessionResponse:
    return BacktestSessionResponse(
        bridge_id=row[0],
        symbol=row[1],
        master_timeframe=row[2],
        start_date=row[3],
        tick_ms=int(row[4]),
        cursor_time=int(row[5]),
        end_time=int(row[6]) if row[6] is not None else None,
        playing=bool(row[7]),
        speed=float(row[8])
    )


@router.get("/session", response_model=BacktestSessionResponse | None)
def get_session(authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        row = db.execute(
            text("""
                SELECT bridge_id, symbol, master_timeframe, start_date, tick_ms,
                       cursor_time, end_time, playing, speed
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
            "symbol": symbol,
            "master_timeframe": timeframe,
            "start_date": start_date,
            "tick_ms": req.tick_ms,
            "cursor_time": req.cursor_time,
            "end_time": req.end_time,
            "playing": 1 if req.playing else 0,
            "speed": req.speed
        }
        db.execute(
            text("""
                INSERT INTO backtest_sessions
                    (user_id, bridge_id, symbol, master_timeframe, start_date, tick_ms,
                     cursor_time, end_time, playing, speed)
                VALUES
                    (:user_id, :bridge_id, :symbol, :master_timeframe, :start_date, :tick_ms,
                     :cursor_time, :end_time, :playing, :speed)
                ON DUPLICATE KEY UPDATE
                    bridge_id = VALUES(bridge_id),
                    symbol = VALUES(symbol),
                    master_timeframe = VALUES(master_timeframe),
                    start_date = VALUES(start_date),
                    tick_ms = VALUES(tick_ms),
                    cursor_time = VALUES(cursor_time),
                    end_time = VALUES(end_time),
                    playing = VALUES(playing),
                    speed = VALUES(speed)
            """),
            params
        )
        db.commit()
        return BacktestSessionResponse(
            bridge_id=req.bridge_id,
            symbol=symbol,
            master_timeframe=timeframe,
            start_date=start_date,
            tick_ms=req.tick_ms,
            cursor_time=req.cursor_time,
            end_time=req.end_time,
            playing=req.playing,
            speed=req.speed
        )
    finally:
        db.close()


@router.delete("/session")
def delete_session(authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        row = db.execute(
            text("SELECT 1 FROM backtest_sessions WHERE user_id = :user_id"),
            {"user_id": user[0]}
        ).fetchone()
        if row:
            db.execute(
                text("DELETE FROM backtest_candles WHERE user_id = :user_id"),
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
