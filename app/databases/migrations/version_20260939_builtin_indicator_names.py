from sqlalchemy import text


def upgrade(conn):
    rows = conn.execute(text("""
        SELECT id, user_id, name FROM indicators
        WHERE LOWER(name) IN ('ema', 'doubleema', 'double ema')
        ORDER BY id
    """)).fetchall()

    for row in rows:
        taken = {
            item[0].lower() for item in conn.execute(
                text("SELECT name FROM indicators WHERE user_id = :user_id"),
                {"user_id": row[1]}
            ).fetchall()
        }
        n = 2
        candidate = f"{row[2]} {n}"
        while candidate.lower() in taken:
            n += 1
            candidate = f"{row[2]} {n}"
        taken.add(candidate.lower())
        conn.execute(
            text("UPDATE indicators SET name = :name WHERE id = :id"),
            {"name": candidate, "id": row[0]}
        )

    conn.commit()
