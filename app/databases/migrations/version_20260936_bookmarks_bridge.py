from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE bookmarks
        ADD COLUMN bridge_id INT NULL
    """))
    conn.commit()
