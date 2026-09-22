from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS ai_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            project_key VARCHAR(191) NOT NULL DEFAULT '',
            title VARCHAR(120) NOT NULL DEFAULT 'New session',
            messages MEDIUMTEXT NOT NULL,
            message_count INT NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_ai_sessions_user_project (user_id, project_key, updated_at)
        )
    """))
    conn.commit()
