# `repository.py` save, find, and list tickets

**In plain words:** this file is the "data access" layer the only place that reads from and
writes to the `tickets` table. Every function takes a database session as its first argument,
so the caller controls the transaction. Everything goes through the ORM (never raw SQL
strings), which automatically parameterizes queries and keeps us safe from SQL injection.

**Beginner terms:**
- **Session (`db`)** = the open connection/unit of work, created in `db.py`.
- **Commit** = actually save the changes to the database.
- **SQL injection** = an attack where bad input becomes part of a query; the ORM prevents it.

---

## `_TICKET_FIELDS` (a tuple)

- **What it is:** the list of dictionary keys we're willing to copy into a new row. Anything
  extra in the incoming dict is ignored a small safety filter.

## `save_ticket(db, result: dict) -> Ticket`

- **What it does:** takes a `route_ticket()` result dict and saves it as one new row.
- **Step by step:** build a `Ticket` from the known fields → `db.add(...)` → `db.commit()` →
  `db.refresh(...)` (so the returned object has its new `id` and `created_at`).
- **Returns:** the saved `Ticket` (now with an id).

## `get_ticket(db, ticket_id: int) -> Ticket | None`

- **What it does:** fetches one ticket by its id.
- **Returns:** the `Ticket`, or `None` if there's no row with that id (caller turns `None`
  into a 404).

## `find_ticket_by_text(db, raw_text: str) -> Ticket | None`

- **What it does:** looks for an existing ticket whose original text matches *exactly*.
- **Returns:** the **oldest** matching row (so we always point back to the first one that ever
  held this text), or `None` if there's no match.
- **Why it exists:** it powers the duplicate check if the same message was already routed,
  we reuse that row instead of routing and storing it again.

## `list_tickets(db, limit, offset, *, priority, team, category, needs_review, q) -> list[Ticket]`

- **What it does:** returns recent tickets, newest first, with optional filters.
- **Inputs (all filters optional):**
  - `limit` / `offset` paging (how many, and where to start).
  - `priority` / `team` / `category` match exact values.
  - `needs_review` only flagged (or only not-flagged) tickets.
  - `q` case-insensitive substring search inside the message text.
- **Returns:** a list of `Ticket` rows. If you pass no filters, you just get the latest ones.
- **Note:** filters are *additive* passing several narrows the results (AND, not OR).

## `route_and_save(db, raw_text: str) -> tuple[Ticket, bool]`

- **What it does:** the one call the API uses route a message and store it, *with a
  duplicate check first.*
- **Step by step:**
  1. Look for an exact duplicate via `find_ticket_by_text`.
  2. If found → return `(existing_row, True)` no second model call, no new row.
  3. If new → run `route_ticket(...)`, save it, return `(new_row, False)`.
- **Returns:** a pair `(ticket, is_duplicate)` so the caller can tell a fresh insert from a
  reused one.
- **Why the pair:** `route_ticket()` always returns a valid dict (even a safe fallback), so
  whatever comes out including an error gets saved. The boolean lets the API respond with
  201 (created) vs 200 (duplicate).
