from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text
from app.api.models.cron import CronJobCreateRequest, CronJobResponse, CronRunResponse, CronJobUpdateRequest
from app.api.controllers.auth import require_user
from app.api.routes.cron_shared import (
    JOB_SELECT,
    fetch_job,
    row_to_response,
    run_to_response,
    validate_bridge,
    validate_indicator,
    validate_interval,
    validate_symbol,
    validate_timeframe,
    values_json
)
from app.api.utils.urls import clean_webhook_url

router = APIRouter()


@router.get("/{job_id}/runs", response_model=list[CronRunResponse])
def list_job_runs(
    job_id: int,
    limit: int = Query(50, ge=1, le=200),
    authorization: str = Header(None)
):
    db, user = require_user(authorization)
    try:
        fetch_job(db, user[0], job_id)
        rows = db.execute(
            text("""
                SELECT id, status, candle_time, alarms, duration_ms, error, ran_at
                FROM cron_job_runs
                WHERE job_id = :job_id
                ORDER BY id DESC
                LIMIT :limit
            """),
            {"job_id": job_id, "limit": limit}
        ).fetchall()
        return [run_to_response(row) for row in rows]
    finally:
        db.close()


@router.get("", response_model=list[CronJobResponse])
def list_jobs(authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        rows = db.execute(
            text(f"{JOB_SELECT} WHERE cj.user_id = :user_id ORDER BY cj.id"),
            {"user_id": user[0]}
        ).fetchall()
        return [row_to_response(row) for row in rows]
    finally:
        db.close()


@router.post("", response_model=CronJobResponse)
def create_job(req: CronJobCreateRequest, authorization: str = Header(None)):
    symbol = validate_symbol(req.symbol)
    timeframe = validate_timeframe(req.timeframe)
    interval = validate_interval(req.interval_seconds)
    webhook_url = clean_webhook_url(req.webhook)
    params_json = values_json(req.values)

    db, user = require_user(authorization)
    try:
        validate_indicator(db, user[0], req.indicator_id)
        validate_bridge(db, req.bridge_id)
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
        return row_to_response(fetch_job(db, user[0], inserted.lastrowid))
    finally:
        db.close()


@router.patch("/{job_id}", response_model=CronJobResponse)
def update_job(job_id: int, req: CronJobUpdateRequest, authorization: str = Header(None)):
    db, user = require_user(authorization)
    try:
        fetch_job(db, user[0], job_id)
        fields = req.model_fields_set
        if "interval_seconds" in fields:
            if req.interval_seconds is None:
                raise HTTPException(status_code=422, detail="interval_seconds is required")
            db.execute(
                text("UPDATE cron_jobs SET interval_seconds = :interval WHERE id = :job_id"),
                {"interval": validate_interval(req.interval_seconds), "job_id": job_id}
            )
        if "webhook" in fields:
            db.execute(
                text("UPDATE cron_jobs SET webhook_url = :webhook WHERE id = :job_id"),
                {"webhook": clean_webhook_url(req.webhook), "job_id": job_id}
            )
        if "values" in fields:
            db.execute(
                text("UPDATE cron_jobs SET params_json = :params WHERE id = :job_id"),
                {"params": values_json(req.values), "job_id": job_id}
            )
        if "enabled" in fields:
            if req.enabled is None:
                raise HTTPException(status_code=422, detail="enabled is required")
            db.execute(
                text("UPDATE cron_jobs SET enabled = :enabled WHERE id = :job_id"),
                {"enabled": 1 if req.enabled else 0, "job_id": job_id}
            )
        db.commit()
        return row_to_response(fetch_job(db, user[0], job_id))
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
