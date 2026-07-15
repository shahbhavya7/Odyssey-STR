# Escalio Project Plan

**Mission:** Read any support message and output `category`, `priority` (High/Medium/Low),
`assigned_team`, and a one-line `reasoning` as structured JSON reliably.

**Our angle:** Everyone builds the same "form → JSON" demo. Ours is a small, production-shaped
triage *service*: a hardened core that never crashes on bad model output, a real client-server
database, a clean API, and a usable UI with optional standout features (a prompt evaluation
lab and a human review loop) layered on top only after the required build is solid.

**Stack:** Python · FastAPI · SQLAlchemy · **local PostgreSQL** · OpenAI (GPT) · Streamlit

---

## Guiding principles

1. **Prompts are the graded core.** Most effort goes into the prompt + reliability layer.
2. **Never crash.** Every failure path (bad JSON, dead key, DB down, empty input) returns a
   valid, useful result.
3. **One layer at a time.** Each phase ends in something runnable and demoable.
4. **Steady commits.** Each phase is a commit cluster, so the GitHub history shows two weeks of
   progress, not a single dump (this is a graded item M4D3).
5. **No secrets in code.** API key and `DATABASE_URL` live in `.env` only.

---

## Architecture (five layers, built bottom-up)

| Layer | Responsibility | Key tech |
|-------|----------------|----------|
| **Core service** | `route_ticket(text)` validate, redact PII, call model, validate JSON, repair/fallback. The only place reliability logic lives. | Python, Pydantic |
| **Prompt module** | System prompt, taxonomy definitions, few-shot examples, priority rubric, version tag. The graded artifact. | Prompt design |
| **Data layer** | SQLAlchemy ORM models + session; save / find-by-id / list. | SQLAlchemy, PostgreSQL |
| **API layer** | REST endpoints; graceful errors on key/DB failure. | FastAPI, Uvicorn |
| **UI layer** | Form + result card, batch mode, lookup-by-id. | Streamlit |

**Request lifecycle (the "walk me through it" answer M4A3):**
UI → `POST /tickets` → `route_ticket()` → input validation → PII redaction → LLM call
(structured output, `temperature=0`, retry) → schema validation → repair or safe fallback →
map to ORM object → `session.add` + `commit` → return JSON row → UI renders the result card.

---

## Database (local PostgreSQL + SQLAlchemy)

- **Setup:** local Postgres instance; `DATABASE_URL` in `.env`
  (e.g. `postgresql+psycopg://user:pass@localhost:5432/ticketrouter`).
- **Schema creation:** `Base.metadata.create_all()` on startup (simple, right-sized for a
  2-week project). *Alembic migrations are noted as a "what I'd do next" answer M4D2.*
- **Why Postgres + ORM (rubric wins):** ORM parameterizes all queries → no SQL injection
  (M4E3); credentials in `.env` → no hardcoded secrets (M4B5); real client-server DB →
  "scope is complete, not a toy" (M4C4).

**`tickets` table**

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | auto |
| `raw_ticket` | text | original message |
| `category` | text | from JSON |
| `priority` | text | High / Medium / Low |
| `assigned_team` | text | from JSON |
| `reasoning` | text | one-line |
| `confidence` | float | 0.0–1.0 |
| `needs_human_review` | bool | low-confidence flag |
| `engine` | text | `openai:<model>` / `mock` / `fallback` |
| `prompt_version` | text | which prompt produced this |
| `processing_ms` | int | for the before/after metric |
| `created_at` | timestamp | default now |
| `human_verdict` | text (nullable) | **Stage-B hook** costs nothing now, avoids a migration later |

---

## Stage A Core (everything the mission requires)

### Phase 0 Foundation & contract
Repo structure, `.env` handling, Pydantic schema with **enums** for category/priority/team
(the model literally cannot return an invalid value), config, SQLAlchemy engine/session setup,
and a **mock mode** so the app runs offline with no API key.
- **Done when:** schema, config, and DB session import cleanly.
- **Covers:** M4B5, M4E3. **Deliverable:** foundation for #1.

### Phase 1 Prompt engine + reliability ★ (the star)
System prompt with taxonomy definitions and a **business-impact priority rubric**
(angry tone does *not* raise priority), few-shot examples covering the three required edge
cases (angry / very short / ambiguous), structured-output enforcement, `temperature=0`, retry
loop, **JSON-repair-or-fallback** path, and `confidence` + `needs_human_review`. A CLI tester.
- **Done when:** any ticket routes to valid JSON every time, including on garbage input.
- **Covers:** M4A1–A4, M4B1, M4B4, "handling AI unreliability". **Deliverables:** #1, #2.
- *Most of our time lives here.*

### Phase 2 Database (SQLAlchemy + Postgres)
`Ticket` ORM model, engine/session, `create_all()` on startup, and repository functions
(`save_ticket`, `get_ticket`, `list_tickets`). Everything through the ORM.
- **Done when:** routing writes a row to Postgres and you can fetch it back by id.
- **Covers:** M4E3, M4C4. **Deliverable:** DB baseline.

### Phase 3 API service
FastAPI wrapping service + DB: `POST /tickets`, `GET /tickets/{id}`, `GET /tickets`.
Session injected via `Depends(get_db)`. Clean errors when the key is missing/invalid or
Postgres is unreachable a useful message, never a stack-trace crash.
- **Done when:** all endpoints work via curl/Postman; invalid key returns a clean error.
- **Covers:** M4B3, M4C3. **Deliverable:** reusable service + POST-to-db / find-by-id.

### Phase 4 UI
Streamlit calling the API: single-ticket form with a **result card** (color-coded priority
badge, confidence bar, review flag), lookup-by-id view, and **batch mode** (paste/upload the
20 tickets → route all → results table). Batch mode *is* the 20-ticket demo in one click.
- **Done when:** a non-technical person routes a ticket and reads the result unaided.
- **Covers:** M4B4, M4C1, M4C2, M4C3. **Deliverables:** #3, #5.

### Phase 5 Before/after + demo readiness
Create the 20 sample-ticket set (reused later as the eval golden set). Add the before/after
metric: documented manual baseline (~1–2 min/ticket) vs measured AI `processing_ms`, surfaced
as a "time saved" line. Harden remaining edge cases (empty, very long, non-English). README
that runs cold + prepared answers for the "Learning Demonstrated" questions.
- **Done when:** runs end-to-end from a clean clone; all 20 tickets demo with a time comparison.
- **Covers:** M4B2, M4C4, M4E2, all of M4D. **Deliverables:** #4, #5.

> **End of Stage A = a complete, gradeable project hitting every deliverable and most of the rubric.**

---

## Stage B Secondary (only after A is solid; this is where we stand out)

Layered on without touching the core path, in priority order.

- **Phase 6 Prompt Lab (eval harness).** Reuse the 20-ticket set as a labeled golden set;
  score per-field accuracy; A/B compare zero-shot vs few-shot (or prompt v1 vs v2). Turns
  "my prompt is good" into "91% vs 68%." *Highest-value extra.* Covers M4A2, M4A4, M4D5.
- **Phase 7 Human review queue + feedback loop.** Low-confidence tickets queue for a human;
  corrections saved to `human_verdict` and promotable into few-shot examples. Covers M4A5,
  M4C1, M4D5.
- **Phase 8 ROI / analytics dashboard.** Distribution by category/team/priority, %
  auto-routed vs flagged, cumulative time & cost saved. Covers M4A5, M4C3.
- **Phase 9 (optional) LLM-as-judge second pass** on low-confidence tickets.

---

## Rubric coverage map

| Rubric area | Where it's earned |
|-------------|-------------------|
| M4A Concept & Understanding | Phases 1, 4, 5 + demo talking points |
| M4B Integration Quality | Phases 1 (consistency, format), 3 (API failure), 0 (secrets), 5 (edge cases) |
| M4C Problem–Solution Fit | Phases 3, 4, 5 |
| M4D Learning Demonstrated | Steady commits (all phases) + Phase 5 prep; Stage B deepens it |
| M4E Code/Build Quality | Enums & ORM (0, 2), README (5), PEP8 throughout |

---

## Per-phase workflow

At the end of each phase, we generate a **single copy-paste Claude Code prompt** for the next
phase scoped to exactly what already exists, with file paths, acceptance criteria
("done when X runs and returns Y"), and constraints (PEP8, no secrets, ORM-only queries) baked
in. This keeps Claude Code focused and stops it rewriting finished work.

**Next step:** on your go, we generate the **Phase 0** Claude Code prompt.
