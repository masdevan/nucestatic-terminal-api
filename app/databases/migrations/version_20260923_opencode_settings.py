from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS opencode_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            api_key VARCHAR(500) NOT NULL,
            model VARCHAR(100) NOT NULL DEFAULT 'big-pickle',
            base_url VARCHAR(255) NOT NULL DEFAULT 'https://opencode.ai/inference/openai',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE INDEX idx_opencode_settings_user (user_id)
        )
    """))
    conn.commit()
