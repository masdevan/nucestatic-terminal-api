from fastapi import APIRouter, Header, HTTPException
import re
from sqlalchemy import text
from app.api.models.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.api.utils.security import (
    create_token,
    hash_password,
    verify_password,
)
from app.api.controllers.auth import require_user
from app.databases.config import SessionLocal

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT id, username, email, name, password FROM users WHERE email = :email"),
            {"email": req.email}
        ).fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_id, username, email, name, hashed = row

        if not verify_password(req.password, hashed):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_token(user_id)
        return LoginResponse(
            token=token,
            user=UserResponse(id=user_id, username=username, email=email, name=name)
        )
    finally:
        db.close()


@router.get("/me", response_model=UserResponse)
def me(authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        user_id, username, email, name, _ = row
        return UserResponse(id=user_id, username=username, email=email, name=name)
    finally:
        db.close()


@router.patch("/me", response_model=UserResponse)
def update_me(req: UpdateProfileRequest, authorization: str = Header(None)):
    username = req.username.strip()
    name = req.name.strip()

    if not username or len(username) > 50:
        raise HTTPException(status_code=422, detail="Username must be 1-50 characters")
    if not re.fullmatch(r"[a-z0-9]+", username):
        raise HTTPException(status_code=422, detail="Username must be lowercase letters and numbers only")
    if not name or len(name) > 100:
        raise HTTPException(status_code=422, detail="Name must be 1-100 characters")

    db, row = require_user(authorization)
    try:
        user_id, _, email, _, _ = row

        existing = db.execute(
            text("SELECT id FROM users WHERE username = :username AND id != :user_id"),
            {"username": username, "user_id": user_id}
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")

        db.execute(
            text("UPDATE users SET username = :username, name = :name WHERE id = :user_id"),
            {"username": username, "name": name, "user_id": user_id}
        )
        db.commit()
        return UserResponse(id=user_id, username=username, email=email, name=name)
    finally:
        db.close()


@router.post("/me/change-password")
def change_password(req: ChangePasswordRequest, authorization: str = Header(None)):
    if len(req.new_password) < 6:
        raise HTTPException(status_code=422, detail="New password must be at least 6 characters")

    db, row = require_user(authorization)
    try:
        user_id, _, _, _, hashed = row

        if not verify_password(req.old_password, hashed):
            raise HTTPException(status_code=401, detail="Old password incorrect")

        db.execute(
            text("UPDATE users SET password = :password WHERE id = :user_id"),
            {"password": hash_password(req.new_password), "user_id": user_id}
        )
        db.commit()
        return {"detail": "Password changed"}
    finally:
        db.close()
