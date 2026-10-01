from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE indicator_versions
            ADD COLUMN session_id INT NULL,
            ADD INDEX idx_indicator_versions_user_session (user_id, session_id, id)
    """))
    conn.commit()
