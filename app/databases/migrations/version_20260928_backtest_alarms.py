from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE alarms
            ADD COLUMN backtest TINYINT(1) NOT NULL DEFAULT 0
    """))
    conn.execute(text("""
        ALTER TABLE backtest_history
            ADD COLUMN alarm_count INT NOT NULL DEFAULT 0,
            ADD COLUMN alarms LONGTEXT NULL
    """))
    conn.commit()
