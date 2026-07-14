# `router_service.py` — the one front door, and it never crashes

**In plain words:** this is the single function everything else calls to route a ticket:
`route_ticket(text)`. It wraps the model call with all the *non-model* safety work —
checking the input, trimming huge messages, hiding personal info (PII) before it leaves the
program, timing how long it took, and turning *any* failure into a safe, valid result. Its
golden rule: **it never raises an exception.** Whatever you throw at it, you get a usable
dictionary back.

**Beginner terms:**
- **PII** = Personally Identifiable Information (emails, card numbers, phone numbers).
- **Redact** = mask/replace sensitive text before sending it anywhere.
- **Guard** = an extra safety rule applied on top of the model's answer.

---

## Module-level setup

- `DetectorFactory.seed = 0` — makes language detection give the *same* answer every time
  (it's random by default; we want deterministic results).
- `_REVIEW_CONFIDENCE_CAP = 0.4` — whenever a safety guard fires, confidence is capped here.
- `_EMAIL_RE`, `_CARD_RE`, `_PHONE_RE` — regular expressions that recognise emails, card-like
  numbers, and phone-like numbers.

## `_redact_pii(text: str) -> str`

- **What it does:** replaces any emails with `[EMAIL]`, card-like numbers with `[CARD]`, and
  phone-like numbers with `[PHONE]`.
- **Why it matters:** the customer's private data never leaves the process / never goes to
  the model. Privacy by default.

## `_EN_STOPWORDS` (a set)

- **What it is:** a hand-picked set of very English words ("the", "you", "please", ...),
  chosen to *not* overlap with Spanish/French look-alikes. Used to sanity-check the language
  detector.

## `_is_non_english(text: str) -> bool`

- **What it does:** best-effort "is this message not in English?" check.
- **How it's careful:**
  - Fewer than 2 words → returns `False` (too short to judge; other rules handle it).
  - Contains 2+ clearly-English words → treated as English (guards against the detector's
    known misfires on short text).
  - Otherwise it asks the `langdetect` library; if that library errors, it returns `False`
    ("not sure" rather than wrongly flagging).
- **Returns:** `True` only when it's reasonably confident the text isn't English.

## `_apply_review_guards(ticket, text) -> RoutedTicket`

- **What it does:** adds deterministic safety on top of the model's answer. Right now: if the
  message is non-English, it forces `needs_human_review=True` and caps confidence at 0.4 —
  *even if the model was confident.*
- **Returns:** a (possibly updated) copy of the ticket. Uses `model_copy` so it doesn't mutate
  the original.
- **Why:** a human should always confirm foreign-language routing; code enforces it rather
  than trusting the model to remember.

## `_to_dict(ticket, raw_ticket, engine, processing_ms, error) -> dict`

- **What it does:** flattens a `RoutedTicket` plus its metadata into one plain dictionary
  ready for JSON / the database.
- **What it adds beyond the routing fields:** the original `raw_ticket`, the `engine` used,
  the `prompt_version`, how long it took (`processing_ms`), and any `error` string.
- **Note:** the enum fields are turned into their plain text (`.value`) here.

## `route_ticket(raw_text: str) -> dict` — *the star function*

- **What it does:** the full, safe routing pipeline. Never raises.
- **Inputs:** `raw_text` — the raw customer message (anything, including empty or garbage).
- **Returns:** a complete dict with category, priority, team, reasoning, confidence,
  review flag, engine, prompt_version, processing_ms, and error.
- **Step by step:**
  1. Start a timer.
  2. **Empty input?** Return a safe fallback immediately — never even calls the model.
  3. **Trim** the text to `max_input_chars`, then **redact PII**.
  4. Call `route_with_llm(...)`, apply the review guards, and return the flattened dict.
  5. If the model layer raises `LLMError`, catch it and return a safe fallback (with the
     error recorded) instead of crashing.
- **In one line:** "validate → redact → time → route → guard → always return something valid."
