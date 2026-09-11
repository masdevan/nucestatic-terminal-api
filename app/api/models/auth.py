from pydantic import BaseModel
from app.api.models.user import UserResponse, LoginResponse


class LoginRequest(BaseModel):
    email: str
    password: str


class UpdateProfileRequest(BaseModel):
    username: str
    name: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


__all__ = [
    "LoginRequest",
    "UpdateProfileRequest",
    "ChangePasswordRequest",
    "UserResponse",
    "LoginResponse",
]