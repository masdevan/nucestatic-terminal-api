from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS alarms (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            symbol VARCHAR(50) NOT NULL,
            description TEXT NULL,
            entry_type VARCHAR(4) NOT NULL,
            entry_price DECIMAL(20, 8) NOT NULL,
            tp_price DECIMAL(20, 8) NULL,
            sl_price DECIMAL(20, 8) NULL,
            timeframe VARCHAR(10) NULL,
            is_read TINYINT(1) NOT NULL DEFAULT 0,
            webhook_url VARCHAR(255) NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_alarms_user (user_id)
        )
    """))
    conn.commit()
