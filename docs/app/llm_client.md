# `llm_client.py` the part that actually talks to the model

**In plain words:** this file sends the prompt to the AI and gets an answer back. It's the
*only* file that touches a real model. It handles everything that can go wrong with a model:
it retries on errors, sends a "you messed up, try again" nudge if the reply isn't valid JSON,
and if there's no model available at all falls back to a simple keyword guesser so the
app still works offline.

**Beginner terms:**
- **Retry** = try again a few times before giving up.
- **Repair** = after a bad reply, add a corrective message and ask once more.
- **Mock** = a fake, rule-based stand-in used when no real model is available.

---

## `class LLMError(Exception)`

- **What it is:** a custom error type raised only when the model fails to give a valid answer
  after all retries. The layer above (`router_service`) catches this and returns a safe
  fallback so this error never reaches the user.

## `_REQUIRED_KEYS` (a tuple)

- **What it is:** the exact list of keys the model's JSON must contain. Used to build the
  repair message ("return a JSON object with exactly these keys: ...").

## `_make_client() -> OpenAI`

- **What it does:** builds the client object pointed at the right backend.
- **The trick:** both Ollama and OpenAI speak the same "OpenAI API" language, so one client
  type handles both it just changes the URL/key. Ollama needs no real key, so a dummy
  `"ollama"` string is passed to satisfy the SDK.

## `_repair_message() -> dict`

- **What it does:** returns a single corrective user message telling the model its last reply
  wasn't valid JSON and to return only the required keys, no markdown.
- **When it's used:** appended to the conversation after a bad/unparseable response, right
  before the next retry.

## `route_with_llm(ticket_text: str) -> tuple[RoutedTicket, str]` *the main function*

- **What it does:** sends the ticket to the model and returns a validated result.
- **Returns:** a pair `(RoutedTicket, engine_name)` where engine_name is like
  `"openai:gpt-4o-mini"` or `"mock"`.
- **Step by step:**
  1. If mock mode is on → skip the model, return `_mock_route(...)` tagged `"mock"`.
  2. Build the messages from the prompt, then loop up to `max_retries + 1` times:
     - Call the model asking for a JSON object (`response_format=json_object`).
     - If the reply is empty → error. If it won't parse as JSON → error. If it doesn't fit
       `RoutedTicket` → error.
     - On any of those, save the reason, append a repair message, wait a bit, and retry.
     - On success, return immediately.
  3. If every attempt fails → raise `LLMError` with the last error.
- **Why the two `except` blocks differ:** bad-shape errors (JSON/validation) trigger a
  *repair* message; network/API errors just retry without one.
- **The `time.sleep(1.5 * (attempt + 1))`:** waits longer after each failure (backoff) so we
  don't hammer a struggling server.

---

## The mock path (offline safety net)

### `_MOCK_RULES` (a list)
- **What it is:** an ordered list of keyword→answer rules. E.g. if the text contains
  "refund"/"charge"/"invoice" → Billing/High/Billing Team. **First match wins.**

### `_mock_route(ticket_text: str) -> RoutedTicket`
- **What it does:** lowercases the text and checks each rule in order; the first keyword hit
  decides the answer. If nothing matches → General / Low / Customer Support, flagged for
  review.
- **Honest limitation (stated in the code):** it's "not smart just enough to keep the app
  runnable offline." Confidence is deliberately modest (0.3–0.5).

## `__all__ = [...]`

- **What it is:** the list of names other files are meant to import from here
  (`route_with_llm`, `LLMError`, `PROMPT_VERSION`). Just a tidiness/convenience marker.
