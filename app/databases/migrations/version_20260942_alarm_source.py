from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE alarms
            ADD COLUMN source VARCHAR(10) NOT NULL DEFAULT 'chart'
    """))
    conn.commit()
