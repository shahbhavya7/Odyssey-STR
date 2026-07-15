# Phase 0, Explained (for complete beginners)

## a) What we built in Phase 0 and why

Phase 0 is the foundation of the Escalio. We didn't build the AI part yet —
we built the ground it will stand on: a place to keep secrets safely, a strict definition
of what a "routed ticket" must look like, and a working connection to the database. We also
added a **provider switch** like choosing which kitchen cooks your order so we can
develop for free against a local AI model (Ollama) and flip one setting to OpenAI for the
final demo. Doing this first means every later phase plugs into something solid instead of guessing.

## b) Every file, explained

| File | What it's for (one line) |
|------|--------------------------|
| `requirements.txt` | The shopping list of software packages this project needs. |
| `.env.example` | A template showing which settings/passwords you need with fake values, safe to share. |
| `.env` (you create it) | Your real settings and passwords. Like a locked drawer it stays on your machine and is never uploaded. |
| `.gitignore` | A "do not pack" list telling git which files (like `.env`) must never be saved to the shared code history. |
| `app/__init__.py` | An empty marker file that tells Python "the `app` folder is a package you can import from." |
| `app/config.py` | Reads all settings out of the locked drawer (`.env`) so no password ever appears in code. |
| `app/schema.py` | The contract: the exact shape every routed ticket must have, with fixed drop-down lists for category/priority/team. |
| `app/db.py` | The plumbing to the database: how to connect, how to open/close a conversation with it, and a health check. |
| `docs/PHASE_0_EXPLAINED.md` | This file the plain-English tour of Phase 0. |

## c) Every function (and class), explained

### In `app/config.py`

**`_as_bool(value)`**
- **What it does:** Turns text like `"true"`, `"1"`, or `"yes"` into the real yes/no value `True`. Environment variables are always text, so we need a translator.
- **Inputs:** one piece of text (a string).
- **Output:** `True` or `False`.
- **Why it exists:** Without it, the text `"false"` would count as "yes" in Python (any non-empty text does), which would silently turn mock mode on.

**`Settings` (a class)**
- **What it does:** One tidy box holding every setting the app needs which provider to use, both models' names, the API key, database address, and so on each read from the environment with a sensible default. It is "frozen," meaning once created it can't be changed, so no code can accidentally overwrite a setting mid-run.
- **Inputs:** none directly; it reads environment variables.
- **Output:** a `Settings` object you can ask things like `settings.provider`.
- **Why it exists:** So there is exactly one place settings come from. Change `.env`, restart, done.

**`Settings.active_model` (a property a value that's computed when you ask for it)**
- **What it does:** Hands back the model name for whichever kitchen is switched on: the Ollama model if `PROVIDER=ollama`, otherwise the OpenAI model.
- **Inputs:** none (it looks at the settings it already holds).
- **Output:** a model name (a string), e.g. `qwen2.5:7b`.
- **Why it exists:** So the rest of the app can ask "which model are we using?" without caring which provider is selected.

**`Settings.use_mock` (a property a value that's computed when you ask for it)**
- **What it does:** Answers "should we run without any real AI model?" It says yes if you set `MOCK_MODE=true`, **or** if you picked OpenAI but left the API key blank. Ollama needs no key, so a blank OpenAI key does *not* force mock mode while `PROVIDER=ollama`.
- **Inputs:** none (it looks at the settings it already holds).
- **Output:** `True` or `False`.
- **Why it exists:** So the app always has a way to run a missing OpenAI key means "pretend mode," never a crash.

**`settings` (a variable at the bottom of the file)**
- **What it does:** The single, ready-made `Settings` object every other file imports and uses.
- **Why it exists:** So the settings are loaded once, not rebuilt in ten different places.

### In `app/schema.py`

**`Category`, `Priority`, `Team` (Enums)**
- **What they do:** An Enum is a fixed drop-down menu: only the listed choices are allowed, nothing else. These three define the allowed categories (7), priorities (High/Medium/Low), and teams (7).
- **Inputs/Output:** you use them like `Priority.HIGH`, which is the text `"High"`.
- **Why they exist:** The AI model literally *cannot* hand us a made-up team like "Wizards" anything off the menu is rejected automatically.

**`RoutedTicket` (a Pydantic model a form with strict rules)**
- **What it does:** Defines the exact shape of one routing result: `category`, `priority`, `assigned_team`, a one-line `reasoning` (200 characters max), a `confidence` score that must be between 0.0 and 1.0, and a `needs_human_review` yes/no flag. If any field is missing or wrong, Pydantic (a library that checks data like a strict form validator) refuses it.
- **Inputs:** the six field values.
- **Output:** a validated ticket object, or a clear error if the data is bad.
- **Why it exists:** This is the promise the whole system keeps: whatever chaos comes in, what comes out always has this shape.

**`safe_fallback(reason)`**
- **What it does:** Builds a guaranteed-valid "I'm not sure a human should look" result: General Inquiry, Medium priority, General Triage team, confidence 0.0, review flag on. The `reason` you pass becomes the explanation (trimmed to 200 characters).
- **Inputs:** one string why we're falling back (e.g. "model returned invalid JSON").
- **Output:** a valid `RoutedTicket`.
- **Why it exists:** It's the safety net. When the AI fails, the app doesn't crash it escalates politely.

### In `app/db.py`

**`engine` (a variable)**
- **What it does:** The engine is the database "phone line" manager it knows the address (from `DATABASE_URL`) and manages the actual connections.
- **Why it exists:** Everything that talks to Postgres goes through this one line.

**`SessionLocal` (a variable)**
- **What it does:** A factory that makes database sessions. A session is like a phone call to the database: you dial, talk (read/write), and must hang up.
- **Why it exists:** Each piece of work gets its own fresh call instead of everyone shouting on one line.

**`Base` (a class)**
- **What it does:** The empty parent class that future database table definitions (Phase 2) will inherit from, so SQLAlchemy knows they're tables.
- **Why it exists:** Declared now so Phase 2 has somewhere to plug in.

**`get_db()`**
- **What it does:** Opens a session, hands it to whoever asked, and no matter what happens hangs up (closes it) at the end. The `finally` part guarantees the hang-up even if an error occurs mid-call.
- **Inputs:** none.
- **Output:** it *yields* (lends out) a session.
- **Why it exists:** In Phase 3, FastAPI will use this so every web request automatically gets a session and never leaks a connection.

**`ping_db()`**
- **What it does:** Asks the database the simplest possible question (`SELECT 1`, meaning "say 1 back to me"). If it answers, return `True`; if anything goes wrong, return `False`. It never crashes.
- **Inputs:** none.
- **Output:** `True` or `False`.
- **Why it exists:** A one-call health check: "is the database even there?"

**The `if __name__ == "__main__":` block**
- **What it does:** This means "only run the next lines when this file is executed directly" (with `python -m app.db`), not when it's imported by other code. It prints whether the database connection worked.
- **Why it exists:** So you can test the database connection with one command.

## d) Every command we ran, explained

| Command | What it does | What success looks like |
|---------|--------------|-------------------------|
| `python -m venv .venv` | Creates a virtual environment a private, separate toolbox of Python packages just for this project, so it doesn't mix with your system. | A new `.venv/` folder appears. |
| `source .venv/bin/activate` | Steps into that toolbox. (Windows: `.venv\Scripts\activate`.) | Your terminal prompt now starts with `(.venv)`. |
| `pip install -r requirements.txt` | Reads the shopping list and downloads/installs every package on it. | Lines of "Successfully installed …" and no red errors. |
| `cp .env.example .env` | Copies the settings template into your real (private) settings file, which you then edit. | A new `.env` file exists; you fill in your real values. |
| `createdb ticketrouter` | Asks Postgres to create an empty database named `ticketrouter`. | No output at all silence means it worked. |
| `python -m app.db` | Runs our database health check. | It prints `Database connection OK.` |
| `python -c "…safe_fallback('x')…"` | Runs one tiny line of Python to prove the contract works: it builds and prints a fallback ticket. | It prints a `RoutedTicket` with General Inquiry / Medium / General Triage. |
| `git init` / `git add` / `git commit` | Starts version control (a save-game history for code), stages the files, and records the first snapshot. | `git log` shows one commit: "Phase 0: foundation, config, schema, db setup". |

## e) Words you'll hear (mini glossary)

- **Environment variable (env var):** a named setting that lives *outside* the code, in your terminal or a `.env` file like a sticky note the program reads at startup. Keeps passwords out of code.
- **`.env` file:** a locked drawer for those sticky notes. It stays on your machine; `.gitignore` makes sure it's never uploaded.
- **Enum:** a fixed drop-down menu in code. Only the listed values are valid; everything else is rejected.
- **Pydantic:** a Python library that acts like a strict form validator data either matches the declared shape or is refused with a clear error.
- **Schema / contract:** the agreed shape of the data (which fields, which types, which limits). Ours is `RoutedTicket`.
- **SQLAlchemy:** a Python library that lets us talk to the database using Python objects instead of writing raw SQL by hand (this also protects against SQL injection attacks).
- **Engine:** SQLAlchemy's connection manager it knows the database's address and handles the actual wiring.
- **Session:** one conversation with the database like a phone call you must hang up when you're done.
- **Dependency (in FastAPI, coming in Phase 3):** something a request needs handed to it automatically like room service delivering a fresh database session to each request.
- **Provider:** which AI backend actually answers our requests. We support two `ollama` and `openai` and pick one with the `PROVIDER` setting, like choosing which kitchen cooks your order.
- **Ollama:** a free tool that runs an AI model on your own computer. It offers an "OpenAI-compatible" doorway, meaning we can talk to it with the same code we'd use for OpenAI so switching providers is just one setting, not a rewrite.
