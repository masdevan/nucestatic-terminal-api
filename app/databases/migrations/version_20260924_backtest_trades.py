from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE backtest_sessions
            ADD COLUMN account_id INT NOT NULL DEFAULT 0,
            ADD COLUMN balance DECIMAL(20, 8) NOT NULL DEFAULT 0
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS backtest_orders (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            local_id VARCHAR(40) NOT NULL,
            symbol VARCHAR(30) NOT NULL,
            side VARCHAR(4) NOT NULL,
            order_type VARCHAR(6) NOT NULL,
            lots DECIMAL(20, 8) NOT NULL,
            entry_price DECIMAL(20, 8) NOT NULL,
            tp_price DECIMAL(20, 8) NULL,
            sl_price DECIMAL(20, 8) NULL,
            status VARCHAR(8) NOT NULL,
            open_price DECIMAL(20, 8) NULL,
            close_price DECIMAL(20, 8) NULL,
            pnl DECIMAL(20, 8) NULL,
            close_reason VARCHAR(10) NULL,
            opened_at DATETIME NULL,
            closed_at DATETIME NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uniq_backtest_orders_local (user_id, local_id)
        )
    """))
    conn.commit()
