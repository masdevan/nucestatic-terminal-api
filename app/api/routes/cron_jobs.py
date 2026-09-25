import json
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.cron import CronJobCreateRequest, CronJobResponse, CronJobUpdateRequest
from app.api.controllers.auth import require_user
from app.api.utils.urls import clean_webhook_url
from app.api.utils.values import validate_input_values

router = APIRouter()

MIN_INTERVAL = 10
MAX_INTERVAL = 2592000

JOB_SELECT = """
    SELECT cj.id, cj.indicator_id, i.name, cj.bridge_id, b.name, cj.symbol, cj.timeframe,
           cj.interval_seconds, cj.webhook_url, cj.params_json, cj.enabled,
           cj.last_run_at, cj.last_alert_at, cj.last_error, cj.created_at
    FROM cron_jobs cj
    JOIN indicators i ON i.id = cj.indicator_id
    JOIN bridge_apis b ON b.id = cj.bridge_id
"""


def _parse_values(raw) -> dict | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _row_to_response(row) -> CronJobResponse:
    return CronJobResponse(
        id=row[0],
        indicator_id=row[1],
        indicator_name=row[2],
        bridge_id=row[3],
        bridge_name=row[4],
        symbol=row[5],
        timeframe=row[6],
        interval_seconds=int(row[7]),
        webhook_url=row[8],
        values=_parse_values(row[9]),
        enabled=bool(row[10]),
        last_run_at=row[11],
        last_alert_at=row[12],
        last_error=row[13],
        created_at=row[14]
    )


def _fetch(db, user_id: int, job_id: int):
    row = db.execute(
        text(f"{JOB_SELECT} WHERE cj.id = :job_id AND cj.user_id = :user_id"),
        {"job_id": job_id, "user_id": user_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cron alert not found")
    return row


def _interval(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < MIN_INTERVAL or value > MAX_INTERVAL:
        raise HTTPException(
            status_code=422,
            detail=f"interval_seconds must be between {MIN_INTERVAL} and {MAX_INTERVAL}"
        )
    return value


def _indicator(db, user_id: int, indicator_id: int) -> None:
    row = db.execute(
        text("SELECT id FROM indicators WHERE id = :indicator_id AND user_id = :user_id"),
        {"indicator_id": indicator_id, "user_id": user_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Indicator not found")


def _bridge(db, bridge_id: int) -> None:
    row = db.execute(
        text("SELECT mode, active FROM bridge_apis WHERE id = :bridge_id"),
        {"bridge_id": bridge_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Bridge not found")
    if row[0] != "dynamic":
        raise HTTPException(status_code=422, detail="Cron alerts require a dynamic bridge")
    if not row[1]:
        raise HTTPException(status_code=422, detail="Bridge is inactive")


def _symbol(raw: str) -> str:
    value = (raw or "").strip()
    if not value or len(value) > 30:
        raise HTTPException(status_code=422, detail="symbol must be 1-30 characters")
    return value


def _timeframe(raw: str) -> str:
    value = (raw or "").strip().upper()
    if not value or len(value) > 10:
        raise HTTPException(status_code=422, detail="timeframe must be 1-10 characters")
    return value


def _values_json(raw: dict | None) -> str | None:
    values = validate_input_values(raw) if raw is not None else None
    return json.dumps(values) if values else None


@router.get("", response_model=list[CronJobResponse])
def list_jobs(authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        rows = db.execute(
            text(f"{JOB_SELECT} WHERE cj.user_id = :user_id ORDER BY cj.id"),
            {"user_id": user[0]}
        ).fetchall()
        return [_row_to_response(row) for row in rows]
    finally:
        db.close()


@router.post("", response_model=CronJobResponse)
def create_job(req: CronJobCreateRequest, authorization: str = Header(None)):
    symbol = _symbol(req.symbol)
    timeframe = _timeframe(req.timeframe)
    interval = _interval(req.interval_seconds)
    webhook_url = clean_webhook_url(req.webhook)
    params_json = _values_json(req.values)

    db, user = require_user(authorization)
    try:
        _indicator(db, user[0], req.indicator_id)
        _bridge(db, req.bridge_id)
        clash = db.execute(
            text("""
                SELECT id FROM cron_jobs
                WHERE user_id = :user_id AND indicator_id = :indicator_id AND bridge_id = :bridge_id
                  AND symbol = :symbol AND timeframe = :timeframe
            """),
            {
                "user_id": user[0],
                "indicator_id": req.indicator_id,
                "bridge_id": req.bridge_id,
                "symbol": symbol,
                "timeframe": timeframe
            }
        ).fetchone()
        if clash:
            raise HTTPException(status_code=409, detail="Cron alert already exists for this combination")
        inserted = db.execute(
            text("""
                INSERT INTO cron_jobs
                    (user_id, indicator_id, bridge_id, symbol, timeframe, interval_seconds,
                     webhook_url, params_json, enabled)
                VALUES
                    (:user_id, :indicator_id, :bridge_id, :symbol, :timeframe, :interval_seconds,
                     :webhook_url, :params_json, :enabled)
            """),
            {
                "user_id": user[0],
                "indicator_id": req.indicator_id,
                "bridge_id": req.bridge_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "interval_seconds": interval,
                "webhook_url": webhook_url,
                "params_json": params_json,
                "enabled": 1 if req.enabled else 0
            }
        )
        db.commit()
        return _row_to_response(_fetch(db, user[0], inserted.lastrowid))
    finally:
        db.close()


@router.patch("/{job_id}", response_model=CronJobResponse)
def update_job(job_id: int, req: CronJobUpdateRequest, authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        _fetch(db, user[0], job_id)
        fields = req.model_fields_set
        if "interval_seconds" in fields:
            if req.interval_seconds is None:
                raise HTTPException(status_code=422, detail="interval_seconds is required")
            db.execute(
                text("UPDATE cron_jobs SET interval_seconds = :interval WHERE id = :job_id"),
                {"interval": _interval(req.interval_seconds), "job_id": job_id}
            )
        if "webhook" in fields:
            db.execute(
                text("UPDATE cron_jobs SET webhook_url = :webhook WHERE id = :job_id"),
                {"webhook": clean_webhook_url(req.webhook), "job_id": job_id}
            )
        if "values" in fields:
            db.execute(
                text("UPDATE cron_jobs SET params_json = :params WHERE id = :job_id"),
                {"params": _values_json(req.values), "job_id": job_id}
            )
        if "enabled" in fields:
            if req.enabled is None:
                raise HTTPException(status_code=422, detail="enabled is required")
            db.execute(
                text("UPDATE cron_jobs SET enabled = :enabled WHERE id = :job_id"),
                {"enabled": 1 if req.enabled else 0, "job_id": job_id}
            )
        db.commit()
        return _row_to_response(_fetch(db, user[0], job_id))
    finally:
        db.close()


@router.delete("/{job_id}")
def delete_job(job_id: int, authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        result = db.execute(
            text("DELETE FROM cron_jobs WHERE id = :job_id AND user_id = :user_id"),
            {"job_id": job_id, "user_id": user[0]}
        )
        db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Cron alert not found")
        return {"detail": "Cron alert deleted"}
    finally:
        db.close()
