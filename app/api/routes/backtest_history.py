import json
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.backtest import (
    BacktestAlarmItem,
    BacktestHistoryDetailResponse,
    BacktestHistoryRequest,
    BacktestHistoryResponse,
    BacktestOrderItem
)
from app.api.controllers.auth import require_user
from app.api.routes.backtest_shared import (
    MAX_ALARMS,
    MAX_METRICS_CHARS,
    MAX_ORDERS,
    _fmt_time,
    _fmt_time_opt,
    _validate_alarm,
    _validate_order,
    _validate_symbol,
    _validate_timeframe
)

router = APIRouter()

def _history_response(row, session_number: int = 0, alarm_count: int = 0) -> BacktestHistoryResponse:
    return BacktestHistoryResponse(
        id=int(row[0]),
        session_number=session_number,
        symbol=row[1],
        master_timeframe=row[2],
        account_id=int(row[3]),
        broker_id=int(row[4]),
        broker_name=row[5],
        account_name=row[6],
        bridge_id=int(row[7]),
        start_date=row[8],
        initial_balance=float(row[9]),
        final_balance=float(row[10]),
        first_trade_at=_fmt_time_opt(row[11]),
        last_trade_at=_fmt_time_opt(row[12]),
        created_at=_fmt_time(row[13]),
        alarm_count=alarm_count
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
    if len(req.alarms) > MAX_ALARMS:
        raise HTTPException(status_code=422, detail=f"Alarms limited to {MAX_ALARMS}")
    orders = [_validate_order(item) for item in req.orders]
    alarms = [_validate_alarm(item) for item in req.alarms]
    metrics = req.metrics if isinstance(req.metrics, dict) else None
    metrics_json = json.dumps(metrics) if metrics else None
    if metrics_json is not None and len(metrics_json) > MAX_METRICS_CHARS:
        raise HTTPException(status_code=422, detail="Metrics payload too large")
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
                    (user_id, symbol, master_timeframe, account_id, broker_id, broker_name,
                     account_name, bridge_id, start_date, session_number,
                     initial_balance, final_balance, orders, alarms, alarm_count, metrics, first_trade_at, last_trade_at)
                VALUES
                    (:user_id, :symbol, :master_timeframe, :account_id, :broker_id, :broker_name,
                     :account_name, :bridge_id, :start_date, :session_number,
                     :initial_balance, :final_balance, :orders, :alarms, :alarm_count, :metrics, :first_trade_at, :last_trade_at)
            """),
            {
                "user_id": user[0],
                "symbol": symbol,
                "master_timeframe": timeframe,
                "account_id": req.account_id,
                "broker_id": req.broker_id,
                "broker_name": req.broker_name,
                "account_name": req.account_name,
                "bridge_id": req.bridge_id,
                "start_date": start_date,
                "session_number": int(session_number),
                "initial_balance": req.initial_balance,
                "final_balance": req.final_balance,
                "orders": json.dumps([order.model_dump() for order in orders]),
                "alarms": json.dumps([alarm.model_dump() for alarm in alarms]),
                "alarm_count": len(alarms),
                "metrics": metrics_json,
                "first_trade_at": trade_times[0] if trade_times else None,
                "last_trade_at": trade_times[-1] if trade_times else None
            }
        )
        db.commit()
        saved = db.execute(
            text("""
                SELECT id, symbol, master_timeframe, account_id, broker_id, broker_name,
                       account_name, bridge_id, start_date, initial_balance, final_balance,
                       first_trade_at, last_trade_at, created_at, session_number, alarm_count,
                       metrics
                FROM backtest_history WHERE id = :history_id
            """),
            {"history_id": result.lastrowid}
        ).fetchone()
        return _history_response(saved, int(saved[14]), int(saved[15]))
    finally:
        db.close()


@router.get("/history", response_model=list[BacktestHistoryResponse])
def list_history(authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        rows = db.execute(
            text("""
                SELECT id, symbol, master_timeframe, account_id, broker_id, broker_name,
                       account_name, bridge_id, start_date, initial_balance, final_balance,
                       first_trade_at, last_trade_at, created_at, session_number, alarm_count
                FROM backtest_history WHERE user_id = :user_id ORDER BY id DESC LIMIT 100
            """),
            {"user_id": user[0]}
        ).fetchall()
        return [_history_response(row, int(row[14]), int(row[15])) for row in rows]
    finally:
        db.close()


@router.get("/history/{history_id}", response_model=BacktestHistoryDetailResponse)
def get_history(history_id: int, authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        row = db.execute(
            text("""
                SELECT id, symbol, master_timeframe, account_id, broker_id, broker_name,
                       account_name, bridge_id, start_date, initial_balance, final_balance,
                       first_trade_at, last_trade_at, created_at, session_number, alarm_count,
                       orders, alarms, metrics
                FROM backtest_history WHERE id = :history_id AND user_id = :user_id
            """),
            {"history_id": history_id, "user_id": user[0]}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="History not found")
        header = _history_response(row, int(row[14]), int(row[15]))
        stored_orders = json.loads(row[16])
        stored_alarms = json.loads(row[17]) if row[17] else []
        return BacktestHistoryDetailResponse(
            **header.model_dump(),
            orders=[BacktestOrderItem(**item) for item in stored_orders],
            alarms=[BacktestAlarmItem(**item) for item in stored_alarms],
            metrics=json.loads(row[18]) if row[18] else None
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
