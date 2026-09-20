from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE backtest_history
            ADD COLUMN broker_id INT NOT NULL DEFAULT 0 AFTER account_id,
            ADD COLUMN broker_name VARCHAR(100) NOT NULL DEFAULT '' AFTER broker_id,
            ADD COLUMN account_name VARCHAR(100) NOT NULL DEFAULT '' AFTER broker_name
    """))
    conn.execute(text("""
        ALTER TABLE backtest_sessions
            ADD COLUMN broker_id INT NOT NULL DEFAULT 0 AFTER bridge_id,
            ADD COLUMN broker_name VARCHAR(100) NOT NULL DEFAULT '' AFTER broker_id,
            ADD COLUMN account_name VARCHAR(100) NOT NULL DEFAULT '' AFTER broker_name
    """))
    conn.execute(text("""
        UPDATE backtest_history h
        JOIN broker_accounts a ON a.id = h.account_id
        JOIN brokers b ON b.id = a.broker_id
        SET h.broker_id = b.id, h.broker_name = b.name, h.account_name = a.name
    """))
    conn.execute(text("""
        UPDATE backtest_sessions s
        JOIN broker_accounts a ON a.id = s.account_id
        JOIN brokers b ON b.id = a.broker_id
        SET s.broker_id = b.id, s.broker_name = b.name, s.account_name = a.name
    """))
    conn.commit()
