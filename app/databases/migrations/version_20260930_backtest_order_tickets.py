import random
from sqlalchemy import text


def _new_ticket(used: set) -> int:
    while True:
        ticket = random.randint(10000000000, 99999999999)
        if ticket not in used:
            return ticket


def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE backtest_orders
            ADD COLUMN ticket BIGINT NOT NULL DEFAULT 0
    """))
    rows = conn.execute(text("SELECT id, user_id FROM backtest_orders ORDER BY id")).fetchall()
    used = {}
    for row in rows:
        user_tickets = used.setdefault(row[1], set())
        ticket = _new_ticket(user_tickets)
        user_tickets.add(ticket)
        conn.execute(
            text("UPDATE backtest_orders SET ticket = :ticket WHERE id = :id"),
            {"ticket": ticket, "id": row[0]}
        )
    conn.execute(text("""
        ALTER TABLE backtest_orders
            ADD UNIQUE KEY uq_backtest_orders_ticket (user_id, ticket)
    """))
    conn.commit()
