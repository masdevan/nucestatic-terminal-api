from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cron_jobs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            indicator_id INT NOT NULL,
            bridge_id INT NOT NULL,
            symbol VARCHAR(30) NOT NULL,
            timeframe VARCHAR(10) NOT NULL,
            interval_seconds INT NOT NULL,
            webhook_url VARCHAR(255) NULL,
            params_json LONGTEXT NULL,
            enabled TINYINT(1) NOT NULL DEFAULT 1,
            last_run_at DATETIME NULL,
            last_alert_at DATETIME NULL,
            last_candle_time VARCHAR(20) NULL,
            last_error VARCHAR(255) NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uniq_cron_job (user_id, indicator_id, bridge_id, symbol, timeframe),
            INDEX idx_cron_due (enabled, last_run_at)
        )
    """))
    conn.commit()
