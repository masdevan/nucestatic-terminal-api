from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.bookmark import BookmarkCreateRequest, BookmarkResponse
from app.api.controllers.auth import require_user

router = APIRouter()


@router.get("/", response_model=list[BookmarkResponse])
def list_bookmarks(authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        rows = db.execute(
            text("SELECT id, symbol, server FROM bookmarks WHERE user_id = :user_id ORDER BY id"),
            {"user_id": row[0]}
        ).fetchall()
        return [BookmarkResponse(id=r[0], symbol=r[1], server=r[2]) for r in rows]
    finally:
        db.close()


@router.post("/", response_model=BookmarkResponse)
def create_bookmark(req: BookmarkCreateRequest, authorization: str = Header(None)):
    symbol = req.symbol.strip()
    server = req.server.strip()
    if not symbol or len(symbol) > 50 or not server or len(server) > 50:
        raise HTTPException(status_code=422, detail="symbol and server must be 1-50 characters")

    db, row = require_user(authorization)
    try:
        db.execute(
            text("""
                INSERT INTO bookmarks (user_id, symbol, server)
                VALUES (:user_id, :symbol, :server)
                ON DUPLICATE KEY UPDATE server = :server
            """),
            {"user_id": row[0], "symbol": symbol, "server": server}
        )
        db.commit()
        result = db.execute(
            text("SELECT id, symbol, server FROM bookmarks WHERE user_id = :user_id AND symbol = :symbol"),
            {"user_id": row[0], "symbol": symbol}
        ).fetchone()
        return BookmarkResponse(id=result[0], symbol=result[1], server=result[2])
    finally:
        db.close()


@router.delete("/{symbol}")
def delete_bookmark(symbol: str, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        result = db.execute(
            text("DELETE FROM bookmarks WHERE user_id = :user_id AND symbol = :symbol"),
            {"user_id": row[0], "symbol": symbol.strip()}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Bookmark not found")
        db.commit()
        return {"detail": "Bookmark deleted"}
    finally:
        db.close()