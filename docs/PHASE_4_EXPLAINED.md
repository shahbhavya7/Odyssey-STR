# Phase 4, Explained (for complete beginners)

## a) What Phase 4 does, and why a UI matters

Until now the router was for programmers: you called it with curl or code. Phase 4 adds
a **web app** a friendly screen a non-technical person (a support lead, a manager, a
demo audience) can use with no commands at all. You type a ticket, click a button, and a
clean **triage card** appears: category, priority, the team it goes to, a confidence bar,
and a reason. This is the **demo surface** the thing people actually see.

Two important design choices:
- The UI talks **only to the API**, never to the database directly. The API is the
  **kitchen** (it cooks the result routing, saving); the UI is the **dining room** (it
  just presents the dish nicely). Keeping the kitchen and dining room separate means we
  can change either without breaking the other.
- The UI holds **no business logic**. It only calls the API and draws the result. All the
  smart parts still live in Phases 1–3.

We also made one small, additive change to the API so the UI can **filter** the ticket
list (by priority, team, category, review flag, or a text search).

## b) Every new file, explained

| File | What it's for (one line) |
|------|--------------------------|
| `ui/app.py` | The Streamlit app: page title, sidebar navigation, and the four pages. |
| `ui/api_client.py` | A thin wrapper that calls the API and turns any failure into a friendly message. |
| `ui/components.py` | Reusable visual pieces: colored badges, the confidence bar, and the triage card. |
| `app/api.py` (extended) | `GET /tickets` now accepts optional filters (additive; old behaviour unchanged). |
| `app/repository.py` (extended) | `list_tickets()` applies those filters via the ORM. |
| `docs/PHASE_4_EXPLAINED.md` | This file the plain-English tour of Phase 4. |

**Why the UI calls the API, not the DB:** if the dining room reached into the kitchen's
fridge directly, every menu change would break it. By going through the API's stable
"windows," the UI stays simple and the two layers stay independent.

## c) Every page and component, explained

### The API client (`ui/api_client.py`)
- **`get_health()` / `create_ticket(text)` / `get_ticket(id)` / `list_tickets(**filters)`**
  one function per API endpoint. Each makes the HTTP **REST call**, waits (with a short
  timeout), and returns the JSON. If the API is unreachable or returns an error, it raises
  a friendly `ApiError` with a readable message, so the screen can show a clean red note
  instead of a scary traceback. `get_ticket` returns `None` for a missing id (a 404) so the
  page can say "not found" gently.

### The visual pieces (`ui/components.py`)
- **Badges** small colored **stickers** for fast scanning: `priority_badge`
  (red/amber/green for High/Medium/Low), `team_badge` (a distinct color per team), and
  `review_badge` (⚠ needs review vs ✓ auto-routed).
- **`confidence_bar(conf)`** a 0–100% bar, colored red below 0.4, amber below 0.7, green
  above so you can see at a glance how sure the router was.
- **`result_card(ticket)`** the hero piece: a bordered card with the big category and a
  priority badge on top, the team badge and confidence bar, a bold ⚠ banner *if* a human
  review is needed, the one-line reason in a quoted callout, and a small grey footer
  (engine, prompt version, milliseconds, timestamp, id). It's designed to look like a real
  triage card a support lead could glance at and act on.

### The pages (`ui/app.py`)
Every page shows a **connection indicator** in the sidebar: green "API connected ·
provider:model" when the API answers `/health`, or a red "API offline" note with the
command to start it. If the API is down, each page shows a friendly banner instead of any
error trace.

1. **Route a Ticket** (default) a big text box plus five one-click **example** buttons
   (so a demo is effortless). Click "Route Ticket →" and, after a **spinner**, the triage
   card appears. A collapsed "View raw JSON" **expander** shows the full data for technical
   reviewers pretty for humans, raw for developers.
2. **Batch Demo** paste many tickets (one per line) or upload a `.txt`/`.csv`. "Route
   All" sends each to the API with a **progress bar**, then shows a **summary strip**
   (counts by priority, % needing review, total time), a results **dataframe** (a table),
   and a "Download results as CSV" button. This is the effortless 20-ticket demo.
3. **Browse & Search** filter controls (priority, team, category, needs-review, and a
   text search) that call `list_tickets` with those filters. Each result expands into a
   full card. The active filters and result count are shown clearly.
4. **Find by ID** type a ticket number, click Fetch, and see its card or a clean
   "No ticket #N found" message if it doesn't exist.

### The additive API filter (Part A)
`GET /tickets` gained optional query params `priority`, `team`, `category`,
`needs_review`, and `q` (a case-insensitive text match on the message). `list_tickets()`
applies each one as an ORM filter only when provided, keeping newest-first order and the
existing paging. With no filters, it behaves exactly as before nothing old broke.

## d) Commands to run BOTH servers, and what to expect

You need **two terminals** (the kitchen and the dining room):

```bash
# Terminal 1 the API (the kitchen). Needs Postgres + Ollama up.
source .venv/bin/activate
uvicorn app.api:app --reload --port 8000

# Terminal 2 the UI (the dining room)
source .venv/bin/activate
streamlit run ui/app.py
```

Streamlit opens a browser tab (usually http://localhost:8501). Expect a green
"API connected" note in the sidebar. Type a ticket on "Route a Ticket" and you'll see the
card; try the Batch Demo to route several at once and download the CSV. If you stop the
API (Ctrl-C in Terminal 1), every page shows the friendly "API offline" banner no crash.

Quick check that the new filter works, from a third terminal:
```bash
curl -s "http://localhost:8000/tickets?priority=High&limit=5" | python -m json.tool
```

## e) Words you'll hear (mini glossary)

- **Streamlit:** a Python tool that turns a script into a web app no HTML/JavaScript
  needed. Great for data apps and demos.
- **Frontend vs backend:** the frontend is what the user sees and clicks (our Streamlit
  UI); the backend is the engine behind it (our API + database + AI).
- **REST call:** a request to an API over the web (GET to ask, POST to submit).
- **JSON:** the plain-text data format the UI and API exchange.
- **Component:** a reusable piece of the interface here, a badge or the result card.
- **State (session state):** the app's short-term memory for one user e.g. remembering
  the text you typed when a button refreshes the page.
- **Spinner:** the little "working…" animation shown while we wait for the API.
- **Dataframe:** a table of rows and columns (from the pandas library) shown on screen.
- **Badge:** a small colored sticker for fast scanning (priority, team, review status).
