import uuid
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from typing import Any
from app.api.controllers.auth import require_user
from app.api.utils.dry_run import is_dry_run
from app.api.utils.opencode_pump import stream_with_keepalive
from app.api.utils.opencode_stream import emit, open_upstream_generator, resolve_root
from app.api.utils.security import decrypt_api_key

router = APIRouter()


class ChatRequest(BaseModel):
    messages: list
    session_id: str | None = None
    tools: list | None = None
    tool_choice: Any | None = None


@router.post("")
def chat(req: ChatRequest, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        if not req.messages:
            raise HTTPException(status_code=422, detail="Messages required")
        setting = db.execute(
            text("SELECT api_key, model, base_url FROM opencode_settings WHERE user_id = :user_id AND active = 1"),
            {"user_id": row[0]}
        ).fetchone()
        if not setting:
            raise HTTPException(status_code=404, detail="No active API key")
        if is_dry_run():
            return StreamingResponse(
                iter([emit({"choices": [{"index": 0, "delta": {"content": "dry run"}}]}), b"data: [DONE]\n\n"]),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
            )
        session_id = req.session_id.strip() if req.session_id else ""
        if not session_id:
            session_id = uuid.uuid4().hex
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {decrypt_api_key(setting[0])}",
            "User-Agent": "nucestatic-terminal/1.0",
            "x-opencode-session": session_id
        }
        root = resolve_root(setting[2])
        stream = open_upstream_generator(
            root, setting[1], req.messages, headers, req.tools, req.tool_choice
        )
        return StreamingResponse(
            stream_with_keepalive(stream),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )
    finally:
        db.close()
