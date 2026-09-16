from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS indicators (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            name VARCHAR(100) NOT NULL,
            folders TEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_indicators_user (user_id)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS indicator_files (
            id INT AUTO_INCREMENT PRIMARY KEY,
            indicator_id INT NOT NULL,
            path VARCHAR(255) NOT NULL,
            content MEDIUMTEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_indicator_file (indicator_id, path),
            INDEX idx_indicator_files_indicator (indicator_id)
        )
    """))

    has_scripts = conn.execute(text("SHOW TABLES LIKE 'scripts'")).fetchone() is not None
    if has_scripts:
        rows = conn.execute(text("SELECT id, user_id, name, content FROM scripts")).fetchall()
        for row in rows:
            inserted = conn.execute(
                text("INSERT INTO indicators (user_id, name, folders) VALUES (:user_id, :name, '[]')"),
                {"user_id": row[1], "name": row[2]}
            )
            conn.execute(
                text("""
                    INSERT INTO indicator_files (indicator_id, path, content)
                    VALUES (:indicator_id, 'index.js', :content)
                """),
                {"indicator_id": inserted.lastrowid, "content": row[3]}
            )
        conn.execute(text("DROP TABLE scripts"))

    conn.commit()
