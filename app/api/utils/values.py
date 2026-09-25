import json
import math
import re
from typing import Any
from fastapi import HTTPException

VALUE_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,49}$")
MAX_ENTRIES = 50
MAX_STRING = 2000
MAX_LIST = 50
MAX_JSON = 20_000


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


def validate_input_values(values: Any) -> dict[str, Any]:
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
