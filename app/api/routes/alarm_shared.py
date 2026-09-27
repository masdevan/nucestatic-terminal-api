import json
import math
import urllib.request
from fastapi import HTTPException
from app.api.models.alarm import AlarmResponse

ENTRY_TYPES = {"buy", "sell"}
ALARM_SOURCES = {"chart", "cron"}
ALARM_COLUMNS = (
    "id, symbol, description, entry_type, entry_price, tp_price, sl_price, timeframe, "
    "is_read, created_at, webhook_url, backtest, source, indicator_name"
)


def source_filter(raw: str | None) -> str | None:
    if raw is None or raw == "":
        return None
    value = raw.strip().lower()
    if value not in ALARM_SOURCES:
        raise HTTPException(status_code=422, detail="source must be chart or cron")
    return value


def price(value: float | None, name: str, required: bool) -> float | None:
    if value is None:
        if required:
            raise HTTPException(status_code=422, detail=f"{name} is required")
        return None
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise HTTPException(status_code=422, detail=f"{name} must be a number greater than 0")
    return float(value)


def row_to_response(r) -> AlarmResponse:
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
        webhook_url=r[10],
        backtest=bool(r[11]),
        source=r[12],
        indicator_name=r[13]
    )


def deliver_webhook(url: str, payload: dict):
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 nucestatic-terminal"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception as err:
        print(f"[webhook] delivery failed: {err}", flush=True)


def webhook_payload(alarm: AlarmResponse) -> dict:
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
        "alarm": alarm.model_dump(mode="json")
    }
