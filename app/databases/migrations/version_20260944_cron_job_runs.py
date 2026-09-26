from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cron_job_runs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            job_id INT NOT NULL,
            user_id INT NOT NULL,
            status VARCHAR(8) NOT NULL DEFAULT 'ok',
            candle_time VARCHAR(20) NULL,
            alarms INT NOT NULL DEFAULT 0,
            duration_ms INT NOT NULL DEFAULT 0,
            error VARCHAR(255) NULL,
            ran_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_cron_job_runs_job (job_id, id)
        )
    """))
    conn.commit()
