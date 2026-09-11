from fastapi import HTTPException
from sqlalchemy import text
from app.api.utils.security import decode_token
from app.databases.config import SessionLocal


def require_user(authorization: str | None):
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = SessionLocal()
    row = db.execute(
        text("SELECT id, username, email, name, password FROM users WHERE id = :user_id"),
        {"user_id": int(payload["sub"])}
    ).fetchone()

    if not row:
        db.close()
        raise HTTPException(status_code=401, detail="User not found")

    return db, row