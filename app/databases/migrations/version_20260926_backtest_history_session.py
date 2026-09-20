from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE backtest_history
            ADD COLUMN session_number INT NOT NULL DEFAULT 0 AFTER start_date
    """))
    conn.execute(text("""
        UPDATE backtest_history h
        SET session_number = (
            SELECT COUNT(*) FROM (
                SELECT id, user_id FROM backtest_history
            ) h2
            WHERE h2.user_id = h.user_id AND h2.id <= h.id
        )
    """))
    conn.commit()
