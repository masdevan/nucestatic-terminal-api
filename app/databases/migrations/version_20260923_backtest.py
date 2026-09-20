from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS backtest_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            bridge_id INT NOT NULL DEFAULT 0,
            symbol VARCHAR(30) NOT NULL,
            master_timeframe VARCHAR(10) NOT NULL,
            start_date VARCHAR(10) NOT NULL,
            tick_ms BIGINT NOT NULL,
            cursor_time BIGINT NOT NULL,
            end_time BIGINT NULL,
            playing TINYINT(1) NOT NULL DEFAULT 0,
            speed DECIMAL(10, 4) NOT NULL DEFAULT 0.5,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uniq_backtest_sessions_user (user_id)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS backtest_candles (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            bridge_id INT NOT NULL DEFAULT 0,
            symbol VARCHAR(30) NOT NULL,
            timeframe VARCHAR(10) NOT NULL,
            time DATETIME NOT NULL,
            open DECIMAL(20, 8) NOT NULL,
            high DECIMAL(20, 8) NOT NULL,
            low DECIMAL(20, 8) NOT NULL,
            close DECIMAL(20, 8) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uniq_backtest_candles (user_id, bridge_id, symbol, timeframe, time)
        )
    """))
    conn.commit()
