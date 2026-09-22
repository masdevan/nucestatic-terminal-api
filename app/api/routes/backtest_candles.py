from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text
from app.api.models.backtest import (
    BacktestCandleBatchRequest,
    BacktestCandleResponse,
    BacktestCandlesPageResponse
)
from app.api.controllers.auth import require_user
from app.api.routes.backtest_shared import (
    MAX_BATCH,
    _fmt_time,
    _parse_time,
    _validate_symbol,
    _validate_timeframe
)

router = APIRouter()

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
