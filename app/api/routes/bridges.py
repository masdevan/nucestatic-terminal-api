import json
import urllib.request
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.bridge import BridgeApiRequest, BridgeApiResponse, BridgeApiUpdate, BridgeStatusResponse
from app.api.controllers.auth import require_user

router = APIRouter()
MODES = {"static", "dynamic"}


def _mode(raw: str | None) -> str:
    mode = (raw or "static").strip().lower()
    return mode if mode in MODES else "static"


def _fetch_row(db, bridge_id: int):
    row = db.execute(
        text("SELECT id, name, url, active, mode FROM bridge_apis WHERE id = :bridge_id"),
        {"bridge_id": bridge_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Bridge API not found")
    return row


def _probe(url: str) -> str:
    try:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/api/health",
            headers={"User-Agent": "Mozilla/5.0 nucestatic-terminal"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                return "disconnected"
            body = json.loads(resp.read().decode())
            return "healthy" if body.get("status") == "healthy" else "disconnected"
    except Exception:
        return "disconnected"


@router.get("", response_model=list[BridgeApiResponse])
def list_bridges(authorization: str = Header(None)):
    db, _ = require_user(authorization)
    try:
        rows = db.execute(
            text("SELECT id, name, url, active, mode FROM bridge_apis ORDER BY id")
        ).fetchall()
        return [BridgeApiResponse(id=r[0], name=r[1], url=r[2], active=bool(r[3]), mode=r[4]) for r in rows]
    finally:
        db.close()


@router.post("", response_model=BridgeApiResponse)
def create_bridge(req: BridgeApiRequest, authorization: str = Header(None)):
    name = req.name.strip()
    url = req.url.strip().rstrip("/")
    mode = _mode(req.mode)
    if not name or len(name) > 100:
        raise HTTPException(status_code=422, detail="Name must be 1-100 characters")
    if not url or len(url) > 255:
        raise HTTPException(status_code=422, detail="URL must be 1-255 characters")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="URL must start with http:// or https://")

    db, _ = require_user(authorization)
    try:
        count = db.execute(text("SELECT COUNT(*) FROM bridge_apis")).scalar()
        active = count == 0
        try:
            result = db.execute(
                text("INSERT INTO bridge_apis (name, url, active, mode) VALUES (:name, :url, :active, :mode)"),
                {"name": name, "url": url, "active": 1 if active else 0, "mode": mode}
            )
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=409, detail="URL already exists")
        return BridgeApiResponse(id=result.lastrowid, name=name, url=url, active=active, mode=mode)
    finally:
        db.close()


@router.patch("/{bridge_id}", response_model=BridgeApiResponse)
def update_bridge(bridge_id: int, req: BridgeApiUpdate, authorization: str = Header(None)):
    db, _ = require_user(authorization)
    try:
        row = _fetch_row(db, bridge_id)

        name = req.name.strip() if req.name is not None else row[1]
        url = req.url.strip().rstrip("/") if req.url is not None else row[2]
        mode = req.mode if req.mode is not None else row[4]
        mode = _mode(mode)
        if not name or len(name) > 100:
            raise HTTPException(status_code=422, detail="Name must be 1-100 characters")
        if not url or len(url) > 255:
            raise HTTPException(status_code=422, detail="URL must be 1-255 characters")
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=422, detail="URL must start with http:// or https://")

        active = row[3]
        if req.active is not None:
            active = req.active
            if active:
                db.execute(text("UPDATE bridge_apis SET active = 0"))

        try:
            result = db.execute(
                text("UPDATE bridge_apis SET name = :name, url = :url, active = :active, mode = :mode WHERE id = :bridge_id"),
                {"name": name, "url": url, "active": 1 if active else 0, "mode": mode, "bridge_id": bridge_id}
            )
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=409, detail="URL already exists")

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Bridge API not found")
        return BridgeApiResponse(id=bridge_id, name=name, url=url, active=active, mode=mode)
    finally:
        db.close()


@router.delete("/{bridge_id}")
def delete_bridge(bridge_id: int, authorization: str = Header(None)):
    db, _ = require_user(authorization)
    try:
        _fetch_row(db, bridge_id)
        db.execute(text("DELETE FROM bridge_apis WHERE id = :bridge_id"), {"bridge_id": bridge_id})
        db.commit()
        return {"detail": "Bridge API deleted"}
    finally:
        db.close()


@router.get("/{bridge_id}/status", response_model=BridgeStatusResponse)
def bridge_status(bridge_id: int, authorization: str = Header(None)):
    db, _ = require_user(authorization)
    try:
        row = _fetch_row(db, bridge_id)
        return BridgeStatusResponse(id=bridge_id, status=_probe(row[2]))
    finally:
        db.close()