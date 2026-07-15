# `api_schemas.py` the JSON shapes the API speaks

**In plain words:** this file defines the shapes of data going *in* and *out* of the web API.
They're kept separate from the database model (`models.py`) and the internal `RoutedTicket`
so the public API format can change independently of how we store things. FastAPI uses these
to validate requests, build responses, and auto-generate the `/docs` page.

**Beginner terms:**
- **Request body** = the JSON you send *to* the server.
- **Response model** = the JSON shape the server promises to send *back*.
- **Field validation** = automatic checks (e.g. "text must not be empty").

---

## `class TicketCreate` *what you send to `POST /tickets`*

- **What it is:** the incoming request body. Just one field:
  - `text` the raw customer message. **Must be at least 1 character** (`min_length=1`), so
    an empty request is rejected before any work happens.

## `class TicketOut` *what the API sends back for one ticket*

- **What it is:** the full routed+saved ticket as JSON. It mirrors `Ticket.to_dict()` and
  includes: `id`, `raw_ticket`, `category`, `priority`, `assigned_team`, `reasoning`,
  `confidence`, `needs_human_review`, `engine`, `prompt_version`, `processing_ms`, `error`,
  `human_verdict`, `created_at`.
- **`duplicate: bool`** extra field, defaults to `False`. It's `True` when the row already
  existed and was returned as-is (you submitted an exact duplicate).
- **`model_config = ConfigDict(from_attributes=True)`:** lets FastAPI read values straight off
  an ORM `Ticket` object, not just a dict convenient.

## `class TicketListOut` *what `GET /tickets` returns*

- **What it is:** a wrapper around a list:
  - `count` how many tickets are in this response.
  - `items` the list of `TicketOut` objects.

## `class HealthOut` *what `GET /health` returns*

- **What it is:** a small status report:
  - `status` usually `"ok"`.
  - `provider` `"ollama"` or `"openai"`.
  - `model` the active model name.
  - `db_ok` `True`/`False`, is the database reachable.
  - `db_kind` `"neon"` or `"local"`.
- **Why:** lets you (or a monitor) check the service is alive and see how it's configured at a
  glance.
