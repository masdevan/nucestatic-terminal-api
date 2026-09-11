from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    name: str


class LoginResponse(BaseModel):
    token: str
    user: UserResponse


class CreateUserRequest(BaseModel):
    username: str
    email: str
    name: str
    password: str


class UpdateUserRequest(BaseModel):
    username: str
    email: str
    name: str
    password: str | None = None