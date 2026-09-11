from fastapi import APIRouter, Header, HTTPException, Query
import re
from sqlalchemy import text
from app.api.models.user import CreateUserRequest, UpdateUserRequest, UserResponse
from app.api.utils.security import hash_password
from app.api.controllers.auth import require_user

router = APIRouter()


def _validate_uniqueness(db, username: str, email: str, user_id: int | None = None):
    if not username or len(username) > 50:
        raise HTTPException(status_code=422, detail="Username must be 1-50 characters")
    if not re.fullmatch(r"[a-z0-9]+", username):
        raise HTTPException(status_code=422, detail="Username must be lowercase letters and numbers only")
    if not email or len(email) > 100:
        raise HTTPException(status_code=422, detail="Email must be 1-100 characters")

    existing = db.execute(
        text("SELECT id FROM users WHERE username = :username AND (:user_id IS NULL OR id != :user_id)"),
        {"username": username, "user_id": user_id}
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    existing = db.execute(
        text("SELECT id FROM users WHERE email = :email AND (:user_id IS NULL OR id != :user_id)"),
        {"email": email, "user_id": user_id}
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="Email already taken")


@router.get("/", response_model=list[UserResponse])
def list_users(q: str | None = Query(None), authorization: str = Header(None)):
    db, _ = require_user(authorization)
    try:
        sql = "SELECT id, username, email, name FROM users"
        params = {}
        if q:
            sql += " WHERE username LIKE :q OR email LIKE :q OR name LIKE :q"
            params["q"] = f"%{q.strip()}%"
        sql += " ORDER BY id"
        rows = db.execute(text(sql), params).fetchall()
        return [UserResponse(id=r[0], username=r[1], email=r[2], name=r[3]) for r in rows]
    finally:
        db.close()


@router.post("/", response_model=UserResponse)
def create_user(req: CreateUserRequest, authorization: str = Header(None)):
    if len(req.password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters")

    db, _ = require_user(authorization)
    try:
        _validate_uniqueness(db, req.username.strip(), req.email.strip())

        result = db.execute(
            text("INSERT INTO users (username, email, name, password) VALUES (:username, :email, :name, :password)"),
            {
                "username": req.username.strip(),
                "email": req.email.strip(),
                "name": req.name.strip(),
                "password": hash_password(req.password),
            }
        )
        db.commit()
        new_id = result.lastrowid
        return UserResponse(id=new_id, username=req.username.strip(), email=req.email.strip(), name=req.name.strip())
    finally:
        db.close()


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, req: UpdateUserRequest, authorization: str = Header(None)):
    db, _ = require_user(authorization)
    try:
        row = db.execute(
            text("SELECT id, username, email, name FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        username = req.username.strip()
        email = req.email.strip()
        name = req.name.strip()

        if not name or len(name) > 100:
            raise HTTPException(status_code=422, detail="Name must be 1-100 characters")

        _validate_uniqueness(db, username, email, user_id)

        password_sql = ", password = :password" if req.password else ""
        params = {"username": username, "email": email, "name": name, "user_id": user_id}
        if req.password:
            if len(req.password) < 6:
                raise HTTPException(status_code=422, detail="Password must be at least 6 characters")
            params["password"] = hash_password(req.password)

        db.execute(
            text(f"UPDATE users SET username = :username, email = :email, name = :name{password_sql} WHERE id = :user_id"),
            params
        )
        db.commit()
        return UserResponse(id=user_id, username=username, email=email, name=name)
    finally:
        db.close()


@router.delete("/{user_id}")
def delete_user(user_id: int, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        if row[0] == user_id:
            raise HTTPException(status_code=403, detail="Cannot delete your own account")

        result = db.execute(
            text("DELETE FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        db.commit()
        return {"detail": "User deleted"}
    finally:
        db.close()