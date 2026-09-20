from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text
from app.api.models.broker import BrokerOrderResponse
from app.api.controllers.auth import require_user
from app.api.routes.broker_shared import fetch_broker_row

router = APIRouter()


@router.get("/{broker_id}/accounts/{account_id}/orders", response_model=list[BrokerOrderResponse])
def list_orders(
    broker_id: int,
    account_id: int,
    status: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    page: int = Query(1, ge=1),
    authorization: str = Header(None)
):
    db, user = require_user(authorization)
    try:
        fetch_broker_row(db, broker_id, user[0])
        account = db.execute(
            text("SELECT id FROM broker_accounts WHERE id = :account_id AND broker_id = :broker_id"),
            {"account_id": account_id, "broker_id": broker_id}
        ).fetchone()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        params = {"account_id": account_id, "limit": limit, "offset": (page - 1) * limit}
        query = """
            SELECT id, symbol, side, lots, entry_price, tp_price, sl_price,
                   status, close_price, pnl, opened_at, closed_at
            FROM broker_orders
            WHERE account_id = :account_id
        """
        if status in ("open", "closed"):
            query += " AND status = :status"
            params["status"] = status
        query += " ORDER BY id DESC LIMIT :limit OFFSET :offset"

        rows = db.execute(text(query), params).fetchall()
        return [
            BrokerOrderResponse(
                id=r[0],
                symbol=r[1],
                side=r[2],
                lots=float(r[3]),
                entry_price=float(r[4]),
                tp_price=float(r[5]) if r[5] is not None else None,
                sl_price=float(r[6]) if r[6] is not None else None,
                status=r[7],
                close_price=float(r[8]) if r[8] is not None else None,
                pnl=float(r[9]) if r[9] is not None else None,
                opened_at=str(r[10]),
                closed_at=str(r[11]) if r[11] is not None else None
            )
            for r in rows
        ]
    finally:
        db.close()
