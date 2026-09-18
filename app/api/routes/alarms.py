import ipaddress
import json
import math
import socket
import urllib.parse
import urllib.request
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query
from sqlalchemy import text
from app.api.models.alarm import AlarmCreateRequest, AlarmResponse
from app.api.controllers.auth import require_user

router = APIRouter()

ENTRY_TYPES = {"buy", "sell"}


def _clean_url(raw: str | None) -> str | None:
    url = (raw or "").strip()
    if not url:
        return None
    if len(url) > 255:
        raise HTTPException(status_code=422, detail="webhook must be at most 255 characters")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=422, detail="webhook must be an http(s) URL")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except Exception:
        raise HTTPException(status_code=422, detail="webhook host could not be resolved")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise HTTPException(status_code=422, detail="webhook must target a public address")
    return url


def _price(value: float | None, name: str, required: bool) -> float | None:
    if value is None:
        if required:
            raise HTTPException(status_code=422, detail=f"{name} is required")
        return None
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise HTTPException(status_code=422, detail=f"{name} must be a number greater than 0")
    return float(value)


def _row_to_response(r) -> AlarmResponse:
    return AlarmResponse(
        id=r[0],
        symbol=r[1],
        description=r[2],
        entry_type=r[3],
        entry_price=float(r[4]),
        tp_price=float(r[5]) if r[5] is not None else None,
        sl_price=float(r[6]) if r[6] is not None else None,
        timeframe=r[7],
        is_read=bool(r[8]),
        created_at=r[9],
        webhook_url=r[10]
    )


def _deliver_webhook(url: str, payload: dict):
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 nucestatic-terminal"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


def _webhook_payload(alarm: AlarmResponse) -> dict:
    content = f"🔔 {alarm.entry_type.upper()} {alarm.symbol} @ {alarm.entry_price}"
    extras = []
    if alarm.tp_price is not None:
        extras.append(f"TP {alarm.tp_price}")
    if alarm.sl_price is not None:
        extras.append(f"SL {alarm.sl_price}")
    if extras:
        content += f" ({', '.join(extras)})"
    if alarm.description:
        content += f" — {alarm.description}"
    return {
        "event": "nucestatic.alarm.created",
        "content": content,
        "alarm": alarm.model_dump()
    }


@router.get("")
def list_alarms(
    limit: int = Query(25, ge=1, le=1000),
    page: int = Query(1, ge=1),
    authorization: str = Header(None)
):
    db, row = require_user(authorization)
    try:
        total = db.execute(
            text("SELECT COUNT(*) FROM alarms WHERE user_id = :user_id"),
            {"user_id": row[0]}
        ).scalar()
        unread = db.execute(
            text("SELECT COUNT(*) FROM alarms WHERE user_id = :user_id AND is_read = 0"),
            {"user_id": row[0]}
        ).scalar()
        rows = db.execute(
            text("SELECT id, symbol, description, entry_type, entry_price, tp_price, sl_price, timeframe, is_read, created_at, webhook_url FROM alarms WHERE user_id = :user_id ORDER BY is_read ASC, id DESC LIMIT :limit OFFSET :offset"),
            {"user_id": row[0], "limit": limit, "offset": (page - 1) * limit}
        ).fetchall()
        total_pages = (total + limit - 1) // limit if total > 0 else 1
        return {
            "alarms": [_row_to_response(r).model_dump() for r in rows],
            "total": total,
            "unread": unread,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
                "has_next": page * limit < total,
                "has_prev": page > 1
            }
        }
    finally:
        db.close()


@router.post("", response_model=AlarmResponse)
def create_alarm(req: AlarmCreateRequest, background: BackgroundTasks, authorization: str = Header(None)):
    symbol = req.symbol.strip()
    if not symbol or len(symbol) > 50:
        raise HTTPException(status_code=422, detail="symbol must be 1-50 characters")
    entry_type = req.entry_type.strip().lower()
    if entry_type not in ENTRY_TYPES:
        raise HTTPException(status_code=422, detail="entry_type must be buy or sell")
    description = (req.description or "").strip() or None
    if description is not None and len(description) > 500:
        raise HTTPException(status_code=422, detail="description must be at most 500 characters")
    entry_price = _price(req.entry_price, "entry_price", True)
    tp_price = _price(req.tp_price, "tp_price", False)
    sl_price = _price(req.sl_price, "sl_price", False)
    timeframe = (req.timeframe or "").strip().upper() or None
    if timeframe is not None and len(timeframe) > 10:
        raise HTTPException(status_code=422, detail="timeframe must be at most 10 characters")
    webhook_url = _clean_url(req.webhook)

    db, row = require_user(authorization)
    try:
        inserted = db.execute(
            text("""
                INSERT INTO alarms (user_id, symbol, description, entry_type, entry_price, tp_price, sl_price, timeframe, webhook_url)
                VALUES (:user_id, :symbol, :description, :entry_type, :entry_price, :tp_price, :sl_price, :timeframe, :webhook_url)
            """),
            {
                "user_id": row[0],
                "symbol": symbol,
                "description": description,
                "entry_type": entry_type,
                "entry_price": entry_price,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "timeframe": timeframe,
                "webhook_url": webhook_url
            }
        )
        alarm_id = inserted.lastrowid
        db.commit()
        result = db.execute(
            text("SELECT id, symbol, description, entry_type, entry_price, tp_price, sl_price, timeframe, is_read, created_at, webhook_url FROM alarms WHERE id = :alarm_id"),
            {"alarm_id": alarm_id}
        ).fetchone()
        alarm = _row_to_response(result)
        if webhook_url:
            background.add_task(_deliver_webhook, webhook_url, _webhook_payload(alarm))
        return alarm
    finally:
        db.close()


@router.patch("/read-all")
def read_all_alarms(authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        db.execute(
            text("UPDATE alarms SET is_read = 1 WHERE user_id = :user_id AND is_read = 0"),
            {"user_id": row[0]}
        )
        db.commit()
        return {"detail": "All alarms marked as read"}
    finally:
        db.close()


@router.patch("/{alarm_id}/read")
def read_alarm(alarm_id: int, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        result = db.execute(
            text("UPDATE alarms SET is_read = 1 WHERE id = :alarm_id AND user_id = :user_id"),
            {"alarm_id": alarm_id, "user_id": row[0]}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Alarm not found")
        db.commit()
        return {"detail": "Alarm marked as read"}
    finally:
        db.close()


@router.delete("")
def delete_all_alarms(authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        result = db.execute(
            text("DELETE FROM alarms WHERE user_id = :user_id"),
            {"user_id": row[0]}
        )
        db.commit()
        return {"detail": f"{result.rowcount} alarm(s) deleted"}
    finally:
        db.close()


@router.delete("/{alarm_id}")
def delete_alarm(alarm_id: int, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        result = db.execute(
            text("DELETE FROM alarms WHERE id = :alarm_id AND user_id = :user_id"),
            {"alarm_id": alarm_id, "user_id": row[0]}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Alarm not found")
        db.commit()
        return {"detail": "Alarm deleted"}
    finally:
        db.close()
