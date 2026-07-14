"""SQLAlchemy setup: engine, sessions, and a connectivity check.

Table models come in Phase 2 — this file only wires up the plumbing.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Single engine/pool, reused for the app lifetime. The engine owns a connection
# POOL; every request borrows a connection from it via a session and returns it.
# We never open ad-hoc engines/connections elsewhere.
# SSL is intentionally configured in DATABASE_URL, so local Postgres and Neon
# use the same code path (Neon URLs include ?sslmode=require). pool_pre_ping checks
# a borrowed connection is alive (auto-recovers after the DB restarts);
# pool_recycle avoids stale connections on idle-suspending hosts like Neon.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=300,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Parent class all ORM table models will inherit from (Phase 2)."""


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and always close it afterwards.

    Used as a FastAPI dependency in Phase 3 so every request gets its own
    session and never leaks a connection.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ping_db() -> bool:
    """Check the database is reachable. Returns True/False, never raises.

    Borrows a connection from the shared pool (pool_pre_ping revalidates it), so a
    True here means the pool can currently serve requests.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def verify_db() -> tuple[bool, str]:
    """One-shot connectivity check for startup. Returns (ok, message). Never raises.

    Runs SELECT 1 against the shared pool. On success returns (True, "connected");
    on failure returns (False, "<ErrorType>: <short reason>") so startup can log a
    clear line and decide whether to continue.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:  # noqa: BLE001 - report, never raise at startup
        return False, f"{type(exc).__name__}: {exc}"[:200]


def init_db() -> None:
    """Create any missing tables. Idempotent — safe to call repeatedly.

    Imports app.models so the ORM models are registered on Base before
    create_all runs. Never drops or alters existing tables.
    """
    import app.models  # noqa: F401  (registers Ticket on Base.metadata)

    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    if ping_db():
        print("Database connection OK.")
    else:
        print("Database connection FAILED — is Postgres running and DATABASE_URL correct?")
