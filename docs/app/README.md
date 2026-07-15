# `app/` explained, file by file (for beginners)

One consolidated tour of **every Python file in `app/`** in plain language: what each file
is for, its key functions, and why they matter. `app/` is the whole service — no UI, no
scripts.

## The big picture (how a ticket flows)

```
UI / CLI
   │  raw text
   ▼
router_service.route_ticket()   ← guardrails, redact PII, time it, NEVER crash
   │  calls
   ▼
llm_client.route_with_llm()     ← talk to the model (Groq / Ollama / OpenAI), retry, repair, or mock
   │  validated against
   ▼
schema.TriageResult             ← the shape the answer MUST fit (enums + strict + is_ticket + issues[])
   │  saved by
   ▼
repository.route_and_save()     ← store real tickets only, dedup, write a row via the ORM
   │  into
   ▼
models.Ticket  (a table row)  ←→  db.py (engine / pool / session)  ←  config.settings (.env)
   │  served over HTTP by
   ▼
api.py  (POST /tickets, GET /tickets, /health)  using shapes from api_schemas.py
```

Read bottom-up (the order it was built): **config → db → schema → prompts → llm_client →
router_service → models → repository → api_schemas → api**.

---

## `config.py` — settings from `.env`
Reads all runtime configuration once from environment variables (no secrets in code).
The star is the **provider switch** (`PROVIDER`): `groq` (default, fast hosted Qwen),
`ollama` (local/free/offline), or `openai`. Exposes `settings` (a frozen dataclass) with
`active_model`, `use_mock` (falls back to the offline stub when a hosted provider has no
key), and DB/temperature/retry/length knobs. Logs a friendly warning if the default
provider has no key.

## `db.py` — database plumbing
Owns **one engine = one connection pool**, reused for the whole app lifetime. Provides
`SessionLocal`/`get_db` (a per-request session drawn from the pool), `Base` (the ORM
parent), `ping_db()` (live health check, never raises), `verify_db()` (one-shot startup
check → `(ok, message)`), and `init_db()` (creates missing tables; idempotent). Each
request borrows a connection and returns it — safe under concurrency. See
[DB_LIFECYCLE.md](../DB_LIFECYCLE.md).

## `schema.py` — the answer's shape (the contract)
Defines what a valid result looks like with Pydantic, and makes bad values **impossible**:
- **Enums** `Category` / `Priority` / `Team` — the model can only return listed values.
- **`Issue`** — one problem: `{category, priority, assigned_team, reasoning}`.
- **`TriageResult`** — `is_ticket` gate + a **list of issues** + ticket-level `priority`
  (= max issue severity), `primary_team`, `primary_issue_index`, `confidence`,
  `needs_human_review`, overall `reasoning`. `extra="forbid"` (unknown keys rejected) plus
  a validator enforcing internal consistency (priority = max, primary matches, 1–5 issues
  for a real ticket, empty for a non-ticket).
- **`safe_fallback(reason)`** — a valid single-issue ticket for when the model fails (a real
  ticket is never dropped). **`rejected_result(reason)`** — a valid non-ticket (gibberish /
  greeting) with null routing, never stored.

## `prompts.py` — the instructions we send (the graded core)
Holds `PROMPT_VERSION` and `SYSTEM_PROMPT` (taxonomy, business-impact priority rubric,
symptom-based bug sub-routing, is_ticket rules, multi-issue extraction, injection
resistance) plus few-shot `FEW_SHOT_EXAMPLES` that anchor the tricky cases. `build_messages()`
assembles system + examples + the new ticket. This is where most routing quality lives.

## `llm_client.py` — talks to the model
The only code that calls a model. `_make_client_for(provider)` builds an OpenAI-SDK client
for Groq / Ollama / OpenAI (all speak the OpenAI wire format). `_run_route_loop()` is the
shared retry + **JSON-repair** loop: on bad/invalid output it appends a corrective message
and retries, raising `LLMError` after `max_retries`. `route_with_llm()` uses the active
provider; `route_with_llm_config(text, provider, model)` targets a specific model (used by
the benchmark) — same prompt/validation path. `_mock_route()` is a keyword stub so the app
runs offline.

## `router_service.py` — the one entry point (never crashes)
`route_ticket(text)` (and `route_ticket_with(...)` for a specific model) run the pipeline:
guardrail `pre_check` → `sanitize` (truncate + redact PII) → LLM → deterministic review
guards (force human review for non-English, or a ticket maxed at 5 issues) → flatten to a
JSON-ready dict carrying the full multi-issue view **plus** flat back-compat fields
(primary issue + ticket priority). Any failure becomes a `safe_fallback` — it never raises.
Does **not** touch the database.

## `models.py` — the `tickets` table (ORM)
The SQLAlchemy `Ticket` model = one row per stored ticket. Flat columns (`category`,
`priority`, `assigned_team`, `reasoning`) hold the **primary** issue + ticket priority, so
existing queries keep working; newer columns hold the full picture (`issues` JSON,
`all_teams`, `primary_team`, `primary_issue_index`) plus metadata (`engine`,
`prompt_version`, `processing_ms`, `confidence`, `needs_human_review`, `created_at`,
`human_verdict`). `to_dict()` returns a JSON-serializable row.

## `repository.py` — save / find / list (ORM only)
The data-access layer; every function takes a `Session`. `save_ticket()` writes a row from
a result dict (serializes `issues`, joins `all_teams`). `get_ticket()` / `find_ticket_by_text()`
/ `list_tickets()` (with additive filters; team filter matches **any** concerned team).
`route_and_save()` is the one call the API uses: routes, then stores **only real tickets**
(gibberish → `stored=false`, no row), de-duplicates exact text, and returns a dict with
`is_ticket` / `stored` / `duplicate` / `id`. ORM-only → parameterized queries, no SQL
injection.

## `api_schemas.py` — the HTTP contract
Pydantic request/response shapes kept separate from the ORM and internal `TriageResult`:
`TicketCreate` (input), `IssueOut`, `TicketOut` (a stored ticket, with the multi-issue
fields), `TriageOut` (POST result — covers both a stored ticket and a rejection),
`TicketListOut`, `HealthOut`.

## `api.py` — the HTTP front door (FastAPI)
Thin endpoints over the layers below; the DB session is injected via `Depends(get_db)`.
A **lifespan** handler verifies the DB once at startup (starts anyway if it's down),
ensures tables, and disposes the pool on shutdown. Endpoints: `GET /health`,
`POST /tickets` (201 when a new row is stored, 200 for a rejection/duplicate),
`GET /tickets/{id}` (404 if missing), `GET /tickets` (filters). A lost DB connection
returns a clean **503**, never a stack trace.
