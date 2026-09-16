from sqlalchemy import text


def upgrade(conn):
    duplicates = conn.execute(text("""
        SELECT user_id, name FROM indicators
        GROUP BY user_id, name
        HAVING COUNT(*) > 1
    """)).fetchall()

    for user_id, name in duplicates:
        rows = conn.execute(
            text("SELECT id FROM indicators WHERE user_id = :user_id AND name = :name ORDER BY id"),
            {"user_id": user_id, "name": name}
        ).fetchall()
        taken = {
            row[0] for row in conn.execute(
                text("SELECT name FROM indicators WHERE user_id = :user_id"),
                {"user_id": user_id}
            ).fetchall()
        }
        for row in rows[1:]:
            n = 2
            candidate = f"{name} {n}"
            while candidate in taken:
                n += 1
                candidate = f"{name} {n}"
            taken.add(candidate)
            conn.execute(
                text("UPDATE indicators SET name = :name WHERE id = :id"),
                {"name": candidate, "id": row[0]}
            )

    has_index = conn.execute(
        text("SHOW INDEX FROM indicators WHERE Key_name = 'uq_indicator_name'")
    ).fetchone() is not None
    if not has_index:
        conn.execute(text("ALTER TABLE indicators ADD UNIQUE KEY uq_indicator_name (user_id, name)"))

    conn.commit()
