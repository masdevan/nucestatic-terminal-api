import json
import urllib.request
from fastapi import APIRouter, Header, HTTPException
from app.api.controllers.auth import require_user

router = APIRouter()
MODELS_URL = "https://opencode.ai/zen/go/v1/models"


@router.get("")
def list_models(authorization: str = Header(None)):
    db, _ = require_user(authorization)
    try:
        req = urllib.request.Request(MODELS_URL, headers={"User-Agent": "nucestatic-terminal/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch models")
    finally:
        db.close()
