import json
import re
from fastapi import HTTPException
from sqlalchemy import text
from app.api.models.indicator import IndicatorFile, IndicatorResponse

MAX_CONTENT = 200_000
MAX_TOTAL = 1_000_000
MAX_FILES = 200
MAX_FOLDERS = 100
BUILTIN_NAMES = {"breakout"}
BUILTIN_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")


def validate_name(name: str) -> str:
    value = name.strip()
    if not value or len(value) > 100:
        raise HTTPException(status_code=422, detail="name must be 1-100 characters")
    if value.lower() in BUILTIN_NAMES:
        raise HTTPException(status_code=422, detail="name is reserved for a built-in indicator")
    return value


def validate_builtin_key(key: str) -> str:
    value = (key or "").strip()
    if not BUILTIN_KEY_PATTERN.match(value):
        raise HTTPException(status_code=422, detail="invalid builtin key")
    return value


def validate_folders(folders: list[str]) -> list[str]:
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


def validate_files(files: list[IndicatorFile]) -> list[IndicatorFile]:
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


def row_to_response(row, folders, files, builtin=None) -> IndicatorResponse:
    return IndicatorResponse(
        id=row[0],
        name=row[1],
        folders=folders,
        files=files,
        updated_at=str(row[2]),
        builtin=builtin
    )


def files_for(db, indicator_id: int) -> list[IndicatorFile]:
    rows = db.execute(
        text("SELECT path, content FROM indicator_files WHERE indicator_id = :indicator_id ORDER BY path"),
        {"indicator_id": indicator_id}
    ).fetchall()
    return [IndicatorFile(path=r[0], content=r[1]) for r in rows]


def files_by_indicator(db, rows) -> dict:
    if not rows:
        return {}
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
    out: dict = {}
    for file_row in file_rows:
        out.setdefault(file_row[0], []).append(IndicatorFile(path=file_row[1], content=file_row[2]))
    return out


def folders_of(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []
