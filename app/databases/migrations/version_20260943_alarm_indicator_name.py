from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE alarms
            ADD COLUMN indicator_name VARCHAR(100) NULL
    """))
    conn.commit()
