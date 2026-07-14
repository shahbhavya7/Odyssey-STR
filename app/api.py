"""FastAPI layer: a thin HTTP front door over the routing + storage stack.

Endpoints validate input, call one repository function, and shape the response.
All real logic lives in the layers below (router_service, repository). The DB
session is injected via Depends(get_db) — endpoints never open their own session.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session

from app.api_schemas import HealthOut, TicketCreate, TicketListOut, TicketOut, TriageOut
from app.config import settings
from app.db import engine, get_db, init_db, ping_db, verify_db
from app.repository import get_ticket, list_tickets, route_and_save

# Ensure our startup/shutdown INFO lines are visible even without extra config.
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("ticket_router.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Own the DB connection lifecycle for the whole server lifetime.

    STARTUP: verify connectivity ONCE (fail-fast visibility), ensure tables if
    connected, and record db state on app.state. We START ANYWAY if the DB is down
    so /health still works and the pool can recover later (pool_pre_ping) with no
    restart. SHUTDOWN: dispose the shared pool cleanly.
    """
    app.state.db_kind = "neon" if settings.is_serverless_db else "local"
    ok, reason = verify_db()
    app.state.db_ok = ok
    if ok:
        logger.info("✅ Database connected (pool ready)")
        try:
            init_db()
            logger.info("Tables ensured (init_db complete).")
        except Exception as exc:  # noqa: BLE001 - never block startup on DB
            logger.warning("init_db() failed after connect: %s", exc)
    else:
        logger.warning(
            "⚠️ Database unavailable at startup: %s — API starting anyway; "
            "/health will report db down.",
            reason,
        )

    yield  # ---- application runs, reusing the single pool for every request ----

    engine.dispose()
    logger.info("Database pool disposed.")


app = FastAPI(title="Escalio", version="0.4.0", lifespan=lifespan)

# Permissive CORS so the Phase 4 Streamlit app can call this locally.
# NOTE: lock this down to specific origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/tickets", response_model=TriageOut, status_code=201)
def create_ticket(
    body: TicketCreate, response: Response, db: Session = Depends(get_db)
) -> dict:
    """Triage a raw message; store it only if it is a real ticket.

    Outcomes (the body always carries stored + is_ticket + reasoning):
      - Gibberish / non-ticket -> 200, stored=false, nothing written to the DB.
      - Duplicate real ticket  -> 200, the existing row (no second model call).
      - New real ticket        -> 201, the freshly saved row.

    The LLM failing needs no special handling: route_ticket() returns a valid
    fallback ticket (flagged for review), which is stored with 201. Only a DB
    failure escalates (to the 503 handler above) — never a stack trace.
    """
    outcome = route_and_save(db, body.text)
    if not (outcome["stored"] and not outcome["duplicate"]):
        response.status_code = 200  # rejected or duplicate — nothing new created
    return outcome


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
