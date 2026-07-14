"""FastAPI layer: a thin HTTP front door over the routing + storage stack.

Endpoints validate input, call one repository function, and shape the response.
All real logic lives in the layers below (router_service, repository). The DB
session is injected via Depends(get_db) — endpoints never open their own session.
"""

import logging

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session

from app.api_schemas import HealthOut, TicketCreate, TicketListOut, TicketOut
from app.config import settings
from app.db import get_db, init_db, ping_db
from app.repository import get_ticket, list_tickets, route_and_save

logger = logging.getLogger("ticket_router.api")

app = FastAPI(title="Escalio", version="0.3.0")

# Permissive CORS so the Phase 4 Streamlit app can call this locally.
# NOTE: lock this down to specific origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup() -> None:
    """Create tables if possible. If the DB is down, start anyway so /health works."""
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001 - never block startup on DB
        logger.warning("init_db() failed at startup (DB down?): %s", exc)


@app.exception_handler(OperationalError)
@app.exception_handler(InterfaceError)
async def _db_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    """Turn a lost/failed DB connection into a clean 503, never a stack trace."""
    logger.warning("Database unavailable during %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database unavailable. Is Postgres running?"},
    )


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    """Liveness + dependency check. Never raises; reports db_ok even when DB is down."""
    return HealthOut(
        status="ok",
        provider=settings.provider,
        model=settings.active_model,
        db_ok=ping_db(),
        db_kind="neon" if settings.is_serverless_db else "local",
    )


@app.post("/tickets", response_model=TicketOut, status_code=201)
def create_ticket(
    body: TicketCreate, response: Response, db: Session = Depends(get_db)
) -> dict:
    """Route a raw message and save it, returning the full classified row at once.

    De-duplicates on exact text: if this message was already routed, the existing
    row is returned with 200 and duplicate=true (no second model call). Genuinely
    new text is routed and saved with 201.

    The LLM failing needs no special handling here: route_ticket() always returns a
    valid fallback dict, so this still returns 201 with needs_human_review=true and a
    populated error field. Only a DB failure escalates (to the 503 handler above).
    """
    ticket, is_duplicate = route_and_save(db, body.text)
    if is_duplicate:
        response.status_code = 200
    return {**ticket.to_dict(), "duplicate": is_duplicate}


@app.get("/tickets/{ticket_id}", response_model=TicketOut)
def read_ticket(ticket_id: int, db: Session = Depends(get_db)) -> dict:
    """Fetch one ticket by id, or 404 if there is no such ticket."""
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket.to_dict()


@app.get("/tickets", response_model=TicketListOut)
def read_tickets(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    priority: str | None = Query(default=None),
    team: str | None = Query(default=None),
    category: str | None = Query(default=None),
    needs_review: bool | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """List recent tickets (newest first) with count + items.

    All filter params are optional and additive; omitting them keeps the
    original behaviour.
    """
    rows = list_tickets(
        db,
        limit=limit,
        offset=offset,
        priority=priority,
        team=team,
        category=category,
        needs_review=needs_review,
        q=q,
    )
    return {"count": len(rows), "items": [row.to_dict() for row in rows]}
