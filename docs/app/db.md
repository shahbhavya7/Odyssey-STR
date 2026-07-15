# `db.py` the database plumbing

**In plain words:** this file sets up the connection to PostgreSQL. It doesn't know about
*tickets* or any table it just builds the pipe to the database and hands out short-lived
"sessions" (a session = one open conversation with the DB). Think of it as the water main;
the actual table lives in `models.py`.

**Key terms (beginner):**
- **Engine** = the connection factory to the database (created once, reused).
- **Session** = one unit of work: you open it, do some reads/writes, then close it.
- **ORM** = "Object–Relational Mapping": lets us work with Python objects instead of
  writing raw SQL strings.

---

## `engine = create_engine(...)`

- **What it is:** the one connection pool to Postgres, built from `settings.database_url`.
- **The two options passed in:**
  - `pool_pre_ping=True` before reusing a connection, quickly check it's still alive
    (stops "server closed the connection" errors after idle time).
  - `pool_recycle=300` throw away and remake connections older than 5 minutes.
- **Note:** SSL is set inside the URL itself, so **the same code works for local Postgres
  and cloud Neon** no branching.

## `SessionLocal = sessionmaker(...)`

- **What it is:** a factory. Call `SessionLocal()` and you get a fresh session.
- **The settings:** `autoflush=False, autocommit=False` nothing is written to the DB until
  *you* explicitly `commit()`. This keeps writes predictable.

## `class Base(DeclarativeBase)`

- **What it is:** the empty parent class that every table model inherits from.
- **Why it matters:** SQLAlchemy uses `Base` to keep a registry of all tables. `models.py`
  says `class Ticket(Base)`, and that's how the DB learns the table exists.

## `get_db() -> Generator[Session, ...]`

- **What it does:** opens a session, hands it to whoever asked (`yield`), and no matter
  what happens **always closes it** afterward (the `finally` block).
- **Where it's used:** FastAPI calls this for every web request via `Depends(get_db)`, so
  each request gets its own session and no connection ever leaks.
- **The `yield` bit:** this is a generator. It gives out the session, pauses, and resumes to
  run the cleanup once the request is done.

## `ping_db() -> bool`

- **What it does:** runs a trivial `SELECT 1` to check the database is reachable.
- **Returns:** `True` if it worked, `False` if anything went wrong. **It never raises** —
  so the health check can safely report "DB down" instead of crashing.

## `init_db() -> None`

- **What it does:** creates any tables that don't exist yet. Safe to run every startup
  (it never drops or changes existing tables).
- **The sneaky important line:** `import app.models` importing the models file is what
  *registers* the `Ticket` table on `Base` so `create_all` actually knows to make it.

## `if __name__ == "__main__":` block

- **What it does:** lets you run `python app/db.py` directly to test the connection. Prints
  "Database connection OK." or a friendly failure message. Handy for debugging setup.
