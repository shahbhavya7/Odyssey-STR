# Phase 2, Explained (for complete beginners)

## a) What Phase 2 does, and why we store to a real database

Until now, a routed ticket was printed and then gone forever. Phase 2 gives the app a
**memory**: every routed ticket is saved as a row in a PostgreSQL database, so it
survives after the program closes. Why bother? Three reasons — **durability** (the
result isn't lost when you shut down), **lookup by id** (you can fetch any past ticket
by its receipt number), and **analytics later** (once tickets pile up, we can count how
many are High priority, which team is busiest, etc.). We talk to the database through an
**ORM**, which also protects us from a whole class of security bugs (explained below).

An everyday analogy: routing a ticket was like reading a form aloud; now we actually
**file the form in a cabinet** so we can pull it out again tomorrow.

## b) Every new file, explained

| File | What it's for (one line) |
|------|--------------------------|
| `app/models.py` | Describes the shape of the `tickets` table — one class that maps to one table. |
| `app/repository.py` | The save / fetch / list functions — the only place that reads and writes ticket rows. |
| `app/db.py` (extended) | Added `init_db()` to create the table if it doesn't exist yet. |
| `db_check.py` | A script that proves the whole chain works: route → save → fetch → list. |
| `docs/PHASE_2_EXPLAINED.md` | This file — the plain-English tour of Phase 2. |

## c) Every function (and class), explained

### In `app/models.py`

**`Ticket` (a class — the ORM model)**
- **What it is:** A Python class that *maps* to the `tickets` table. Each **column** in
  the table (id, category, priority, …) is one attribute on the class. One saved
  `Ticket` object = one **row** = one filled-in form filed in the cabinet.
- **Why it exists:** So we work with normal Python objects (`ticket.category`) instead of
  writing database commands by hand. The library translates between the two.
- **Key columns:** `id` is the **primary key** — the ticket's unique receipt number, filled
  in automatically and never repeated. `created_at` is stamped by the database itself at
  save time. `human_verdict` is an empty column reserved for a future feature (a human
  review loop) so we don't have to change the table later.

**`Ticket.to_dict(self)`**
- **What it does:** Copies every column into a plain dictionary (with the timestamp as
  readable text), so a row can be turned into JSON for the API or UI later.
- **Input:** none (reads the object's own values). **Output:** a dict.
- **Why it exists:** Web layers speak JSON, not database objects; this is the translator.

### In `app/db.py` (one addition)

**`init_db()`**
- **What it does:** Creates the `tickets` table if it isn't there yet. It first imports the
  models so the database library knows the table exists, then asks it to "create all
  missing tables." Running it again does nothing — that's called **idempotent** (safe to
  repeat), so there's no "table already exists" error on the second run.
- **Input:** none. **Output:** none. **Why it exists:** So a fresh clone of the project can
  build its own table with one call, no manual setup.

### In `app/repository.py`

Every function here takes a `db` **session** as its first argument — a session is one
open conversation with the database (like a phone call you hang up when done). The caller
opens and closes it, so it controls the **transaction** (the all-or-nothing unit of work).

**`save_ticket(db, result)`**
- **What it does:** Takes the dictionary from `route_ticket()`, builds a `Ticket` object
  from the known fields (ignoring any unexpected keys), adds it, and **commits** — which
  actually writes it to disk. Then it refreshes the object so it now carries its new `id`
  and `created_at`.
- **Input:** a session and a route-result dict. **Output:** the saved `Ticket`.
- **Why it exists:** One safe, reusable "write a ticket" function.

**`get_ticket(db, ticket_id)`**
- **What it does:** Looks up one row by its primary key. Returns the `Ticket`, or `None`
  if no ticket has that id.
- **Input:** a session and an id. **Output:** a `Ticket` or `None`.
- **Why it exists:** Fetch any past ticket by its receipt number.

**`list_tickets(db, limit=20, offset=0)`**
- **What it does:** Returns recent tickets, newest first. `limit` caps how many come back;
  `offset` skips ahead (for paging through older ones later).
- **Input:** a session, and optional limit/offset. **Output:** a list of `Ticket` objects.
- **Why it exists:** Show a feed of the latest tickets (and, later, the batch view).

**`route_and_save(db, raw_text)`**
- **What it does:** The convenience combo the API will call in Phase 3 — it routes the raw
  message with `route_ticket()` and immediately saves the result. Because `route_ticket()`
  always returns a valid dict (even a safe fallback when the model fails), whatever it
  returns is stored, including any `error` field.
- **Input:** a session and the raw ticket text. **Output:** the saved `Ticket`.
- **Why it exists:** So the web layer needs just one call to go from text to a stored row.

### In `db_check.py`

**`main()`**
- **What it does:** Runs the six proof steps in order — check the DB is reachable, create
  the table, open a session, route-and-save a ticket (printing its new id and full row),
  fetch it back and assert it matches, list the five most recent, and close the session.
  If the database isn't reachable it prints one clean line and exits instead of dumping a
  scary error trace.
- **Why it exists:** A one-command demonstration that the entire data layer works.

### Why the ORM keeps us safe (SQL injection)

We never build query text by gluing strings together. The ORM turns
`get_ticket(db, 5)` into a **parameterized** query where the value `5` is sent
separately from the command. That means a malicious value can never be mistaken for a
command — which is exactly how **SQL injection** attacks are prevented. Using the ORM for
everything is a deliberate security choice, not just convenience.

## d) Commands we ran, and what success looks like

| Command | What it does | Successful result |
|---------|--------------|-------------------|
| `python db_check.py` | Routes, saves, fetches, and lists a ticket. | Prints a saved row with an `id`, "matches saved row ✔", and a list. |
| `python db_check.py` (again) | Saves a second ticket. | A new, higher `id` appears; no "table exists" error. |
| `psql ticketrouter -c "SELECT id, category, priority, assigned_team, needs_human_review FROM tickets ORDER BY id DESC LIMIT 5;"` | Peeks directly at the table. | The JSON fields appear as real columns, newest first. |
| (stop Postgres) `python db_check.py` | Simulates the DB being down. | "DB not reachable — is Postgres running…", clean exit, no traceback. |

## e) Words you'll hear (mini glossary)

- **ORM (Object–Relational Mapper):** a library that maps database rows to Python objects,
  so you use objects instead of hand-written SQL. Ours is SQLAlchemy.
- **Table:** a grid of data in the database (like one sheet in a spreadsheet). Ours is
  `tickets`.
- **Model:** the Python class that describes a table's shape. Ours is `Ticket`.
- **Column:** one field in the table (e.g. `priority`).
- **Row / record:** one entry in the table — one routed ticket.
- **Primary key:** the column that uniquely identifies each row — the ticket's receipt
  number (`id`). Never repeats.
- **Session:** one open conversation with the database; you close it when finished.
- **Commit:** actually saving the pending changes — like mailing the letter you wrote.
- **Transaction:** an all-or-nothing bundle of changes; a commit makes the whole bundle
  permanent, and if something fails partway, none of it sticks.
- **CRUD:** Create, Read, Update, Delete — the four basic data operations. Phase 2 does
  the Create (`save`) and Read (`get`/`list`) parts.
- **Idempotent:** safe to run more than once with the same effect — like `init_db()`.
- **Migration:** a controlled change to the table's shape over time. We create tables
  directly with `create_all()`, which is right-sized for a two-week project; the "proper"
  grown-up tool for evolving a schema is **Alembic**, which we'd add if this went to
  production.
