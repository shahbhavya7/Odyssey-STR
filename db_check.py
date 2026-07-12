"""End-to-end proof for Phase 2: route -> save -> fetch -> list.

Run with Postgres and Ollama up:  python db_check.py
If the database is unreachable it prints a clean message and exits (no traceback).
"""

import json
import sys

from app.db import SessionLocal, init_db, ping_db
from app.repository import get_ticket, list_tickets, route_and_save


def main() -> None:
    """Route and save a ticket, read it back, and list recent rows."""
    if not ping_db():
        print("DB not reachable — is Postgres running and is DATABASE_URL correct?")
        sys.exit(1)

    print("Step 1: init_db() — create tables if missing ...")
    init_db()

    print("Step 2: open a session ...")
    db = SessionLocal()
    try:
        print("Step 3: route + save a ticket ...")
        ticket = route_and_save(db, "I was charged twice, refund please")
        print(f"  saved id = {ticket.id}")
        print("  row: " + json.dumps(ticket.to_dict(), indent=2, ensure_ascii=False))

        print(f"Step 4: fetch id {ticket.id} back ...")
        fetched = get_ticket(db, ticket.id)
        assert fetched is not None, "get_ticket returned None for a just-saved id"
        assert fetched.id == ticket.id
        assert fetched.category == ticket.category
        print(f"  fetched id {fetched.id} — matches saved row ✔")

        print("Step 5: list recent tickets (newest first) ...")
        rows = list_tickets(db, limit=5)
        print(f"  {len(rows)} row(s): " + ", ".join(
            f"#{r.id} {r.category}" for r in rows
        ))
    finally:
        print("Step 6: close the session.")
        db.close()

    print("\nPhase 2 check complete.")


if __name__ == "__main__":
    main()
