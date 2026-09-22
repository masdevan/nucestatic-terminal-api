from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.backtest import BacktestSessionRequest, BacktestSessionResponse
from app.api.controllers.auth import require_user
from app.api.routes.backtest_shared import _validate_provider, _validate_symbol, _validate_timeframe

router = APIRouter()

def _session_response(row) -> BacktestSessionResponse:
    return BacktestSessionResponse(
        bridge_id=row[0],
        account_id=row[1],
        broker_id=row[2],
        broker_name=row[3],
        account_name=row[4],
        symbol=row[5],
        provider=row[6],
        master_timeframe=row[7],
        start_date=row[8],
        tick_ms=int(row[9]),
        cursor_time=int(row[10]),
        end_time=int(row[11]) if row[11] is not None else None,
        playing=bool(row[12]),
        speed=float(row[13]),
        balance=float(row[14])
    )


@router.get("/session", response_model=BacktestSessionResponse | None)
def get_session(authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        row = db.execute(
            text("""
                SELECT bridge_id, account_id, broker_id, broker_name, account_name,
                       symbol, provider, master_timeframe, start_date, tick_ms,
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
    provider = _validate_provider(req.provider)
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
            "broker_id": req.broker_id,
            "broker_name": req.broker_name,
            "account_name": req.account_name,
            "symbol": symbol,
            "provider": provider,
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
                    (user_id, bridge_id, account_id, broker_id, broker_name, account_name,
                     symbol, provider, master_timeframe, start_date, tick_ms,
                     cursor_time, end_time, playing, speed, balance)
                VALUES
                    (:user_id, :bridge_id, :account_id, :broker_id, :broker_name, :account_name,
                     :symbol, :provider, :master_timeframe, :start_date, :tick_ms,
                     :cursor_time, :end_time, :playing, :speed, :balance)
                ON DUPLICATE KEY UPDATE
                    bridge_id = VALUES(bridge_id),
                    account_id = VALUES(account_id),
                    broker_id = VALUES(broker_id),
                    broker_name = VALUES(broker_name),
                    account_name = VALUES(account_name),
                    symbol = VALUES(symbol),
                    provider = VALUES(provider),
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
            broker_id=req.broker_id,
            broker_name=req.broker_name,
            account_name=req.account_name,
            symbol=symbol,
            provider=provider,
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
        db.execute(
            text("DELETE FROM alarms WHERE user_id = :user_id AND backtest = 1"),
            {"user_id": user[0]}
        )
        db.execute(text("DELETE FROM backtest_sessions WHERE user_id = :user_id"), {"user_id": user[0]})
        db.commit()
        return {"detail": "Backtest session deleted"}
    finally:
        db.close()
