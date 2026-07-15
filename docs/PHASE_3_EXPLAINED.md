# Phase 3, Explained (for complete beginners)

## a) What Phase 3 does, and why an API matters

So far the router could only be used from the terminal. Phase 3 wraps it in a **web
API** a stable "front door" that *any* client can knock on over HTTP: a `curl`
command, the Streamlit UI we build next, or some entirely separate app. Nothing that
calls the API needs to know Python, our database, or how the AI works; it just sends a
message to a web address and gets JSON back. This separation is what makes the system
reusable instead of a one-off script.

An everyday analogy: the API is a building with labelled **service windows** (endpoints).
You walk up to the right window, hand in your request, and the clerk hands back a result
with a **stamp** (a status code) telling you what happened.

We built it **thin**: each endpoint just checks the input, calls one function from the
layers below, and shapes the reply. All the real work still lives in Phases 1–2.

## b) Every new file, explained

| File | What it's for (one line) |
|------|--------------------------|
| `app/api_schemas.py` | Defines the exact JSON shapes the API accepts and returns. |
| `app/api.py` | The FastAPI app and its four endpoints. |
| `run_api.sh` | The one command that starts the web server. |
| `api_check.sh` | Curl commands that exercise every endpoint in order. |
| `docs/PHASE_3_EXPLAINED.md` | This file the plain-English tour of Phase 3. |

## c) Every endpoint and function, explained

### The shapes (`app/api_schemas.py`)

These are **Pydantic** models describing the API's contract deliberately separate from
the internal routing object and the database model, so the public JSON can change
independently.
- **`TicketCreate`** the incoming body: `{ "text": "..." }`. It has a `min_length=1`
  rule, so a *truly* empty string is rejected by validation before it ever reaches our
  code (a clean 422). A whitespace-only string still gets through and is handled safely
  by the service belt and suspenders.
- **`TicketOut`** one ticket going out, mirroring `Ticket.to_dict()` (id, category,
  priority, …). `from_attributes=True` lets it be built straight from a database row.
- **`TicketListOut`** `{ count, items }` for the list endpoint.
- **`HealthOut`** `{ status, provider, model, db_ok }` for the health check.

### `Depends(get_db)` how each endpoint gets a database session

Endpoints that touch the database declare `db: Session = Depends(get_db)`. This is
**dependency injection**: FastAPI automatically opens a fresh session (from Phase 0's
`get_db`), hands it to the endpoint, and closes it afterwards like room service
delivering a clean session to each request and clearing it away when done. The endpoint
never opens or closes its own session, so connections can't leak.

### `GET /health` → `HealthOut`
- **What it does:** Reports that the service is alive, which provider/model is active, and
  whether the database is reachable (`db_ok`, via `ping_db()`).
- **Input:** none. **Output:** the health JSON. **Status:** always 200.
- **Why it exists:** A safe status window that works *even when the database is down*
  (it just reports `db_ok=false`). This is the proof of **graceful degradation** the
  app tells you what's wrong instead of crashing.

### `POST /tickets` → `TicketOut` (status 201)
- **What it does:** Takes `{ "text": ... }`, calls `route_and_save()` (route it, store it),
  and returns the **complete saved row** including the classification in the *same*
  response. So the caller sees the category/priority/team immediately, with no second
  lookup.
- **Input:** a `TicketCreate` body. **Output:** the saved `TicketOut`. **Status:** 201
  ("Created").
- **Why it returns the saved row directly:** convenience and speed one round trip gives
  you both "it's stored (here's its id)" and "here's how it was classified."
- **If the AI fails:** no special handling needed. `route_ticket()` always returns a valid
  fallback, so this still returns **201** with `needs_human_review=true` and a populated
  `error` field a useful answer, never a crash.

### `GET /tickets/{ticket_id}` → `TicketOut`
- **What it does:** Fetches one ticket by its id. If there's no such ticket, returns a
  clean **404** with `{"detail": "Ticket not found"}`.
- **Input:** the id in the **path**. **Output:** that ticket, or 404.
- **Why it exists:** Look up any past ticket by its receipt number.

### `GET /tickets` → `TicketListOut`
- **What it does:** Returns recent tickets, newest first, as `{ count, items }`.
- **Input:** optional **query params** `limit` (default 20, max 100) and `offset`
  (default 0), validated by FastAPI. **Output:** the count and the list.
- **Why it exists:** Show a feed / page through history (and power the Phase 4 batch view).

### Error handling (the graded bit)
- A dedicated exception handler catches database-connection errors (`OperationalError`,
  `InterfaceError`) and turns them into a clean **503** with
  `{"detail": "Database unavailable. Is Postgres running?"}` never a raw stack trace.
- At startup, `init_db()` is wrapped in try/except: if the DB is down the app still
  **starts** (so `/health` can report `db_ok=false`), it just logs a one-line warning.

### CORS
The API enables permissive **CORS** (`allow_origins=["*"]`) so the Streamlit app can call
it from the browser during local development. In production this should be locked down to
specific origins noted in a comment in the code.

## d) Commands, expected output, and the /docs page

Start the server (leave it running in one terminal):
```bash
bash run_api.sh          # == uvicorn app.api:app --reload --port 8000
```

**Swagger UI** open **http://localhost:8000/docs** in a browser. FastAPI auto-generates
this interactive page from the code: you can expand `POST /tickets`, click "Try it out",
type a message, and see the live JSON response no curl needed. (It's generated from the
**OpenAPI** description of the API.)

Exercise every endpoint from another terminal:
```bash
bash api_check.sh
```
Expected, in order: `/health` shows `db_ok: true`; `POST /tickets` returns **201** with a
new `id` and the classification; `GET /tickets/{id}` returns that same row; `GET /tickets`
returns a count and newest-first items; the empty-text POST still returns **201** with
`needs_human_review: true` and `error: "empty_input"`; and `GET /tickets/999999` returns a
clean **404**.

## e) Words you'll hear (mini glossary)

- **API (Application Programming Interface):** a defined way for programs to talk to each
  other here, over the web.
- **Endpoint:** one labelled service window at a URL path (e.g. `/tickets`).
- **HTTP method:** the *kind* of request. **GET = ask for** data; **POST = submit** data.
- **Path parameter vs query parameter:** part of the address itself (`/tickets/7`) vs
  tacked-on options after `?` (`/tickets?limit=5`).
- **Request body / response body:** the JSON you send in / get back.
- **Status code the clerk's stamp:** **200** OK, **201** created (filed), **404** not
  found, **422** your input was invalid, **503** office closed (DB unavailable).
- **JSON:** the plain text format for structured data both sides speak.
- **Dependency injection:** the framework hands an endpoint what it needs (a DB session)
  automatically that's `Depends(get_db)`.
- **CORS (Cross-Origin Resource Sharing):** browser rules for which websites may call this
  API; we open it up for local dev.
- **Swagger / OpenAPI:** an auto-generated, interactive description of the API the
  `/docs` page you can click through.
