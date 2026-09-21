from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE backtest_sessions
            ADD COLUMN provider VARCHAR(100) NOT NULL DEFAULT '' AFTER symbol
    """))
    conn.commit()
