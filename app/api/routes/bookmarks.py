from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text
from app.api.models.bookmark import BookmarkCreateRequest, BookmarkResponse
from app.api.controllers.auth import require_user

router = APIRouter()


@router.get("")
def list_bookmarks(
    limit: int = Query(25, ge=1, le=1000),
    page: int = Query(1, ge=1),
    authorization: str = Header(None)
):
    db, row = require_user(authorization)
    try:
        total = db.execute(
            text("SELECT COUNT(*) FROM bookmarks WHERE user_id = :user_id"),
            {"user_id": row[0]}
        ).scalar()
        rows = db.execute(
            text("SELECT id, symbol, server, bridge_id FROM bookmarks WHERE user_id = :user_id ORDER BY id LIMIT :limit OFFSET :offset"),
            {"user_id": row[0], "limit": limit, "offset": (page - 1) * limit}
        ).fetchall()
        total_pages = (total + limit - 1) // limit if total > 0 else 1
        return {
            "bookmarks": [BookmarkResponse(id=r[0], symbol=r[1], server=r[2], bridge_id=r[3]).model_dump() for r in rows],
            "total": total,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
                "has_next": page * limit < total,
                "has_prev": page > 1
            }
        }
    finally:
        db.close()


@router.post("", response_model=BookmarkResponse)
def create_bookmark(req: BookmarkCreateRequest, authorization: str = Header(None)):
    symbol = req.symbol.strip()
    server = req.server.strip()
    bridge_id = req.bridge_id or 0
    if not symbol or len(symbol) > 50 or not server or len(server) > 50:
        raise HTTPException(status_code=422, detail="symbol and server must be 1-50 characters")

    db, row = require_user(authorization)
    try:
        db.execute(
            text("""
                INSERT INTO bookmarks (user_id, symbol, server, bridge_id)
                VALUES (:user_id, :symbol, :server, :bridge_id)
                ON DUPLICATE KEY UPDATE server = :server
            """),
            {"user_id": row[0], "symbol": symbol, "server": server, "bridge_id": bridge_id}
        )
        db.commit()
        result = db.execute(
            text("""
                SELECT id, symbol, server, bridge_id FROM bookmarks
                WHERE user_id = :user_id AND symbol = :symbol AND bridge_id = :bridge_id
            """),
            {"user_id": row[0], "symbol": symbol, "bridge_id": bridge_id}
        ).fetchone()
        return BookmarkResponse(id=result[0], symbol=result[1], server=result[2], bridge_id=result[3])
    finally:
        db.close()


@router.delete("/{symbol}")
def delete_bookmark(symbol: str, bridge_id: int = Query(0), authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        result = db.execute(
            text("""
                DELETE FROM bookmarks
                WHERE user_id = :user_id AND symbol = :symbol AND bridge_id = :bridge_id
            """),
            {"user_id": row[0], "symbol": symbol.strip(), "bridge_id": bridge_id}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Bookmark not found")
        db.commit()
        return {"detail": "Bookmark deleted"}
    finally:
        db.close()