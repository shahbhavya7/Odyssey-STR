"""Data-access layer: save / get / list tickets through the ORM.

Every function takes a Session as its first argument so the caller owns the
transaction. Uses the ORM exclusively — no raw SQL string building — which
parameterizes all queries and keeps us safe from SQL injection.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ticket
from app.router_service import route_ticket

# Columns we accept from a route_ticket() dict. Unexpected keys are ignored.
_TICKET_FIELDS = (
    "raw_ticket",
    "category",
    "priority",
    "assigned_team",
    "reasoning",
    "confidence",
    "needs_human_review",
    "engine",
    "prompt_version",
    "processing_ms",
    "error",
)


def save_ticket(db: Session, result: dict) -> Ticket:
    """Persist a route_ticket() result dict as a new row and return it.

    Reads only known keys from the dict; any extra keys are ignored. Commits and
    refreshes so the returned Ticket has its generated id and created_at.
    """
    ticket = Ticket(**{key: result[key] for key in _TICKET_FIELDS if key in result})
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def get_ticket(db: Session, ticket_id: int) -> Ticket | None:
    """Return the ticket with this id, or None if there is no such row."""
    return db.get(Ticket, ticket_id)


def list_tickets(
    db: Session,
    limit: int = 20,
    offset: int = 0,
    *,
    priority: str | None = None,
    team: str | None = None,
    category: str | None = None,
    needs_review: bool | None = None,
    q: str | None = None,
) -> list[Ticket]:
    """Return recent tickets, newest first, with optional filters.

    All filters are optional and additive; when none are given the behaviour is
    unchanged. Uses ORM filters only (q is a case-insensitive substring match).
    """
    stmt = select(Ticket)
    if priority is not None:
        stmt = stmt.where(Ticket.priority == priority)
    if team is not None:
        stmt = stmt.where(Ticket.assigned_team == team)
    if category is not None:
        stmt = stmt.where(Ticket.category == category)
    if needs_review is not None:
        stmt = stmt.where(Ticket.needs_human_review == needs_review)
    if q:
        stmt = stmt.where(Ticket.raw_ticket.ilike(f"%{q}%"))
    stmt = (
        stmt.order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())


def route_and_save(db: Session, raw_text: str) -> Ticket:
    """Route a raw ticket and persist the result — the one call the API will use.

    route_ticket() always returns a valid dict (a safe fallback even on model
    failure), so whatever it produces — including the error field — is saved.
    """
    result = route_ticket(raw_text)
    return save_ticket(db, result)
