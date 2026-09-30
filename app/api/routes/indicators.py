import json

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text
from app.api.models.indicator import (
    IndicatorBuiltinSyncRequest,
    IndicatorCreateRequest,
    IndicatorResponse,
    IndicatorUpdateRequest
)
from app.api.controllers.auth import require_user
from app.api.routes.indicator_shared import (
    files_by_indicator,
    files_for,
    folders_of,
    row_to_response,
    validate_builtin_key,
    validate_files,
    validate_folders,
    validate_name
)

router = APIRouter()

MAX_BUILTINS = 50


@router.get("")
def list_indicators(
    limit: int = Query(200, ge=1, le=1000),
    page: int = Query(1, ge=1),
    authorization: str = Header(None)
):
    db, row = require_user(authorization)
    try:
        total = db.execute(
            text("SELECT COUNT(*) FROM indicators WHERE user_id = :user_id AND builtin IS NULL"),
            {"user_id": row[0]}
        ).scalar()
        rows = db.execute(
            text("""
                SELECT id, name, updated_at, folders FROM indicators
                WHERE user_id = :user_id AND builtin IS NULL
                ORDER BY id
                LIMIT :limit OFFSET :offset
            """),
            {"user_id": row[0], "limit": limit, "offset": (page - 1) * limit}
        ).fetchall()

        files_map = files_by_indicator(db, rows)

        total_pages = (total + limit - 1) // limit if total > 0 else 1
        return {
            "indicators": [
                row_to_response(r, folders_of(r[3]), files_map.get(r[0], [])).model_dump()
                for r in rows
            ],
            "total": total,
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


@router.get("/builtins", response_model=list[IndicatorResponse])
def list_builtins(authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        rows = db.execute(
            text("""
                SELECT id, name, updated_at, folders, builtin FROM indicators
                WHERE user_id = :user_id AND builtin IS NOT NULL
                ORDER BY id
            """),
            {"user_id": row[0]}
        ).fetchall()
        files_map = files_by_indicator(db, rows)
        return [
            row_to_response(r, folders_of(r[3]), files_map.get(r[0], []), r[4])
            for r in rows
        ]
    finally:
        db.close()


@router.post("/builtins", response_model=list[IndicatorResponse])
def sync_builtins(req: IndicatorBuiltinSyncRequest, authorization: str = Header(None)):
    if len(req.builtins) > MAX_BUILTINS:
        raise HTTPException(status_code=422, detail="too many builtin indicators")
    items = []
    for item in req.builtins:
        key = validate_builtin_key(item.key)
        name = (item.name or "").strip()
        if not name or len(name) > 100:
            raise HTTPException(status_code=422, detail="builtin name must be 1-100 characters")
        items.append((key, name, validate_files(item.files)))

    db, row = require_user(authorization)
    try:
        responses = []
        for key, name, files in items:
            existing = db.execute(
                text("SELECT id FROM indicators WHERE user_id = :user_id AND builtin = :key"),
                {"user_id": row[0], "key": key}
            ).fetchone()
            if existing is None:
                inserted = db.execute(
                    text("""
                        INSERT INTO indicators (user_id, name, folders, builtin)
                        VALUES (:user_id, :name, '[]', :key)
                    """),
                    {"user_id": row[0], "name": name, "key": key}
                )
                indicator_id = inserted.lastrowid
            else:
                indicator_id = existing[0]
                db.execute(
                    text("""
                        UPDATE indicators SET name = :name
                        WHERE id = :indicator_id AND user_id = :user_id
                    """),
                    {"name": name, "indicator_id": indicator_id, "user_id": row[0]}
                )
                db.execute(
                    text("DELETE FROM indicator_files WHERE indicator_id = :indicator_id"),
                    {"indicator_id": indicator_id}
                )
            for file in files:
                db.execute(
                    text("""
                        INSERT INTO indicator_files (indicator_id, path, content)
                        VALUES (:indicator_id, :path, :content)
                    """),
                    {"indicator_id": indicator_id, "path": file.path, "content": file.content}
                )
            result = db.execute(
                text("""
                    SELECT id, name, updated_at FROM indicators
                    WHERE id = :indicator_id AND user_id = :user_id
                """),
                {"indicator_id": indicator_id, "user_id": row[0]}
            ).fetchone()
            responses.append(row_to_response(result, [], files, key))
        db.commit()
        return responses
    finally:
        db.close()


@router.post("", response_model=IndicatorResponse)
def create_indicator(req: IndicatorCreateRequest, authorization: str = Header(None)):
    name = validate_name(req.name)
    folders = validate_folders(req.folders)
    files = validate_files(req.files)

    db, row = require_user(authorization)
    try:
        clash = db.execute(
            text("SELECT id FROM indicators WHERE user_id = :user_id AND name = :name"),
            {"user_id": row[0], "name": name}
        ).fetchone()
        if clash is not None:
            raise HTTPException(status_code=409, detail="Indicator name already exists")

        inserted = db.execute(
            text("INSERT INTO indicators (user_id, name, folders) VALUES (:user_id, :name, :folders)"),
            {"user_id": row[0], "name": name, "folders": json.dumps(folders)}
        )
        indicator_id = inserted.lastrowid
        for file in files:
            db.execute(
                text("INSERT INTO indicator_files (indicator_id, path, content) VALUES (:indicator_id, :path, :content)"),
                {"indicator_id": indicator_id, "path": file.path, "content": file.content}
            )
        db.commit()
        result = db.execute(
            text("SELECT id, name, updated_at FROM indicators WHERE user_id = :user_id AND id = :indicator_id"),
            {"user_id": row[0], "indicator_id": indicator_id}
        ).fetchone()
        return row_to_response(result, folders, files)
    finally:
        db.close()


@router.patch("/{indicator_id}", response_model=IndicatorResponse)
def update_indicator(
    indicator_id: int,
    req: IndicatorUpdateRequest,
    authorization: str = Header(None)
):
    db, row = require_user(authorization)
    try:
        existing = db.execute(
            text("SELECT id, name, updated_at, folders, builtin FROM indicators WHERE user_id = :user_id AND id = :indicator_id"),
            {"user_id": row[0], "indicator_id": indicator_id}
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Indicator not found")
        if existing[4] is not None:
            raise HTTPException(status_code=403, detail="Built-in indicator is read-only")

        if req.name is not None:
            name = validate_name(req.name)
            clash = db.execute(
                text("""
                    SELECT id FROM indicators
                    WHERE user_id = :user_id AND name = :name AND id <> :indicator_id
                """),
                {"user_id": row[0], "name": name, "indicator_id": indicator_id}
            ).fetchone()
            if clash is not None:
                raise HTTPException(status_code=409, detail="Indicator name already exists")
        else:
            name = existing[1]
        folders = folders_of(existing[3])
        if req.folders is not None:
            folders = validate_folders(req.folders)
        files = files_for(db, indicator_id)
        if req.files is not None:
            files = validate_files(req.files)
            db.execute(
                text("DELETE FROM indicator_files WHERE indicator_id = :indicator_id"),
                {"indicator_id": indicator_id}
            )
            for file in files:
                db.execute(
                    text("INSERT INTO indicator_files (indicator_id, path, content) VALUES (:indicator_id, :path, :content)"),
                    {"indicator_id": indicator_id, "path": file.path, "content": file.content}
                )

        db.execute(
            text("UPDATE indicators SET name = :name, folders = :folders WHERE user_id = :user_id AND id = :indicator_id"),
            {"user_id": row[0], "indicator_id": indicator_id, "name": name, "folders": json.dumps(folders)}
        )
        db.commit()
        result = db.execute(
            text("SELECT id, name, updated_at FROM indicators WHERE user_id = :user_id AND id = :indicator_id"),
            {"user_id": row[0], "indicator_id": indicator_id}
        ).fetchone()
        return row_to_response(result, folders, files)
    finally:
        db.close()


@router.delete("/{indicator_id}")
def delete_indicator(indicator_id: int, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        existing = db.execute(
            text("SELECT builtin FROM indicators WHERE user_id = :user_id AND id = :indicator_id"),
            {"user_id": row[0], "indicator_id": indicator_id}
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Indicator not found")
        if existing[0] is not None:
            raise HTTPException(status_code=403, detail="Built-in indicator is read-only")
        db.execute(
            text("DELETE FROM indicators WHERE user_id = :user_id AND id = :indicator_id"),
            {"user_id": row[0], "indicator_id": indicator_id}
        )
        db.execute(
            text("DELETE FROM indicator_files WHERE indicator_id = :indicator_id"),
            {"indicator_id": indicator_id}
        )
        db.commit()
        return {"detail": "Indicator deleted"}
    finally:
        db.close()
