from sqlalchemy import text
from app.databases.config import SessionLocal


def seed():
    db = SessionLocal()
    try:
        existing = db.execute(
            text("SELECT id FROM bridge_apis WHERE url = :url"),
            {"url": "https://marketpool.devan.my.id"}
        ).fetchone()
        if existing:
            print("Bridge API already exists, skipping.")
            return

        count = db.execute(text("SELECT COUNT(*) FROM bridge_apis")).scalar()
        db.execute(
            text("INSERT INTO bridge_apis (name, url, active) VALUES (:name, :url, :active)"),
            {"name": "marketpool", "url": "https://marketpool.devan.my.id", "active": 1 if count == 0 else 0}
        )
        db.commit()
        print("Bridge API seeded successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()