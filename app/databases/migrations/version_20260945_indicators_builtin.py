from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE indicators
            ADD COLUMN builtin VARCHAR(100) NULL,
            ADD UNIQUE KEY uq_indicators_user_builtin (user_id, builtin)
    """))
    conn.commit()
