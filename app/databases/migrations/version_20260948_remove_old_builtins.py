from sqlalchemy import text


def upgrade(conn):
    rows = conn.execute(text(
        "SELECT id FROM indicators WHERE builtin IS NOT NULL AND builtin <> 'breakout'"
    )).fetchall()
    ids = [row[0] for row in rows]

    if ids:
        params = {f"id{index}": value for index, value in enumerate(ids)}
        placeholders = ", ".join(f":id{index}" for index in range(len(ids)))
        conn.execute(
            text(f"""
                DELETE FROM cron_job_runs
                WHERE job_id IN (
                    SELECT id FROM cron_jobs WHERE indicator_id IN ({placeholders})
                )
            """),
            params
        )
        conn.execute(
            text(f"DELETE FROM cron_jobs WHERE indicator_id IN ({placeholders})"),
            params
        )
        conn.execute(
            text(f"DELETE FROM indicator_files WHERE indicator_id IN ({placeholders})"),
            params
        )
        for indicator_id in ids:
            conn.execute(
                text("DELETE FROM indicator_settings WHERE indicator_key = :key"),
                {"key": f"custom:{indicator_id}"}
            )
        conn.execute(
            text(f"DELETE FROM indicators WHERE id IN ({placeholders})"),
            params
        )

    conn.execute(text("""
        DELETE FROM indicator_settings
        WHERE indicator_key NOT LIKE 'custom:%' AND indicator_key <> 'breakout'
    """))
    conn.commit()
