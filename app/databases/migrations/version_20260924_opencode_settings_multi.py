from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE opencode_settings
        DROP INDEX idx_opencode_settings_user
    """))
    conn.execute(text("""
        ALTER TABLE opencode_settings
        ADD COLUMN active TINYINT(1) NOT NULL DEFAULT 1
    """))
    conn.execute(text("""
        CREATE UNIQUE INDEX idx_opencode_settings_user_key
        ON opencode_settings (user_id, api_key(191))
    """))
    conn.commit()
