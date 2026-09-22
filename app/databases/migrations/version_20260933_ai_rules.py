from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS ai_rules (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            text VARCHAR(500) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_ai_rules_user (user_id, id)
        )
    """))
    conn.commit()
