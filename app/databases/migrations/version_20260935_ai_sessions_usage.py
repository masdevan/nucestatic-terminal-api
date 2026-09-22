from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE ai_sessions
            ADD COLUMN `usage` MEDIUMTEXT NULL
    """))
    conn.commit()
