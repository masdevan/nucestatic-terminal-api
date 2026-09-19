import math
import re
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.broker import (
    BrokerAccountRequest,
    BrokerAccountResponse,
    BrokerAccountUpdate,
    BrokerCreateRequest,
    BrokerPairRequest,
    BrokerPairResponse,
    BrokerResponse,
    BrokerUpdateRequest
)
from app.api.controllers.auth import require_user

router = APIRouter()

SPREAD_TYPES = {"pips", "money"}
PAIR_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,19}$")
MAX_PAIRS = 200
MAX_LEVERAGE = 10000


def _validate_name(name: str) -> str:
    value = name.strip()
    if not value or len(value) > 100:
        raise HTTPException(status_code=422, detail="Name must be 1-100 characters")
    return value


def _validate_pairs(pairs: list[BrokerPairRequest]) -> list[BrokerPairResponse]:
    if len(pairs) > MAX_PAIRS:
        raise HTTPException(status_code=422, detail="Too many pairs")
    out = []
    seen = set()
    for entry in pairs:
        pair = entry.pair.strip().upper()
        if pair != "*" and not PAIR_PATTERN.fullmatch(pair):
            raise HTTPException(status_code=422, detail="Invalid pair name")
        if pair in seen:
            raise HTTPException(status_code=422, detail="Duplicate pair")
        seen.add(pair)
        spread_type = entry.spread_type.strip().lower()
        if spread_type not in SPREAD_TYPES:
            raise HTTPException(status_code=422, detail="Spread type must be pips or money")
        if not math.isfinite(entry.spread_value) or entry.spread_value < 0:
            raise HTTPException(status_code=422, detail="Spread value must be zero or greater")
        if not math.isfinite(entry.lot) or entry.lot <= 0 or entry.lot > 10000:
            raise HTTPException(status_code=422, detail="Lot must be greater than zero")
        out.append(
            BrokerPairResponse(
                pair=pair,
                spread_type=spread_type,
                spread_value=entry.spread_value,
                lot=entry.lot
            )
        )
    return out


def _validate_balance(balance: float) -> float:
    if not math.isfinite(balance) or balance < 0:
        raise HTTPException(status_code=422, detail="Balance must be zero or greater")
    return balance


def _validate_leverage(leverage: int) -> int:
    if leverage < 1 or leverage > MAX_LEVERAGE:
        raise HTTPException(status_code=422, detail=f"Leverage must be 1-{MAX_LEVERAGE}")
    return leverage


def _fetch_row(db, broker_id: int, user_id: int):
    row = db.execute(
        text("SELECT id, name, updated_at FROM brokers WHERE id = :broker_id AND user_id = :user_id"),
        {"broker_id": broker_id, "user_id": user_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Broker not found")
    return row


def _pairs_for(db, broker_id: int) -> list[BrokerPairResponse]:
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


def _accounts_for(db, broker_id: int) -> list[BrokerAccountResponse]:
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


def _insert_pairs(db, broker_id: int, pairs: list[BrokerPairResponse]) -> None:
    for entry in pairs:
        db.execute(
            text("""
                INSERT INTO broker_pairs (broker_id, pair, spread_type, spread_value, lot)
                VALUES (:broker_id, :pair, :spread_type, :spread_value, :lot)
            """),
            {
                "broker_id": broker_id,
                "pair": entry.pair,
                "spread_type": entry.spread_type,
                "spread_value": entry.spread_value,
                "lot": entry.lot
            }
        )


def _updated_at(db, broker_id: int) -> str:
    row = db.execute(
        text("SELECT updated_at FROM brokers WHERE id = :broker_id"),
        {"broker_id": broker_id}
    ).fetchone()
    return str(row[0])


@router.get("", response_model=list[BrokerResponse])
def list_brokers(authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        rows = db.execute(
            text("SELECT id, name, updated_at FROM brokers WHERE user_id = :user_id ORDER BY id"),
            {"user_id": user[0]}
        ).fetchall()

        pairs_by_broker = {}
        accounts_by_broker = {}
        if rows:
            ids = [r[0] for r in rows]
            placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
            params = {f"id{i}": value for i, value in enumerate(ids)}
            pair_rows = db.execute(
                text(f"""
                    SELECT broker_id, pair, spread_type, spread_value, lot FROM broker_pairs
                    WHERE broker_id IN ({placeholders})
                    ORDER BY pair
                """),
                params
            ).fetchall()
            for r in pair_rows:
                pairs_by_broker.setdefault(r[0], []).append(
                    BrokerPairResponse(
                        pair=r[1],
                        spread_type=r[2],
                        spread_value=float(r[3]),
                        lot=float(r[4])
                    )
                )
            account_rows = db.execute(
                text(f"""
                    SELECT broker_id, id, name, balance, leverage FROM broker_accounts
                    WHERE broker_id IN ({placeholders})
                    ORDER BY id
                """),
                params
            ).fetchall()
            for r in account_rows:
                accounts_by_broker.setdefault(r[0], []).append(
                    BrokerAccountResponse(
                        id=r[1],
                        name=r[2],
                        balance=float(r[3]),
                        leverage=r[4]
                    )
                )

        return [
            BrokerResponse(
                id=r[0],
                name=r[1],
                pairs=pairs_by_broker.get(r[0], []),
                accounts=accounts_by_broker.get(r[0], []),
                updated_at=str(r[2])
            )
            for r in rows
        ]
    finally:
        db.close()


@router.post("", response_model=BrokerResponse)
def create_broker(req: BrokerCreateRequest, authorization: str = Header(None)):
    name = _validate_name(req.name)
    pairs = _validate_pairs(req.pairs)

    db, user = require_user(authorization)
    try:
        existing = db.execute(
            text("SELECT id FROM brokers WHERE user_id = :user_id AND name = :name"),
            {"user_id": user[0], "name": name}
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Broker name already exists")

        try:
            result = db.execute(
                text("INSERT INTO brokers (user_id, name) VALUES (:user_id, :name)"),
                {"user_id": user[0], "name": name}
            )
            broker_id = result.lastrowid
            _insert_pairs(db, broker_id, pairs)
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=409, detail="Broker name already exists")

        return BrokerResponse(
            id=broker_id,
            name=name,
            pairs=pairs,
            accounts=[],
            updated_at=_updated_at(db, broker_id)
        )
    finally:
        db.close()


@router.patch("/{broker_id}", response_model=BrokerResponse)
def update_broker(broker_id: int, req: BrokerUpdateRequest, authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        row = _fetch_row(db, broker_id, user[0])
        name = _validate_name(req.name) if req.name is not None else row[1]
        pairs = _validate_pairs(req.pairs) if req.pairs is not None else None

        if name != row[1]:
            existing = db.execute(
                text("""
                    SELECT id FROM brokers
                    WHERE user_id = :user_id AND name = :name AND id != :broker_id
                """),
                {"user_id": user[0], "name": name, "broker_id": broker_id}
            ).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="Broker name already exists")

        try:
            db.execute(
                text("UPDATE brokers SET name = :name WHERE id = :broker_id"),
                {"name": name, "broker_id": broker_id}
            )
            if pairs is not None:
                db.execute(
                    text("DELETE FROM broker_pairs WHERE broker_id = :broker_id"),
                    {"broker_id": broker_id}
                )
                _insert_pairs(db, broker_id, pairs)
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=409, detail="Broker name already exists")

        return BrokerResponse(
            id=broker_id,
            name=name,
            pairs=pairs if pairs is not None else _pairs_for(db, broker_id),
            accounts=_accounts_for(db, broker_id),
            updated_at=_updated_at(db, broker_id)
        )
    finally:
        db.close()


@router.delete("/{broker_id}")
def delete_broker(broker_id: int, authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        _fetch_row(db, broker_id, user[0])
        db.execute(
            text("DELETE FROM broker_pairs WHERE broker_id = :broker_id"),
            {"broker_id": broker_id}
        )
        db.execute(
            text("DELETE FROM broker_accounts WHERE broker_id = :broker_id"),
            {"broker_id": broker_id}
        )
        db.execute(
            text("DELETE FROM brokers WHERE id = :broker_id"),
            {"broker_id": broker_id}
        )
        db.commit()
        return {"detail": "Broker deleted"}
    finally:
        db.close()


@router.post("/{broker_id}/accounts", response_model=BrokerAccountResponse)
def create_account(
    broker_id: int,
    req: BrokerAccountRequest,
    authorization: str = Header(None)
):
    name = _validate_name(req.name)
    balance = _validate_balance(req.balance)
    leverage = _validate_leverage(req.leverage)

    db, user = require_user(authorization)
    try:
        _fetch_row(db, broker_id, user[0])
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
        _fetch_row(db, broker_id, user[0])
        row = db.execute(
            text("""
                SELECT id, name, balance, leverage FROM broker_accounts
                WHERE id = :account_id AND broker_id = :broker_id
            """),
            {"account_id": account_id, "broker_id": broker_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found")

        name = _validate_name(req.name) if req.name is not None else row[1]
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
        _fetch_row(db, broker_id, user[0])
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
