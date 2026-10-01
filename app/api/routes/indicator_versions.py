import difflib
import hashlib
import json
from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text
from app.api.controllers.auth import require_user
from app.api.models.indicator import IndicatorFile
from app.api.models.indicator_version import (
    IndicatorVersionCreateRequest,
    IndicatorVersionDetail,
    IndicatorVersionMeta,
)
from app.api.routes.indicator_shared import folders_of, validate_files, validate_folders

router = APIRouter()

MAX_VERSIONS = 50
TIME_FMT = "%Y-%m-%d %H:%i:%s"
META_COLUMNS = "id, label, name, file_count, additions, deletions, DATE_FORMAT(created_at, :fmt)"


def _meta(row) -> IndicatorVersionMeta:
    return IndicatorVersionMeta(
        id=row[0],
        label=row[1],
        name=row[2],
        file_count=row[3],
        additions=row[4],
        deletions=row[5],
        created_at=row[6],
    )


def _files_from_json(raw: str | None) -> list[IndicatorFile]:
    try:
        parsed = json.loads(raw or "[]")
    except ValueError:
        return []
    if not isinstance(parsed, list):
        return []
    files = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        content = item.get("content")
        if isinstance(path, str) and isinstance(content, str):
            files.append(IndicatorFile(path=path, content=content))
    return files


def _line_stats(before: list[IndicatorFile], after: list[IndicatorFile]) -> tuple[int, int]:
    before_map = {file.path: file.content.splitlines() for file in before}
    after_map = {file.path: file.content.splitlines() for file in after}
    additions = 0
    deletions = 0
    for path in set(before_map) | set(after_map):
        matcher = difflib.SequenceMatcher(
            a=before_map.get(path, []),
            b=after_map.get(path, []),
            autojunk=False,
        )
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ("replace", "delete"):
                deletions += i2 - i1
            if tag in ("replace", "insert"):
                additions += j2 - j1
    return additions, deletions


@router.get("", response_model=list[IndicatorVersionMeta])
def list_versions(
    session: int = Query(...),
    limit: int = Query(50, ge=1, le=100),
    authorization: str = Header(None),
):
    db, row = require_user(authorization)
    try:
        rows = db.execute(
            text(f"""
                SELECT {META_COLUMNS}
                FROM indicator_versions
                WHERE user_id = :user_id AND session_id = :session
                ORDER BY id DESC
                LIMIT :limit
            """),
            {
                "user_id": row[0],
                "session": session,
                "limit": limit,
                "fmt": TIME_FMT,
            },
        ).fetchall()
        return [_meta(r) for r in rows]
    finally:
        db.close()


@router.get("/{version_id}", response_model=IndicatorVersionDetail)
def get_version(version_id: int, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        found = db.execute(
            text("""
                SELECT id, project_key, label, name, folders, files, additions, deletions,
                       DATE_FORMAT(created_at, :fmt)
                FROM indicator_versions WHERE id = :version_id AND user_id = :user_id
            """),
            {"version_id": version_id, "user_id": row[0], "fmt": TIME_FMT},
        ).fetchone()
        if not found:
            raise HTTPException(status_code=404, detail="Version not found")
        return IndicatorVersionDetail(
            id=found[0],
            project_key=found[1],
            label=found[2],
            name=found[3],
            folders=folders_of(found[4]),
            files=_files_from_json(found[5]),
            additions=found[6],
            deletions=found[7],
            created_at=found[8],
        )
    finally:
        db.close()


@router.post("", response_model=IndicatorVersionMeta)
def create_version(req: IndicatorVersionCreateRequest, authorization: str = Header(None)):
    if req.session_id <= 0:
        raise HTTPException(status_code=422, detail="session_id must be a positive number")
    project_key = req.project_key.strip()[:191]
    label = req.label.strip()[:120] or "Change"
    name = req.name.strip()[:100]
    folders = validate_folders(req.folders)
    files = validate_files(req.files)
    payload = json.dumps([file.model_dump() for file in files], sort_keys=True)
    content_hash = hashlib.sha256(payload.encode()).hexdigest()

    db, row = require_user(authorization)
    try:
        latest = db.execute(
            text(f"""
                SELECT {META_COLUMNS}, content_hash, files
                FROM indicator_versions
                WHERE user_id = :user_id AND session_id = :session
                ORDER BY id DESC LIMIT 1
            """),
            {"user_id": row[0], "session": req.session_id, "fmt": TIME_FMT},
        ).fetchone()
        if latest and latest[7] == content_hash:
            return _meta(latest)

        additions, deletions = _line_stats(
            _files_from_json(latest[8]) if latest else [],
            files,
        )
        inserted = db.execute(
            text("""
                INSERT INTO indicator_versions
                    (user_id, project_key, session_id, label, name, folders, files, file_count,
                     content_hash, additions, deletions)
                VALUES
                    (:user_id, :project, :session, :label, :name, :folders, :files, :file_count,
                     :hash, :additions, :deletions)
            """),
            {
                "user_id": row[0],
                "project": project_key,
                "session": req.session_id,
                "label": label,
                "name": name,
                "folders": json.dumps(folders),
                "files": json.dumps([file.model_dump() for file in files]),
                "file_count": len(files),
                "hash": content_hash,
                "additions": additions,
                "deletions": deletions,
            },
        )
        version_id = inserted.lastrowid
        db.execute(
            text("""
                DELETE FROM indicator_versions
                WHERE user_id = :user_id AND session_id = :session AND id NOT IN (
                    SELECT id FROM (
                        SELECT id FROM indicator_versions
                        WHERE user_id = :user_id AND session_id = :session
                        ORDER BY id DESC LIMIT :keep
                    ) AS kept
                )
            """),
            {"user_id": row[0], "session": req.session_id, "keep": MAX_VERSIONS},
        )
        db.commit()
        created = db.execute(
            text(f"SELECT {META_COLUMNS} FROM indicator_versions WHERE id = :version_id"),
            {"version_id": version_id, "fmt": TIME_FMT},
        ).fetchone()
        return _meta(created)
    finally:
        db.close()


@router.delete("/{version_id}")
def delete_version(version_id: int, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        result = db.execute(
            text("DELETE FROM indicator_versions WHERE id = :version_id AND user_id = :user_id"),
            {"version_id": version_id, "user_id": row[0]},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Version not found")
        db.commit()
        return {"detail": "Version deleted"}
    finally:
        db.close()
