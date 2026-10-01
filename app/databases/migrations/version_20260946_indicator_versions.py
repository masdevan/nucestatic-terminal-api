from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS indicator_versions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            project_key VARCHAR(191) NOT NULL DEFAULT '',
            label VARCHAR(120) NOT NULL DEFAULT '',
            name VARCHAR(100) NOT NULL DEFAULT '',
            folders TEXT NOT NULL,
            files MEDIUMTEXT NOT NULL,
            file_count INT NOT NULL DEFAULT 0,
            content_hash CHAR(64) NOT NULL,
            additions INT NOT NULL DEFAULT 0,
            deletions INT NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_indicator_versions_user_project (user_id, project_key, id)
        )
    """))
    conn.commit()
