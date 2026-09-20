from fastapi import HTTPException
from sqlalchemy import text
from app.api.models.broker import BrokerAccountResponse, BrokerPairResponse


def validate_name(name: str) -> str:
    value = name.strip()
    if not value or len(value) > 100:
        raise HTTPException(status_code=422, detail="Name must be 1-100 characters")
    return value


def fetch_broker_row(db, broker_id: int, user_id: int):
    row = db.execute(
        text("SELECT id, name, updated_at FROM brokers WHERE id = :broker_id AND user_id = :user_id"),
        {"broker_id": broker_id, "user_id": user_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Broker not found")
    return row


def pairs_for(db, broker_id: int) -> list[BrokerPairResponse]:
    rows = db.execute(
        text("""
            SELECT pair, spread_type, spread_value, lot FROM broker_pairs
            WHERE broker_id = :broker_id
            ORDER BY pair
        """),
        {"broker_id": broker_id}
    ).fetchall()
    return [
        BrokerPairResponse(
            pair=r[0],
            spread_type=r[1],
            spread_value=float(r[2]),
            lot=float(r[3])
        )
        for r in rows
    ]


def accounts_for(db, broker_id: int) -> list[BrokerAccountResponse]:
    rows = db.execute(
        text("""
            SELECT id, name, balance, leverage FROM broker_accounts
            WHERE broker_id = :broker_id
            ORDER BY id
        """),
        {"broker_id": broker_id}
    ).fetchall()
    return [
        BrokerAccountResponse(id=r[0], name=r[1], balance=float(r[2]), leverage=r[3])
        for r in rows
    ]
