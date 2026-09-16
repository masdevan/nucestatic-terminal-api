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

router = APIRouter()

MAX_CONTENT = 200_000
MAX_TOTAL = 1_000_000
MAX_FILES = 200
MAX_FOLDERS = 100


def _validate_name(name: str) -> str:
    value = name.strip()
    if not value or len(value) > 100:
        raise HTTPException(status_code=422, detail="name must be 1-100 characters")
    return value


def _validate_folders(folders: list[str]) -> list[str]:
    if len(folders) > MAX_FOLDERS:
        raise HTTPException(status_code=422, detail="too many folders")
    out = []
    for folder in folders:
        path = folder.strip().strip("/")
        if not path or len(path) > 255:
            raise HTTPException(status_code=422, detail="invalid folder path")
        segments = path.split("/")
        if any(segment in ("", ".", "..") for segment in segments):
            raise HTTPException(status_code=422, detail="invalid folder path")
        if path not in out:
            out.append(path)
    return out


def _validate_files(files: list[IndicatorFile]) -> list[IndicatorFile]:
    if not files:
        raise HTTPException(status_code=422, detail="at least one file is required")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=422, detail="too many files")
    out = []
    seen = set()
    total = 0
    for file in files:
        path = file.path.strip().strip("/")
        segments = path.split("/")
        if not path or len(path) > 255 or any(segment in ("", ".", "..") for segment in segments):
            raise HTTPException(status_code=422, detail="invalid file path")
        if not path.endswith(".js"):
            raise HTTPException(status_code=422, detail="only .js files are allowed")
        if path in seen:
            raise HTTPException(status_code=422, detail="duplicate file path")
        seen.add(path)
        if len(file.content) > MAX_CONTENT:
            raise HTTPException(status_code=422, detail="file content is too large")
        total += len(file.content)
        out.append(IndicatorFile(path=path, content=file.content))
    if total > MAX_TOTAL:
        raise HTTPException(status_code=422, detail="indicator is too large")
    return out


def _row_to_response(row, folders, files) -> IndicatorResponse:
    return IndicatorResponse(
        id=row[0],
        name=row[1],
        folders=folders,
        files=files,
        updated_at=str(row[2])
    )


def _files_for(db, indicator_id: int) -> list[IndicatorFile]:
    rows = db.execute(
        text("SELECT path, content FROM indicator_files WHERE indicator_id = :indicator_id ORDER BY path"),
        {"indicator_id": indicator_id}
    ).fetchall()
    return [IndicatorFile(path=r[0], content=r[1]) for r in rows]


def _folders_of(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


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
                _row_to_response(r, _folders_of(r[3]), files_by_indicator.get(r[0], [])).model_dump()
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
    name = _validate_name(req.name)
    folders = _validate_folders(req.folders)
    files = _validate_files(req.files)

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
        return _row_to_response(result, folders, files)
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
            name = _validate_name(req.name)
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
        folders = _folders_of(existing[3])
        if req.folders is not None:
            folders = _validate_folders(req.folders)
        files = _files_for(db, indicator_id)
        if req.files is not None:
            files = _validate_files(req.files)
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
        return _row_to_response(result, folders, files)
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
