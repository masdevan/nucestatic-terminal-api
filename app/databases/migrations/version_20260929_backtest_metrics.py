from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE backtest_history
            ADD COLUMN metrics LONGTEXT NULL
    """))
    conn.commit()
