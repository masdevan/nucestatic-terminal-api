import json
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.backtest import BacktestTradeStateRequest, BacktestTradeStateResponse
from app.api.controllers.auth import require_user
from app.api.routes.backtest_shared import (
    MAX_METRICS_CHARS,
    MAX_ORDERS,
    _order_response,
    _reroll_tickets,
    _validate_order
)

router = APIRouter()

@router.get("/trade-state", response_model=BacktestTradeStateResponse)
def get_trade_state(authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        session_row = db.execute(
            text("SELECT balance, metrics FROM backtest_sessions WHERE user_id = :user_id"),
            {"user_id": user[0]}
        ).fetchone()
        rows = db.execute(
            text("""
                SELECT local_id, symbol, side, order_type, lots, entry_price, tp_price, sl_price,
                       status, open_price, close_price, pnl, close_reason, opened_at, closed_at,
                       ticket
                FROM backtest_orders WHERE user_id = :user_id ORDER BY id
            """),
            {"user_id": user[0]}
        ).fetchall()
        return BacktestTradeStateResponse(
            balance=float(session_row[0]) if session_row else 0,
            orders=[_order_response(row) for row in rows],
            metrics=json.loads(session_row[1]) if session_row and session_row[1] else None
        )
    finally:
        db.close()


@router.put("/trade-state", response_model=BacktestTradeStateResponse)
def save_trade_state(req: BacktestTradeStateRequest, authorization: str = Header(None)):
    if len(req.orders) > MAX_ORDERS:
        raise HTTPException(status_code=422, detail=f"Orders limited to {MAX_ORDERS}")
    orders = _reroll_tickets([_validate_order(item) for item in req.orders])
    metrics_json = json.dumps(req.metrics) if req.metrics else None
    if metrics_json is not None and len(metrics_json) > MAX_METRICS_CHARS:
        raise HTTPException(status_code=422, detail="Metrics payload too large")

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
                        (user_id, local_id, ticket, symbol, side, order_type, lots, entry_price,
                         tp_price, sl_price, status, open_price, close_price, pnl, close_reason,
                         opened_at, closed_at)
                    VALUES
                        (:user_id, :local_id, :ticket, :symbol, :side, :order_type, :lots, :entry_price,
                         :tp_price, :sl_price, :status, :open_price, :close_price, :pnl, :close_reason,
                         :opened_at, :closed_at)
                """),
                [{**order.model_dump(), "user_id": user[0]} for order in orders]
            )
        db.execute(
            text("""
                UPDATE backtest_sessions
                SET balance = :balance, metrics = :metrics
                WHERE user_id = :user_id
            """),
            {"balance": req.balance, "metrics": metrics_json, "user_id": user[0]}
        )
        db.commit()
        return BacktestTradeStateResponse(
            balance=req.balance,
            orders=orders,
            metrics=req.metrics
        )
    finally:
        db.close()
