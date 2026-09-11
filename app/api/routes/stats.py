from fastapi import APIRouter, Header
from sqlalchemy import text
from app.api.controllers.auth import require_user

router = APIRouter()


@router.get("")
def get_stats(authorization: str = Header(None)):
    db, _ = require_user(authorization)
    try:
        bridges = db.execute(text("SELECT COUNT(*) FROM bridge_apis")).scalar()
        users = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
        return {"bridges": bridges, "users": users}
    finally:
        db.close()