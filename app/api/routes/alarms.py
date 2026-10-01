from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query
from sqlalchemy import text
from app.api.models.alarm import AlarmCreateRequest, AlarmResponse
from app.api.controllers.auth import require_user
from app.api.routes.alarm_shared import (
    ALARM_COLUMNS,
    ENTRY_TYPES,
    deliver_webhook,
    price,
    row_to_response,
    source_filter,
    webhook_payload
)
from app.api.utils.dry_run import is_dry_run
from app.api.utils.urls import clean_webhook_url

router = APIRouter()


@router.get("")
def list_alarms(
    limit: int = Query(25, ge=1, le=1000),
    page: int = Query(1, ge=1),
    source: str | None = Query(None),
    backtest: bool | None = Query(None),
    authorization: str = Header(None)
):
    source_value = source_filter(source)
    db, row = require_user(authorization)
    try:
        where = "user_id = :user_id"
        params = {"user_id": row[0]}
        if source_value is not None:
            where += " AND source = :source"
            params["source"] = source_value
        if backtest is not None:
            where += " AND backtest = :backtest"
            params["backtest"] = 1 if backtest else 0
        total = db.execute(
            text(f"SELECT COUNT(*) FROM alarms WHERE {where}"),
            params
        ).scalar()
        unread = db.execute(
            text(f"SELECT COUNT(*) FROM alarms WHERE {where} AND is_read = 0"),
            params
        ).scalar()
        rows = db.execute(
            text(f"SELECT {ALARM_COLUMNS} FROM alarms WHERE {where} ORDER BY is_read ASC, id DESC LIMIT :limit OFFSET :offset"),
            {**params, "limit": limit, "offset": (page - 1) * limit}
        ).fetchall()
        total_pages = (total + limit - 1) // limit if total > 0 else 1
        return {
            "alarms": [row_to_response(r).model_dump() for r in rows],
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
    indicator_name = (req.indicator_name or "").strip() or None
    if indicator_name is not None and len(indicator_name) > 100:
        raise HTTPException(status_code=422, detail="indicator_name must be at most 100 characters")
    entry_price = price(req.entry_price, "entry_price", True)
    tp_price = price(req.tp_price, "tp_price", False)
    sl_price = price(req.sl_price, "sl_price", False)
    timeframe = (req.timeframe or "").strip().upper() or None
    if timeframe is not None and len(timeframe) > 10:
        raise HTTPException(status_code=422, detail="timeframe must be at most 10 characters")
    webhook_url = None if req.backtest else clean_webhook_url(req.webhook)

    db, row = require_user(authorization)
    try:
        inserted = db.execute(
            text("""
                INSERT INTO alarms (user_id, symbol, description, entry_type, entry_price, tp_price, sl_price, timeframe, webhook_url, backtest, source, indicator_name)
                VALUES (:user_id, :symbol, :description, :entry_type, :entry_price, :tp_price, :sl_price, :timeframe, :webhook_url, :backtest, :source, :indicator_name)
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
                "webhook_url": webhook_url,
                "backtest": 1 if req.backtest else 0,
                "source": req.source,
                "indicator_name": indicator_name
            }
        )
        alarm_id = inserted.lastrowid
        db.commit()
        result = db.execute(
            text(f"SELECT {ALARM_COLUMNS} FROM alarms WHERE id = :alarm_id"),
            {"alarm_id": alarm_id}
        ).fetchone()
        alarm = row_to_response(result)
        if webhook_url and not is_dry_run():
            background.add_task(deliver_webhook, webhook_url, webhook_payload(alarm))
        return alarm
    finally:
        db.close()


@router.patch("/read-all")
def read_all_alarms(
    source: str | None = Query(None),
    backtest: bool | None = Query(None),
    authorization: str = Header(None)
):
    source_value = source_filter(source)
    db, row = require_user(authorization)
    try:
        where = "user_id = :user_id AND is_read = 0"
        params = {"user_id": row[0]}
        if source_value is not None:
            where += " AND source = :source"
            params["source"] = source_value
        if backtest is not None:
            where += " AND backtest = :backtest"
            params["backtest"] = 1 if backtest else 0
        db.execute(text(f"UPDATE alarms SET is_read = 1 WHERE {where}"), params)
        db.commit()
        return {"detail": "Alarms marked as read"}
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
def delete_all_alarms(
    source: str | None = Query(None),
    backtest: bool | None = Query(None),
    authorization: str = Header(None)
):
    source_value = source_filter(source)
    db, row = require_user(authorization)
    try:
        where = "user_id = :user_id"
        params = {"user_id": row[0]}
        if source_value is not None:
            where += " AND source = :source"
            params["source"] = source_value
        if backtest is not None:
            where += " AND backtest = :backtest"
            params["backtest"] = 1 if backtest else 0
        result = db.execute(text(f"DELETE FROM alarms WHERE {where}"), params)
        db.commit()
        return {"detail": f"{result.rowcount} alarm(s) deleted"}
    finally:
        db.close()


@router.delete("/backtest")
def delete_backtest_alarms(authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        result = db.execute(
            text("DELETE FROM alarms WHERE user_id = :user_id AND backtest = 1"),
            {"user_id": row[0]}
        )
        db.commit()
        return {"detail": f"{result.rowcount} backtest alarm(s) deleted"}
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
