from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS broker_orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            broker_id INT NOT NULL,
            account_id INT NOT NULL,
            symbol VARCHAR(30) NOT NULL,
            side VARCHAR(4) NOT NULL,
            lots DECIMAL(20, 8) NOT NULL,
            entry_price DECIMAL(20, 8) NOT NULL,
            tp_price DECIMAL(20, 8) NULL,
            sl_price DECIMAL(20, 8) NULL,
            status VARCHAR(6) NOT NULL DEFAULT 'open',
            close_price DECIMAL(20, 8) NULL,
            pnl DECIMAL(20, 8) NULL,
            opened_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            closed_at DATETIME NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_broker_orders_account (account_id, status),
            INDEX idx_broker_orders_broker (broker_id)
        )
    """))
    conn.commit()
