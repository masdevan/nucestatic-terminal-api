from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS backtest_history (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            symbol VARCHAR(30) NOT NULL,
            master_timeframe VARCHAR(10) NOT NULL,
            account_id INT NOT NULL DEFAULT 0,
            bridge_id INT NOT NULL DEFAULT 0,
            start_date VARCHAR(10) NOT NULL,
            initial_balance DECIMAL(20, 8) NOT NULL,
            final_balance DECIMAL(20, 8) NOT NULL,
            orders LONGTEXT NOT NULL,
            first_trade_at DATETIME NULL,
            last_trade_at DATETIME NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_backtest_history_user (user_id)
        )
    """))
    conn.commit()
