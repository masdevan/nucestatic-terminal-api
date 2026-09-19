from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS broker_accounts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            broker_id INT NOT NULL,
            name VARCHAR(100) NOT NULL,
            balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
            leverage INT NOT NULL DEFAULT 100,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_broker_account_name (broker_id, name),
            INDEX idx_broker_accounts_broker (broker_id)
        )
    """))
    conn.commit()
