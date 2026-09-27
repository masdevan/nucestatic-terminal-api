import json
from fastapi import HTTPException
from sqlalchemy import text
from app.api.models.cron import CronJobResponse, CronRunResponse
from app.api.utils.values import validate_input_values

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


def parse_values(raw) -> dict | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def row_to_response(row) -> CronJobResponse:
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
        values=parse_values(row[9]),
        enabled=bool(row[10]),
        last_run_at=row[11],
        last_alert_at=row[12],
        last_error=row[13],
        created_at=row[14]
    )


def run_to_response(row) -> CronRunResponse:
    return CronRunResponse(
        id=row[0],
        status=row[1],
        candle_time=row[2],
        alarms=int(row[3]),
        duration_ms=int(row[4]),
        error=row[5],
        ran_at=row[6]
    )


def fetch_job(db, user_id: int, job_id: int):
    row = db.execute(
        text(f"{JOB_SELECT} WHERE cj.id = :job_id AND cj.user_id = :user_id"),
        {"job_id": job_id, "user_id": user_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cron alert not found")
    return row


def validate_interval(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < MIN_INTERVAL or value > MAX_INTERVAL:
        raise HTTPException(
            status_code=422,
            detail=f"interval_seconds must be between {MIN_INTERVAL} and {MAX_INTERVAL}"
        )
    return value


def validate_indicator(db, user_id: int, indicator_id: int) -> None:
    row = db.execute(
        text("SELECT id FROM indicators WHERE id = :indicator_id AND user_id = :user_id"),
        {"indicator_id": indicator_id, "user_id": user_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Indicator not found")


def validate_bridge(db, bridge_id: int) -> None:
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


def validate_symbol(raw: str) -> str:
    value = (raw or "").strip()
    if not value or len(value) > 30:
        raise HTTPException(status_code=422, detail="symbol must be 1-30 characters")
    return value


def validate_timeframe(raw: str) -> str:
    value = (raw or "").strip().upper()
    if not value or len(value) > 10:
        raise HTTPException(status_code=422, detail="timeframe must be 1-10 characters")
    return value


def values_json(raw: dict | None) -> str | None:
    values = validate_input_values(raw) if raw is not None else None
    return json.dumps(values) if values else None
