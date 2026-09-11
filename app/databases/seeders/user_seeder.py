from sqlalchemy import text
from app.databases.config import SessionLocal
from app.api.utils.security import hash_password


def seed():
    db = SessionLocal()
    try:
        existing = db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": "masdevansugiharta@gmail.com"}
        ).fetchone()

        if existing:
            print("User already exists, skipping.")
            return

        db.execute(
            text("UPDATE users SET email = :email, password = :password WHERE username = 'admin'"),
            {
                "email": "masdevansugiharta@gmail.com",
                "password": hash_password("sugiharta")
            }
        )
        if db.execute(text("SELECT ROW_COUNT() AS n")).scalar() == 0:
            db.execute(
                text("INSERT INTO users (username, email, name, password) VALUES (:username, :email, :name, :password)"),
                {
                    "username": "admin",
                    "email": "masdevansugiharta@gmail.com",
                    "name": "Admin",
                    "password": hash_password("sugiharta")
                }
            )
        db.commit()
        print("User seeded successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()