# Database connection lifecycle (for complete beginners)

Mentor feedback: *"verify one DB connection at start and use it throughout until the
server shuts down."* This doc explains how we did that **correctly** and why "one
connection" really means "one connection **pool**."

## The four words, with one analogy

Think of the database access like a **phone switchboard**:

| Term | Analogy | In our code |
|------|---------|-------------|
| **Engine** | The switchboard itself | One `create_engine(...)` in `app/db.py`, made once. |
| **Pool** | The set of phone lines the switchboard manages | Built into the engine; several connections kept ready. |
| **Connection** | One phone line | Borrowed from the pool for a moment, then returned. |
| **Session** | A single phone *call* on a borrowed line | One per web request, via `get_db()`. |

So the flow for every request is: **borrow a line (connection) from the switchboard
(pool) → make a call (session) → hang up and return the line.**

## Why a POOL, not one shared connection?

The naive reading of "use one connection throughout" is: open a single connection at
startup and reuse that exact object for every request. **That's unsafe.** A raw DB
connection is not meant to be used by two requests at the same time if ten people
submit tickets at once, they'd fight over the one line and you'd get
"connection already in use" errors or corrupted results.

The **correct** version: keep **one engine** (one switchboard) that owns a **pool** of a
few connections. Each request borrows a free line and returns it. That is still "one
thing reused for the whole app lifetime" (one engine/pool), but it is **safe under
concurrency** which we proved by firing 10 simultaneous requests with zero errors.

## Verify ONCE at startup why?

We check the database **one time** when the server boots (`verify_db()` runs
`SELECT 1`). This is **fail-fast visibility**: the very first log line tells you whether
the DB is reachable, instead of discovering it only when the first user hits an error.

```
✅ Database connected (pool ready)          # DB up
⚠️ Database unavailable at startup: ...      # DB down but we START ANYWAY
```

We deliberately **start even if the DB is down**, so `/health` still works and you can
diagnose the problem. Because the pool uses `pool_pre_ping=True`, once the database comes
back the next borrowed connection is silently revalidated **it recovers on its own, no
server restart needed.**

## What `lifespan` does (startup + shutdown in one place)

FastAPI's **lifespan** is a single function that runs code *before* the app serves
requests and *after* it stops. We use it to own the whole connection lifecycle:

- **On startup:** `verify_db()` → log the result → if connected, `init_db()` creates any
  missing tables → remember the state on `app.state`.
- **App runs:** every endpoint uses `db: Session = Depends(get_db)`, drawing sessions
  from the *same* shared pool. No endpoint ever opens its own engine or connection.
- **On shutdown (Ctrl-C):** `engine.dispose()` closes every pooled connection cleanly and
  logs `Database pool disposed.`

## Why `dispose()` at shutdown matters

Closing the pool politely tells the database "I'm done with these lines." Without it,
connections can linger on the server side until they time out wasteful, and on hosted
Postgres (like Neon) you have a limited number of connections, so leaked ones can block
future startups. Disposing on shutdown keeps things tidy.

## The health check

`GET /health` calls `ping_db()` **live** every time (a quick `SELECT 1` through the pool),
so it always reflects the *current* state `db_ok: true` when reachable, `false` when
not and it never raises.

---

### Proof (what we verified)

1. **DB up:** log shows `✅ Database connected (pool ready)`; tables ensured; `/health`
   `db_ok:true`.
2. **DB down:** API still starts; log shows the ⚠️ warning; `/health` `db_ok:false`;
   bring the DB back and `/health` returns `true` with no restart.
3. **10 concurrent POSTs:** all succeed, no "connection already in use" errors.
4. **Ctrl-C:** log shows `Database pool disposed.`
5. Every endpoint uses `Depends(get_db)` no ad-hoc engines or connections anywhere.
