import json

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text
from app.api.models.indicator import (
    IndicatorCreateRequest,
    IndicatorFile,
    IndicatorResponse,
    IndicatorUpdateRequest
)
from app.api.controllers.auth import require_user
from app.api.routes.indicator_shared import (
    files_for,
    folders_of,
    row_to_response,
    validate_files,
    validate_folders,
    validate_name
)

router = APIRouter()


@router.get("")
def list_indicators(
    limit: int = Query(200, ge=1, le=1000),
    page: int = Query(1, ge=1),
    authorization: str = Header(None)
):
    db, row = require_user(authorization)
    try:
        total = db.execute(
            text("SELECT COUNT(*) FROM indicators WHERE user_id = :user_id"),
            {"user_id": row[0]}
        ).scalar()
        rows = db.execute(
            text("""
                SELECT id, name, updated_at, folders FROM indicators
                WHERE user_id = :user_id
                ORDER BY id
                LIMIT :limit OFFSET :offset
            """),
            {"user_id": row[0], "limit": limit, "offset": (page - 1) * limit}
        ).fetchall()

        files_by_indicator = {}
        if rows:
            params = {f"id{i}": r[0] for i, r in enumerate(rows)}
            placeholders = ", ".join(f":id{i}" for i in range(len(rows)))
            file_rows = db.execute(
                text(f"""
                    SELECT indicator_id, path, content FROM indicator_files
                    WHERE indicator_id IN ({placeholders})
                    ORDER BY indicator_id, path
                """),
                params
            ).fetchall()
            for file_row in file_rows:
                files_by_indicator.setdefault(file_row[0], []).append(
                    IndicatorFile(path=file_row[1], content=file_row[2])
                )

        total_pages = (total + limit - 1) // limit if total > 0 else 1
        return {
            "indicators": [
                row_to_response(r, folders_of(r[3]), files_by_indicator.get(r[0], [])).model_dump()
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
            text("SELECT id, name, updated_at, folders FROM indicators WHERE user_id = :user_id AND id = :indicator_id"),
            {"user_id": row[0], "indicator_id": indicator_id}
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Indicator not found")

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
        result = db.execute(
            text("DELETE FROM indicators WHERE user_id = :user_id AND id = :indicator_id"),
            {"user_id": row[0], "indicator_id": indicator_id}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Indicator not found")
        db.execute(
            text("DELETE FROM indicator_files WHERE indicator_id = :indicator_id"),
            {"indicator_id": indicator_id}
        )
        db.commit()
        return {"detail": "Indicator deleted"}
    finally:
        db.close()
