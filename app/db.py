"""SQLAlchemy setup: engine, sessions, and a connectivity check.

Table models come in Phase 2 — this file only wires up the plumbing.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)

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
    """Check the database is reachable. Returns True/False, never raises."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


if __name__ == "__main__":
    if ping_db():
        print("Database connection OK.")
    else:
        print("Database connection FAILED — is Postgres running and DATABASE_URL correct?")
