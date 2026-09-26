from fastapi import HTTPException
from sqlalchemy import text
from app.api.utils.dry_run import is_dry_run
from app.api.utils.security import decode_token
from app.databases.config import DryRunSession, SessionLocal, engine


def require_user(authorization: str | None):
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = DryRunSession(bind=engine) if is_dry_run() else SessionLocal()
    row = db.execute(
        text("SELECT id, username, email, name, password FROM users WHERE id = :user_id"),
        {"user_id": int(payload["sub"])}
    ).fetchone()

    if not row:
        db.close()
        raise HTTPException(status_code=401, detail="User not found")

    return db, row