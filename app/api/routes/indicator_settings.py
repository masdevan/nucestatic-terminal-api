import json
import math
import re
from typing import Any
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.indicator import IndicatorSettingsRequest, IndicatorSettingsResponse
from app.api.controllers.auth import require_user

router = APIRouter()

KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
VALUE_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,49}$")
MAX_ENTRIES = 50
MAX_STRING = 2000
MAX_LIST = 50
MAX_JSON = 20_000


def _validate_key(key: str) -> str:
    value = key.strip()
    if not KEY_PATTERN.match(value):
        raise HTTPException(status_code=422, detail="Invalid indicator key")
    return value


def _validate_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise HTTPException(status_code=422, detail="Value must be finite")
        return value
    if isinstance(value, str):
        if len(value) > MAX_STRING:
            raise HTTPException(status_code=422, detail="Value too long")
        return value
    if isinstance(value, list):
        if len(value) > MAX_LIST:
            raise HTTPException(status_code=422, detail="List value too long")
        items: list[str] = []
        for item in value:
            if not isinstance(item, str) or len(item) > MAX_STRING:
                raise HTTPException(status_code=422, detail="List items must be short strings")
            items.append(item)
        return items
    raise HTTPException(status_code=422, detail="Unsupported value type")


def _validate_values(values: Any) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise HTTPException(status_code=422, detail="Values must be an object")
    if len(values) > MAX_ENTRIES:
        raise HTTPException(status_code=422, detail="Too many settings entries")
    clean: dict[str, Any] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not VALUE_KEY_PATTERN.match(key):
            raise HTTPException(status_code=422, detail=f"Invalid input key: {key}")
        clean[key] = _validate_value(value)
    if len(json.dumps(clean)) > MAX_JSON:
        raise HTTPException(status_code=422, detail="Settings payload too large")
    return clean


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
    values = _validate_values(req.values)
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
