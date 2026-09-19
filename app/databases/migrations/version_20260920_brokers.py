from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS brokers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            name VARCHAR(100) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_broker_name (user_id, name),
            INDEX idx_brokers_user (user_id)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS broker_pairs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            broker_id INT NOT NULL,
            pair VARCHAR(20) NOT NULL,
            spread_type VARCHAR(6) NOT NULL,
            spread_value DECIMAL(18, 8) NOT NULL,
            lot DECIMAL(18, 8) NOT NULL DEFAULT 0.01,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_broker_pair (broker_id, pair),
            INDEX idx_broker_pairs_broker (broker_id)
        )
    """))
    conn.commit()
