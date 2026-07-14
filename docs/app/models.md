# `models.py` — the `tickets` database table

**In plain words:** this file describes one database table, `tickets`, as a Python class.
One saved ticket = one row = one `Ticket` object. Because we describe the table in Python
(an "ORM model"), we never write raw SQL by hand — SQLAlchemy generates safe queries for us.

**Beginner terms:**
- **ORM model** = a Python class that maps to a database table; its attributes are columns.
- **Column** = one field in the table (like a spreadsheet column).
- **Primary key** = the unique id for each row.
- **Nullable** = whether a column is allowed to be empty.

---

## `class Ticket(Base)`

- **What it is:** the whole table definition. `Base` (from `db.py`) is what registers it with
  SQLAlchemy. `__tablename__ = "tickets"` names the actual table.

### The columns (what each row stores)

| Attribute | Type | Empty allowed? | Plain meaning |
|-----------|------|:--------------:|---------------|
| `id` | int | (auto) | Unique row number, filled in automatically. |
| `raw_ticket` | text | no | The original customer message. |
| `category` | text | no | Which of the six categories. |
| `priority` | text | no | High / Medium / Low. |
| `assigned_team` | text | no | Which team it went to. |
| `reasoning` | text | no | The one-line "why". |
| `confidence` | float | no | 0.0–1.0 sureness. |
| `needs_human_review` | bool | no (defaults False) | Should a human check it? |
| `engine` | text | no | What produced it (`openai:...` / `mock` / `fallback`). |
| `prompt_version` | text | no | Which prompt version was used. |
| `processing_ms` | int | no | How many milliseconds routing took. |
| `error` | text | **yes** | Error message if something went wrong (else empty). |
| `human_verdict` | text | **yes** | Reserved for the future human-review feature. |
| `created_at` | timestamp | no | When the row was made (filled by the DB). |

- **`created_at` detail:** `server_default=func.now()` means the *database* stamps the time,
  not Python — reliable and consistent.
- **`human_verdict` detail:** unused today, but including it now avoids a database migration
  later when the human-review loop is built. Cheap foresight.

## `to_dict(self) -> dict`

- **What it does:** turns a `Ticket` row into a plain dictionary that can be sent as JSON.
- **Returns:** every column as a key. `created_at` is converted to a readable ISO text string
  (`"2026-07-14T..."`) instead of a raw datetime object.
- **Why it matters:** the API and UI want JSON, not database objects — this is the bridge.
