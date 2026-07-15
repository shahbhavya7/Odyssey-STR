# `app/` explained, file by file

This folder documents **every Python file in `app/`** in plain, beginner language.
Each doc explains what the file is for and walks through each function/class one at a time:
*what it does, what goes in, what comes out, and why it matters.*

## The big picture (how a ticket flows)

```
UI / CLI
   │  raw text
   ▼
router_service.route_ticket()      ← validate, redact PII, time it, never crash
   │  calls
   ▼
llm_client.route_with_llm()        ← talk to the model, retry, repair, or mock
   │  validated against
   ▼
schema.RoutedTicket                ← the shape the answer must fit (enums!)
   │  saved by
   ▼
repository.save_ticket()           ← write a row via the ORM
   │  into
   ▼
models.Ticket  (a table row)  ←→  db.py (engine/session)  ←  config.settings (.env)
   │  served over HTTP by
   ▼
api.py  (POST /tickets, GET /tickets, ...)  using shapes from api_schemas.py
```

## Read in this order (bottom-up, like it was built)

| # | File | One line | Doc |
|---|------|----------|-----|
| 1 | `config.py` | Reads settings from `.env` (keys, model, DB URL) | [config.md](config.md) |
| 2 | `db.py` | Database plumbing: engine, sessions, connect check | [db.md](db.md) |
| 3 | `schema.py` | The answer's shape + enums + safe fallback | [schema.md](schema.md) |
| 4 | `prompts.py` | The instructions we send the model (the graded core) | [prompts.md](prompts.md) |
| 5 | `llm_client.py` | Talks to the model; retry / repair / mock | [llm_client.md](llm_client.md) |
| 6 | `router_service.py` | The one entry point everything calls; never crashes | [router_service.md](router_service.md) |
| 7 | `models.py` | The `tickets` database table (ORM) | [models.md](models.md) |
| 8 | `repository.py` | Save / find / list tickets (+ duplicate check) | [repository.md](repository.md) |
| 9 | `api_schemas.py` | The JSON shapes the API accepts and returns | [api_schemas.md](api_schemas.md) |
| 10 | `api.py` | The web server and its endpoints | [api.md](api.md) |

`__init__.py` is empty it only marks `app/` as a Python package so `import app.x` works.

> **How to read a doc:** every function has a signature line like
> `route_ticket(raw_text: str) -> dict`. The words after `:` are the *type* of each input,
> and the type after `->` is what it hands back. You can ignore the types at first and
> just read the plain-English bullets.
