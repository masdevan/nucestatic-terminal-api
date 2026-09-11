import os
import bcrypt
import jwt
from datetime import datetime, timedelta


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: int) -> str:
    secret = os.getenv("JWT_SECRET", "")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    expiration = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(hours=expiration)
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str) -> dict | None:
    secret = os.getenv("JWT_SECRET", "")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")

    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.PyJWTError:
        return None
