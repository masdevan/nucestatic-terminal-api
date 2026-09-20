import math
import re
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.broker import (
    BrokerAccountResponse,
    BrokerPairRequest,
    BrokerPairResponse,
    BrokerCreateRequest,
    BrokerResponse,
    BrokerUpdateRequest
)
from app.api.controllers.auth import require_user
from app.api.routes.broker_shared import accounts_for, fetch_broker_row, pairs_for, validate_name

router = APIRouter()

SPREAD_TYPES = {"pips", "money"}
PAIR_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,19}$")
MAX_PAIRS = 200


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
    name = validate_name(req.name)
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
        row = fetch_broker_row(db, broker_id, user[0])
        name = validate_name(req.name) if req.name is not None else row[1]
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
            pairs=pairs if pairs is not None else pairs_for(db, broker_id),
            accounts=accounts_for(db, broker_id),
            updated_at=_updated_at(db, broker_id)
        )
    finally:
        db.close()


@router.delete("/{broker_id}")
def delete_broker(broker_id: int, authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        fetch_broker_row(db, broker_id, user[0])
        db.execute(
            text("DELETE FROM broker_pairs WHERE broker_id = :broker_id"),
            {"broker_id": broker_id}
        )
        db.execute(
            text("DELETE FROM broker_orders WHERE broker_id = :broker_id"),
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
