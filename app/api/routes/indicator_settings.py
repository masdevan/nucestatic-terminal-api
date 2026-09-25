import json
import re
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.indicator import IndicatorSettingsRequest, IndicatorSettingsResponse
from app.api.controllers.auth import require_user
from app.api.utils.values import validate_input_values

router = APIRouter()

KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")


def _validate_key(key: str) -> str:
    value = key.strip()
    if not KEY_PATTERN.match(value):
        raise HTTPException(status_code=422, detail="Invalid indicator key")
    return value


@router.get("")
def list_indicator_settings(authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        rows = db.execute(
            text("""
                SELECT indicator_key, values_json FROM indicator_settings
                WHERE user_id = :user_id ORDER BY indicator_key
            """),
            {"user_id": row[0]}
        ).fetchall()
        settings = []
        for item in rows:
            try:
                values = json.loads(item[1])
            except Exception:
                values = {}
            settings.append(
                IndicatorSettingsResponse(indicator_key=item[0], values=values).model_dump()
            )
        return {"settings": settings}
    finally:
        db.close()


@router.put("/{indicator_key}")
def save_indicator_settings(
    indicator_key: str,
    req: IndicatorSettingsRequest,
    authorization: str = Header(None)
):
    key = _validate_key(indicator_key)
    values = validate_input_values(req.values)
    db, row = require_user(authorization)
    try:
        db.execute(
            text("""
                INSERT INTO indicator_settings (user_id, indicator_key, values_json)
                VALUES (:user_id, :indicator_key, :values_json)
                ON DUPLICATE KEY UPDATE values_json = :values_json
            """),
            {"user_id": row[0], "indicator_key": key, "values_json": json.dumps(values)}
        )
        db.commit()
        return IndicatorSettingsResponse(indicator_key=key, values=values)
    finally:
        db.close()


@router.delete("/{indicator_key}")
def reset_indicator_settings(indicator_key: str, authorization: str = Header(None)):
    key = _validate_key(indicator_key)
    db, row = require_user(authorization)
    try:
        db.execute(
            text("""
                DELETE FROM indicator_settings
                WHERE user_id = :user_id AND indicator_key = :indicator_key
            """),
            {"user_id": row[0], "indicator_key": key}
        )
        db.commit()
        return {"detail": "Indicator settings reset"}
    finally:
        db.close()
