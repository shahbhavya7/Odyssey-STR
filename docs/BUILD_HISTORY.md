# Escalio — build history (for beginners)

How Escalio was built, phase by phase, in plain language. This is the *story* of the
project (what each step added and why); to run or understand the current app, start with
the root [README.md](../README.md) and [ARCHITECTURE.md](../ARCHITECTURE.md), and the
per-file tour in [docs/app/README.md](app/README.md).

Each layer was built bottom-up, and every phase ended in something runnable.

---

## Phase 0 — Foundation & contract
Set up the skeleton: repo layout, `.env` handling (no secrets in code), the Pydantic
**data contract** with enums for category/priority/team (so the model literally can't
return an off-list value), config, the SQLAlchemy engine/session, and a **mock mode** so
the app runs offline with no API key.
- **Done when:** schema, config, and DB session import cleanly.
- **Why it matters:** the enums are the safety rail everything else leans on.

## Phase 1 — Prompt engine + reliability ★ (the heart)
The graded core: a system prompt with taxonomy definitions and a **business-impact priority
rubric** (an angry tone does *not* raise priority), few-shot examples for the hard edge
cases, structured-output enforcement, `temperature=0`, a **retry + JSON-repair-or-fallback**
loop, and `confidence` + `needs_human_review`. Any input routes to valid JSON *every time* —
even garbage. A CLI tester (`cli.py`) drives it by hand.
- **Why it matters:** this is where routing quality and the "never crash" promise live.

## Phase 1.1 — Prompt tuning
Iterated the prompt against real examples: broadened "Bug & Outage" to cover cosmetic
defects, added explicit confidence bands, a multi-issue tie-break rule, a deterministic
default engineering team when unclear, and prompt-injection resistance (the message is
*data, not instructions*).

## Phase 2 — Database (SQLAlchemy + PostgreSQL)
The `Ticket` ORM model, engine/session, `create_all()` on startup, and repository functions
(`save_ticket`, `get_ticket`, `list_tickets`) — everything through the ORM, so queries are
parameterized (no SQL injection).
- **Done when:** routing writes a row to Postgres and you can fetch it back by id.

## Phase 3 — API service (FastAPI)
A thin HTTP front door over the service + DB: `POST /tickets`, `GET /tickets/{id}`,
`GET /tickets`, `GET /health`. The session is injected via `Depends(get_db)`; a dead key or
unreachable DB returns a clean error, never a stack trace.
- **Run it:** `uvicorn app.api:app --reload --port 8000` (or `bash run_all.sh` to start the
  API + UI together). Interactive docs at `http://localhost:8000/docs`.

## Phase 4 — UI (Streamlit)
A friendly front end calling the API only: a single-ticket form with a color-coded **result
card** (priority badge, confidence bar, review flag), lookup-by-id, and **batch mode** (route
many tickets at once — the effortless demo).

## Phase 4.5 — Dark "liquid-glass" redesign
A visual overhaul (paint only, no logic change): a dark glassmorphism theme with an aurora
glow, design tokens, and a unique "plasma" color identity. Gave the app its name, **Escalio**.

## Phase 5 — Demo readiness & before/after proof
The finishing layer: the 20-ticket sample set (`data/sample_tickets.csv`), a measured
**manual-vs-AI timing** comparison surfaced as a "Time Saved" card, an edge-case hardening
pass, a run-cold README, and the demo script. See [EDGE_CASES.md](EDGE_CASES.md).

---

## After Phase 5 — the standout features
These built on the solid core; each has its own dedicated doc:

- **Input safety & the `is_ticket` gate** — guardrails (empty-reject, length cap, PII
  redaction), strict JSON (`extra="forbid"`), and LLM-flagged gibberish/greetings that are
  *shown but never stored*. → [GUARDRAILS.md](GUARDRAILS.md)
- **Multi-issue routing** — one message can hold several problems; each is classified, with
  one ticket-level priority (the max) and one accountable primary team. → [MULTI_ISSUE.md](MULTI_ISSUE.md)
- **DB connection lifecycle** — verify once at startup, reuse one connection pool for the
  app's lifetime, dispose cleanly on shutdown. → [DB_LIFECYCLE.md](DB_LIFECYCLE.md)
- **Provider switch** — `groq` (default, fast hosted Qwen) ⇄ `ollama` (local/free) ⇄
  `openai`, one env var, zero code change. → root [README.md](../README.md)
- **Model benchmark harness** — score multiple models against a labeled set, 3× for
  variance, with a Streamlit "Benchmarks" tab. → [../eval/README.md](../eval/README.md)

## Words you'll hear (mini glossary)
- **Enum:** a fixed list of allowed values; the model can't return anything off the list.
- **Fallback:** a safe, valid default result returned when something fails, so the service
  never crashes.
- **Few-shot:** worked examples included in the prompt to anchor the tricky calls.
- **ORM:** maps database rows to Python objects and parameterizes queries (no SQL injection).
- **Guardrail:** deterministic input safety that runs *before* the model.
- **Edge case:** an unusual input that breaks naive code (empty, huge, foreign-language,
  hostile) — handling these *is* the reliability story.
