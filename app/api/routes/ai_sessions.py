import json
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.ai_session import (
    AiSessionCreateRequest,
    AiSessionDetail,
    AiSessionMeta,
    AiSessionSaveRequest,
)
from app.api.controllers.auth import require_user

router = APIRouter()

MAX_MESSAGES = 200
MAX_JSON_CHARS = 2000000
TIME_FMT = "%Y-%m-%d %H:%i:%s"


def _meta(row) -> AiSessionMeta:
    return AiSessionMeta(id=row[0], title=row[1], message_count=row[2], updated_at=row[3])


def _detail(row) -> AiSessionDetail:
    try:
        messages = json.loads(row[1])
    except ValueError:
        messages = []
    if not isinstance(messages, list):
        messages = []
    try:
        reverted = json.loads(row[4] or '[]')
    except (ValueError, IndexError):
        reverted = []
    if not isinstance(reverted, list):
        reverted = []
    try:
        usage = json.loads(row[5] or 'null')
    except (ValueError, IndexError):
        usage = None
    if not isinstance(usage, dict):
        usage = None
    return AiSessionDetail(id=row[0], title=row[2], messages=messages, reverted=reverted, usage=usage, updated_at=row[3])


@router.get("", response_model=list[AiSessionMeta])
def list_sessions(project: str = "", authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        rows = db.execute(
            text("SELECT id, title, message_count, DATE_FORMAT(updated_at, :fmt) FROM ai_sessions WHERE user_id = :user_id AND project_key = :project ORDER BY updated_at DESC"),
            {"user_id": row[0], "project": project.strip()[:191], "fmt": TIME_FMT}
        ).fetchall()
        return [_meta(r) for r in rows]
    finally:
        db.close()


@router.post("", response_model=AiSessionDetail)
def create_session(req: AiSessionCreateRequest, authorization: str = Header(None)):
    title = req.title.strip()[:120] or "New session"
    db, row = require_user(authorization)
    try:
        result = db.execute(
            text("INSERT INTO ai_sessions (user_id, project_key, title, messages, message_count) VALUES (:user_id, :project, :title, '[]', 0)"),
            {"user_id": row[0], "project": req.project.strip()[:191], "title": title}
        )
        db.commit()
        created = db.execute(
            text("SELECT id, messages, title, DATE_FORMAT(updated_at, :fmt), reverted, `usage` FROM ai_sessions WHERE id = :id"),
            {"id": result.lastrowid, "fmt": TIME_FMT}
        ).fetchone()
        return _detail(created)
    finally:
        db.close()


@router.get("/{session_id}", response_model=AiSessionDetail)
def get_session(session_id: int, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        found = db.execute(
            text("SELECT id, messages, title, DATE_FORMAT(updated_at, :fmt), reverted, `usage` FROM ai_sessions WHERE id = :id AND user_id = :user_id"),
            {"id": session_id, "user_id": row[0], "fmt": TIME_FMT}
        ).fetchone()
        if not found:
            raise HTTPException(status_code=404, detail="Session not found")
        return _detail(found)
    finally:
        db.close()


@router.put("/{session_id}", response_model=AiSessionDetail)
def save_session(session_id: int, req: AiSessionSaveRequest, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        existing = db.execute(
            text("SELECT id FROM ai_sessions WHERE id = :id AND user_id = :user_id"),
            {"id": session_id, "user_id": row[0]}
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Session not found")
        messages_json = None
        message_count = None
        if req.messages is not None:
            if not isinstance(req.messages, list) or len(req.messages) > MAX_MESSAGES:
                raise HTTPException(status_code=422, detail=f"Messages must be a list of at most {MAX_MESSAGES}")
            messages_json = json.dumps(req.messages)
            if len(messages_json) > MAX_JSON_CHARS:
                raise HTTPException(status_code=422, detail="Messages payload too large")
            message_count = len(req.messages)
        reverted_json = None
        if req.reverted is not None:
            if not isinstance(req.reverted, list) or len(req.reverted) > MAX_MESSAGES:
                raise HTTPException(status_code=422, detail=f"Reverted must be a list of at most {MAX_MESSAGES}")
            reverted_json = json.dumps(req.reverted)
            if len(reverted_json) > MAX_JSON_CHARS:
                raise HTTPException(status_code=422, detail="Reverted payload too large")
        title = req.title.strip()[:120] if req.title is not None else None
        if title == "":
            title = None
        if messages_json is not None:
            db.execute(
                text("UPDATE ai_sessions SET messages = :messages, message_count = :count WHERE id = :id"),
                {"messages": messages_json, "count": message_count, "id": session_id}
            )
        if reverted_json is not None:
            db.execute(
                text("UPDATE ai_sessions SET reverted = :reverted WHERE id = :id"),
                {"reverted": reverted_json, "id": session_id}
            )
        if req.usage is not None:
            usage_json = json.dumps(req.usage)
            if len(usage_json) > 4096:
                raise HTTPException(status_code=422, detail="Usage payload too large")
            db.execute(
                text("UPDATE ai_sessions SET `usage` = :usage WHERE id = :id"),
                {"usage": usage_json, "id": session_id}
            )
        if title is not None:
            db.execute(
                text("UPDATE ai_sessions SET title = :title WHERE id = :id"),
                {"title": title, "id": session_id}
            )
        db.commit()
        updated = db.execute(
            text("SELECT id, messages, title, DATE_FORMAT(updated_at, :fmt), reverted, `usage` FROM ai_sessions WHERE id = :id"),
            {"id": session_id, "fmt": TIME_FMT}
        ).fetchone()
        return _detail(updated)
    finally:
        db.close()


@router.delete("/{session_id}")
def delete_session(session_id: int, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        existing = db.execute(
            text("SELECT id FROM ai_sessions WHERE id = :id AND user_id = :user_id"),
            {"id": session_id, "user_id": row[0]}
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Session not found")
        db.execute(
            text("DELETE FROM ai_sessions WHERE id = :id"),
            {"id": session_id}
        )
        db.commit()
        return {"detail": "Session deleted"}
    finally:
        db.close()
