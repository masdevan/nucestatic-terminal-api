import math
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.broker import (
    BrokerAccountRequest,
    BrokerAccountResponse,
    BrokerAccountUpdate
)
from app.api.controllers.auth import require_user
from app.api.routes.broker_shared import fetch_broker_row, validate_name

router = APIRouter()

MAX_LEVERAGE = 10000


def _validate_balance(balance: float) -> float:
    if not math.isfinite(balance) or balance < 0:
        raise HTTPException(status_code=422, detail="Balance must be zero or greater")
    return balance


def _validate_leverage(leverage: int) -> int:
    if leverage < 1 or leverage > MAX_LEVERAGE:
        raise HTTPException(status_code=422, detail=f"Leverage must be 1-{MAX_LEVERAGE}")
    return leverage


@router.post("/{broker_id}/accounts", response_model=BrokerAccountResponse)
def create_account(
    broker_id: int,
    req: BrokerAccountRequest,
    authorization: str = Header(None)
):
    name = validate_name(req.name)
    balance = _validate_balance(req.balance)
    leverage = _validate_leverage(req.leverage)

    db, user = require_user(authorization)
    try:
        fetch_broker_row(db, broker_id, user[0])
        existing = db.execute(
            text("SELECT id FROM broker_accounts WHERE broker_id = :broker_id AND name = :name"),
            {"broker_id": broker_id, "name": name}
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Account name already exists")

        try:
            result = db.execute(
                text("""
                    INSERT INTO broker_accounts (broker_id, name, balance, leverage)
                    VALUES (:broker_id, :name, :balance, :leverage)
                """),
                {"broker_id": broker_id, "name": name, "balance": balance, "leverage": leverage}
            )
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=409, detail="Account name already exists")

        return BrokerAccountResponse(
            id=result.lastrowid,
            name=name,
            balance=balance,
            leverage=leverage
        )
    finally:
        db.close()


@router.patch("/{broker_id}/accounts/{account_id}", response_model=BrokerAccountResponse)
def update_account(
    broker_id: int,
    account_id: int,
    req: BrokerAccountUpdate,
    authorization: str = Header(None)
):
    db, user = require_user(authorization)
    try:
        fetch_broker_row(db, broker_id, user[0])
        row = db.execute(
            text("""
                SELECT id, name, balance, leverage FROM broker_accounts
                WHERE id = :account_id AND broker_id = :broker_id
            """),
            {"account_id": account_id, "broker_id": broker_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found")

        name = validate_name(req.name) if req.name is not None else row[1]
        balance = _validate_balance(req.balance) if req.balance is not None else float(row[2])
        leverage = _validate_leverage(req.leverage) if req.leverage is not None else row[3]

        if name != row[1]:
            existing = db.execute(
                text("""
                    SELECT id FROM broker_accounts
                    WHERE broker_id = :broker_id AND name = :name AND id != :account_id
                """),
                {"broker_id": broker_id, "name": name, "account_id": account_id}
            ).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="Account name already exists")

        try:
            db.execute(
                text("""
                    UPDATE broker_accounts
                    SET name = :name, balance = :balance, leverage = :leverage
                    WHERE id = :account_id
                """),
                {"name": name, "balance": balance, "leverage": leverage, "account_id": account_id}
            )
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=409, detail="Account name already exists")

        return BrokerAccountResponse(id=account_id, name=name, balance=balance, leverage=leverage)
    finally:
        db.close()


@router.delete("/{broker_id}/accounts/{account_id}")
def delete_account(broker_id: int, account_id: int, authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        fetch_broker_row(db, broker_id, user[0])
        db.execute(
            text("DELETE FROM broker_orders WHERE account_id = :account_id AND broker_id = :broker_id"),
            {"account_id": account_id, "broker_id": broker_id}
        )
        result = db.execute(
            text("DELETE FROM broker_accounts WHERE id = :account_id AND broker_id = :broker_id"),
            {"account_id": account_id, "broker_id": broker_id}
        )
        db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"detail": "Account deleted"}
    finally:
        db.close()
