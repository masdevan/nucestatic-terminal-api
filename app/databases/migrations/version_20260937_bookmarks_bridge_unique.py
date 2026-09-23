from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("UPDATE bookmarks SET bridge_id = 0 WHERE bridge_id IS NULL"))
    conn.execute(text("ALTER TABLE bookmarks MODIFY bridge_id INT NOT NULL DEFAULT 0"))
    conn.execute(text("ALTER TABLE bookmarks DROP INDEX uq_bookmark"))
    conn.execute(text("ALTER TABLE bookmarks ADD UNIQUE KEY uq_bookmark (user_id, symbol, bridge_id)"))
    conn.commit()
