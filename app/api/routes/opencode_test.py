import json
import urllib.error
import urllib.request
import uuid
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.api.controllers.auth import require_user
from app.api.utils.security import decrypt_api_key

router = APIRouter()


class TestRequest(BaseModel):
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    setting_id: int | None = None


@router.post("")
def test_connection(req: TestRequest, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        stored_key = ""
        if req.setting_id is not None:
            found = db.execute(
                text("SELECT api_key FROM opencode_settings WHERE id = :id AND user_id = :user_id"),
                {"id": req.setting_id, "user_id": row[0]}
            ).fetchone()
            if not found:
                raise HTTPException(status_code=404, detail="Setting not found")
            stored_key = decrypt_api_key(found[0])
        api_key = req.api_key.strip() or stored_key
        model = req.model.strip()
        base_url = req.base_url.strip().rstrip("/")
        if not api_key:
            raise HTTPException(status_code=422, detail="API key required")
        if not model:
            raise HTTPException(status_code=422, detail="Model required")
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            raise HTTPException(status_code=422, detail="Base URL must start with http:// or https://")
        root = base_url
        for suffix in ("/v1/chat/completions", "/v1/responses", "/chat/completions", "/responses", "/v1"):
            if root.endswith(suffix):
                root = root[: -len(suffix)]
                break
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "nucestatic-terminal/1.0",
            "x-opencode-session": uuid.uuid4().hex
        }
        chat_data = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5
        }).encode()
        chat_failure = ""
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{root}/v1/chat/completions", data=chat_data, headers=headers), timeout=15) as resp:
                resp.read()
                return {"status": "success"}
        except urllib.error.HTTPError as chat_err:
            if chat_err.code in (401, 402, 403):
                body = chat_err.read().decode(errors="ignore")[:500]
                raise HTTPException(status_code=502, detail=f"Provider {chat_err.code}: {body or chat_err.reason}")
            chat_failure = f"chat={chat_err.code}: {chat_err.read().decode(errors='ignore')[:300] or chat_err.reason}"
        except urllib.error.URLError as chat_url_err:
            chat_failure = f"chat=unreachable: {chat_url_err.reason}"
        responses_data = json.dumps({"model": model, "input": "Hi"}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{root}/v1/responses", data=responses_data, headers=headers), timeout=15) as resp:
                resp.read()
                return {"status": "success"}
        except urllib.error.HTTPError as resp_err:
            body = resp_err.read().decode(errors="ignore")[:500]
            detail = f"Provider responses={resp_err.code}: {body or resp_err.reason}"
            if chat_failure:
                detail = f"Provider {chat_failure} / responses={resp_err.code}: {body or resp_err.reason}"
            raise HTTPException(status_code=502, detail=detail)
        except urllib.error.URLError as url_err:
            detail = f"Cannot reach provider: {url_err.reason}"
            if chat_failure:
                detail = f"Provider {chat_failure} / responses=unreachable: {url_err.reason}"
            raise HTTPException(status_code=502, detail=detail)
    finally:
        db.close()
