# Architecture

Escalio is built as five layers, bottom-up. Each layer only talks to the one below it,
so the reliability logic lives in exactly one place and the UI can be swapped without
touching routing.

| Layer | File(s) | Responsibility |
|-------|---------|----------------|
| **Core service** | `app/router_service.py` | `route_ticket(text)` — validate, truncate, redact PII, time, apply review guards, and turn any failure into a safe fallback. **Never raises.** |
| **LLM client** | `app/llm_client.py` | The only code that talks to a model. Provider-agnostic (Ollama or OpenAI via the same SDK). Retry + JSON-repair loop + offline mock. |
| **Prompt** | `app/prompts.py` | The graded artifact: taxonomy, business-impact priority rubric, symptom-based bug sub-routing, few-shot examples, `PROMPT_VERSION`. |
| **Data** | `app/models.py`, `app/repository.py`, `app/db.py` | SQLAlchemy ORM model + session + save/get/list. ORM only → parameterized queries. |
| **API** | `app/api.py`, `app/api_schemas.py` | FastAPI HTTP front door. `POST /tickets`, `GET /tickets/{id}`, `GET /tickets`, `GET /health`. Session injected via `Depends(get_db)`. Clean 503 when the DB is down. |
| **UI** | `ui/` | Streamlit. Calls the API only; holds no business logic. |

## Request lifecycle

```
Streamlit UI
   │  POST /tickets  {text}
   ▼
FastAPI  create_ticket()          app/api.py
   │  route_and_save(db, text)
   ▼
repository.route_and_save         app/repository.py
   │  route_ticket(text)
   ▼
router_service.route_ticket       app/router_service.py
   │   1. empty? → safe_fallback (no model call)
   │   2. truncate to MAX_INPUT_CHARS
   │   3. redact PII (email / card / phone)
   │   4. route_with_llm(text) ──────────────► llm_client.py
   │        - JSON mode, temperature 0
   │        - retry + corrective "repair" message
   │        - LLMError after N attempts
   │   5. validate against RoutedTicket enums
   │   6. apply review guards (non-English → flag)
   │   7. on any failure → safe_fallback
   ▼
repository.save_ticket → ORM commit → Ticket row (id, created_at)
   │
   ▼
TicketOut JSON → UI renders the glass result card
```

## Why these choices

- **Enums as the contract** — the model literally cannot return an off-taxonomy value;
  a bad value fails validation and triggers repair/fallback rather than corrupting data.
- **Provider switch** — develop free against local Ollama, flip one env var to OpenAI for
  the demo. Same code path (Ollama exposes an OpenAI-compatible endpoint).
- **ORM everywhere** — parameterized queries, no SQL injection, and the schema is created
  from the model (`create_all`), right-sized for a two-week project. (Alembic migrations
  are the "what I'd do next" answer.)
- **Fallback is a valid result, not an error** — a dead model still returns a 201 with
  `needs_human_review: true` and a populated `error` field; only a DB failure escalates
  (to a clean 503).
