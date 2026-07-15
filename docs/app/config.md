# `config.py` all the knobs, read from `.env`

**In plain words:** this file is the single place that reads *settings* things like
which model to use, your API key, and the database address. Nothing secret is written
in the code; it all comes from a `.env` file on your machine. Everywhere else in the app
just says `from app.config import settings` and reads what it needs.

**Why it exists:** so we can change behaviour (local model vs OpenAI, which database)
*without editing code* and so secrets never get committed to git.

---

## `load_dotenv()` (called once at the top)

- **What it does:** reads the `.env` file and loads those `KEY=value` lines into the
  environment so `os.getenv(...)` can see them.
- **Note:** this runs the moment the file is imported. If there's no `.env`, it silently
  does nothing and the defaults below kick in.

## `_as_bool(value: str) -> bool`

- **What it does:** turns text like `"true"`, `"1"`, `"yes"`, `"on"` into a real
  `True`/`False`.
- **Why:** environment variables are always strings. `"false"` as text is actually
  "truthy" in Python, which would be a nasty bug this function avoids that.
- **In/out:** in = a string; out = `True` or `False`.

## `class Settings` (a frozen dataclass)

- **What it is:** a bundle of every setting, each with a sensible default. "Frozen" means
  once created you can't accidentally change a value at runtime it's read-only.
- **The important fields:**
  - `provider` `"ollama"` (local, free) or `"openai"`. Decides which model backend to call.
  - `ollama_model` / `ollama_base_url` which local model and where it lives.
  - `openai_api_key` / `openai_model` your OpenAI key and model name.
  - `temperature` set to `0` so answers are consistent (not creative/random).
  - `max_retries` how many extra tries the model gets if it returns junk.
  - `mock_mode` force the app to run *without any model* (keyword fallback).
  - `max_input_chars` longest message we accept before trimming (`6000`).
  - `database_url` where Postgres lives (defaults to a local one).

### `is_serverless_db` (property)
- **What it does:** returns `True` if the database URL points at Neon (cloud Postgres).
- **Used for:** showing "neon" vs "local" in the health check.

### `active_model` (property)
- **What it does:** returns the right model name for whichever `provider` is selected —
  so the rest of the app can just ask for "the model" without caring which backend it is.

### `use_mock` (property) *the clever safety net*
- **What it does:** answers "should we skip the real model and use the built-in keyword
  router?"
- **When it's True:** either you asked for it (`mock_mode`), **or** you picked OpenAI but
  gave no API key.
- **Why it's smart:** if you're on Ollama (which needs no key), a missing OpenAI key does
  NOT force mock mode. The result: **the app always has a way to run**, key or no key.

---

## `settings = Settings()` (the last line)

- **What it is:** one ready-made `Settings` object, built as soon as the file loads.
- **How everyone uses it:** `from app.config import settings` then `settings.provider`, etc.
  There's only ever this one shared copy.
