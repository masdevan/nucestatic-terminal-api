from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.opencode_settings import (
    OpenCodeSettingsRequest,
    OpenCodeSettingsItem,
    OpenCodeSettingsUpdate,
)
from app.api.controllers.auth import require_user
from app.api.utils.security import decrypt_api_key, encrypt_api_key

router = APIRouter()


def _mask_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "••••••••"
    return api_key[:4] + "•" * (len(api_key) - 8) + api_key[-4:]


@router.get("", response_model=list[OpenCodeSettingsItem])
def list_settings(authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        user_id = row[0]
        rows = db.execute(
            text("SELECT id, api_key, model, base_url, active FROM opencode_settings WHERE user_id = :user_id ORDER BY id"),
            {"user_id": user_id}
        ).fetchall()
        return [
            OpenCodeSettingsItem(
                id=r[0],
                api_key_masked=_mask_key(decrypt_api_key(r[1])),
                api_key=None,
                model=r[2],
                base_url=r[3],
                active=bool(r[4]),
                has_key=True,
            )
            for r in rows
        ]
    finally:
        db.close()


@router.post("", response_model=OpenCodeSettingsItem)
def create_setting(req: OpenCodeSettingsRequest, authorization: str = Header(None)):
    api_key = req.api_key.strip()
    model = req.model.strip()
    base_url = req.base_url.strip().rstrip("/")

    if not api_key or len(api_key) > 500:
        raise HTTPException(status_code=422, detail="API key must be 1-500 characters")
    if not model or len(model) > 100:
        raise HTTPException(status_code=422, detail="Model must be 1-100 characters")
    if not base_url or len(base_url) > 255:
        raise HTTPException(status_code=422, detail="Base URL must be 1-255 characters")

    db, row = require_user(authorization)
    try:
        user_id = row[0]
        db.execute(
            text("UPDATE opencode_settings SET active = 0 WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        api_key = encrypt_api_key(api_key)
        result = db.execute(
            text("INSERT INTO opencode_settings (user_id, api_key, model, base_url, active) VALUES (:user_id, :api_key, :model, :base_url, 1)"),
            {"user_id": user_id, "api_key": api_key, "model": model, "base_url": base_url}
        )
        db.commit()
        return OpenCodeSettingsItem(
            id=result.lastrowid,
            api_key_masked=_mask_key(api_key),
            model=model,
            base_url=base_url,
            active=True,
            has_key=True,
        )
    finally:
        db.close()


@router.post("/{setting_id}/activate")
def activate_setting(setting_id: int, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        user_id = row[0]
        existing = db.execute(
            text("SELECT id FROM opencode_settings WHERE id = :id AND user_id = :user_id"),
            {"id": setting_id, "user_id": user_id}
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Setting not found")
        db.execute(
            text("UPDATE opencode_settings SET active = 0 WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        db.execute(
            text("UPDATE opencode_settings SET active = 1 WHERE id = :id"),
            {"id": setting_id}
        )
        db.commit()
        return {"detail": "Activated"}
    finally:
        db.close()


@router.patch("/{setting_id}", response_model=OpenCodeSettingsItem)
def update_setting(setting_id: int, req: OpenCodeSettingsUpdate, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        user_id = row[0]
        existing = db.execute(
            text("SELECT id, api_key, model, base_url, active FROM opencode_settings WHERE id = :id AND user_id = :user_id"),
            {"id": setting_id, "user_id": user_id}
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Setting not found")

        model = req.model if req.model is not None else existing[2]
        base_url = req.base_url.strip().rstrip("/") if req.base_url is not None else existing[3]

        if not model or len(model) > 100:
            raise HTTPException(status_code=422, detail="Model must be 1-100 characters")
        if not base_url or len(base_url) > 255:
            raise HTTPException(status_code=422, detail="Base URL must be 1-255 characters")

        db.execute(
            text("UPDATE opencode_settings SET model = :model, base_url = :base_url WHERE id = :id"),
            {"model": model, "base_url": base_url, "id": setting_id}
        )
        db.commit()
        return OpenCodeSettingsItem(
            id=setting_id,
            api_key_masked=_mask_key(decrypt_api_key(existing[1])),
            model=model,
            base_url=base_url,
            active=bool(existing[4]),
            has_key=True,
        )
    finally:
        db.close()


@router.delete("/{setting_id}")
def delete_setting(setting_id: int, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        user_id = row[0]
        existing = db.execute(
            text("SELECT id FROM opencode_settings WHERE id = :id AND user_id = :user_id"),
            {"id": setting_id, "user_id": user_id}
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Setting not found")
        was_active = db.execute(
            text("SELECT active FROM opencode_settings WHERE id = :id"),
            {"id": setting_id}
        ).fetchone()
        db.execute(
            text("DELETE FROM opencode_settings WHERE id = :id"),
            {"id": setting_id}
        )
        if was_active and was_active[0]:
            first = db.execute(
                text("SELECT id FROM opencode_settings WHERE user_id = :user_id ORDER BY id LIMIT 1"),
                {"user_id": user_id}
            ).fetchone()
            if first:
                db.execute(
                    text("UPDATE opencode_settings SET active = 1 WHERE id = :id"),
                    {"id": first[0]}
                )
        db.commit()
        return {"detail": "Setting deleted"}
    finally:
        db.close()
