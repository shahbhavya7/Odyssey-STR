# `api.py` — the web server and its endpoints

**In plain words:** this is the HTTP front door. It's a thin FastAPI app: each endpoint checks
the input, calls *one* function from the layers below, and shapes the reply. No real logic
lives here — routing lives in `router_service`, storage in `repository`. It also makes sure
that when the database is down, users get a clean error instead of a scary stack trace.

**Beginner terms:**
- **Endpoint** = a URL + method (e.g. `POST /tickets`) the server responds to.
- **Dependency (`Depends`)** = something FastAPI supplies automatically per request (here, a
  DB session).
- **Status code** = the number that says how it went (200 OK, 201 Created, 404 Not Found,
  503 Unavailable).

---

## `app = FastAPI(...)` and CORS middleware

- **What it is:** the application object. The `CORSMiddleware` with `allow_origins=["*"]` lets
  the Streamlit UI (a different local port) call this API during development.
- **Note in the code:** this is deliberately permissive for local dev and should be locked
  down to specific origins in production.

## `_on_startup()` — runs once when the server boots

- **What it does:** calls `init_db()` to create tables if needed.
- **The clever bit:** if the database is down, it *logs a warning and starts anyway* — so the
  `/health` endpoint still works and can report the problem, rather than the whole app
  refusing to boot.

## `_db_unavailable_handler(request, exc)` — the safety net

- **What it does:** catches `OperationalError` / `InterfaceError` (a lost or failed DB
  connection) anywhere in the app and turns it into a clean **503** response with the message
  "Database unavailable. Is Postgres running?"
- **Why it matters:** users never see a raw crash; they get a helpful, honest error.

## `GET /health` → `health()`

- **What it does:** a liveness check. Reports status, provider, model, whether the DB is
  reachable, and whether it's local or Neon.
- **Never raises:** even with the DB down it returns `db_ok=false` instead of failing.

## `POST /tickets` → `create_ticket(body, response, db)`

- **What it does:** the main endpoint — route a message and save it, returning the full
  classified row in one call.
- **Inputs:** a `TicketCreate` body (just `text`); the DB session is injected.
- **What it returns:**
  - A **new** ticket → status **201** with `duplicate: false`.
  - An **exact duplicate** → status **200** with `duplicate: true` (reuses the existing row,
    no second model call).
- **Why no special error handling for the model:** `route_ticket()` always returns a valid
  fallback, so a model failure still returns 201 with `needs_human_review=true` and a filled
  `error` field. Only a *database* failure escalates (to the 503 handler above).

## `GET /tickets/{ticket_id}` → `read_ticket(ticket_id, db)`

- **What it does:** fetch one ticket by its id.
- **Returns:** the ticket as JSON, or a **404 "Ticket not found"** if there's no such id.

## `GET /tickets` → `read_tickets(...)`

- **What it does:** list recent tickets (newest first) with optional filters.
- **Query parameters (all optional):**
  - `limit` (1–100, default 20) and `offset` — paging.
  - `priority`, `team`, `category`, `needs_review` — narrow the results.
  - `q` — substring search in the message text.
- **Returns:** `{ "count": N, "items": [...] }`. With no parameters, you get the latest 20.
- **Validation note:** `limit` is bounded (`ge=1, le=100`) so nobody can request a
  million rows at once.
