from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS bridge_apis (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            url VARCHAR(255) NOT NULL UNIQUE,
            active TINYINT(1) NOT NULL DEFAULT 0,
            mode VARCHAR(10) NOT NULL DEFAULT 'static',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_bridge_apis_url (url),
            INDEX idx_bridge_apis_active (active)
        )
    """))
    conn.commit()