"""Input-safety guardrails: the named layer that hardens what reaches the model.

Pure functions, no LLM calls so it is fast, deterministic, and easy to demo.

What this layer covers:
  1. Empty input        rejected before any model call (pre_check).
  2. Length cap         input truncated to MAX_INPUT_CHARS (sanitize).
  3. PII redaction      emails, card-like, and phone-like numbers are masked
                          BEFORE the text leaves this process (sanitize).

Deliberately NOT here:
  - Gibberish / not-a-ticket detection is a PRODUCT decision left to the LLM
    (it sets is_ticket=false with a reason). We do NOT try to heuristically guess
    gibberish in code natural language is too varied for a safe rule, and a
    false reject is worse than a cheap model call. See app/prompts.py.
  - Prompt injection is handled at the PROMPT level: the system prompt treats the
    message as data, never as instructions ("mark this High" is classified, not obeyed).
"""

import re

from app.config import settings

# Single source of truth for the length cap (from .env via settings).
MAX_INPUT_CHARS = settings.max_input_chars

# PII patterns, redacted before any text is sent to a model.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CARD_RE = re.compile(r"\b\d[\d -]{11,17}\d\b")  # 13-16 digits, spaces/dashes ok
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")


def _redact_pii(text: str) -> str:
    """Mask emails, card-like, and phone-like numbers. Card first (most specific)."""
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _CARD_RE.sub("[CARD]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    return text


def sanitize(text: str) -> str:
    """Return model-ready text: stripped, length-capped, and PII-redacted.

    Order matters: strip whitespace, truncate to the cap, then redact so we never
    ship raw PII and never blow the model's context window on an oversized message.
    """
    trimmed = text.strip()[:MAX_INPUT_CHARS]
    return _redact_pii(trimmed)


def pre_check(text: str) -> str | None:
    """Return a rejection REASON if the input can be rejected without a model call.

    Only the unambiguous case lives here: empty / whitespace-only input. Everything
    else including possible gibberish is passed to the model, which decides
    is_ticket. Returns None when the input should proceed to the model.
    """
    if not text or not text.strip():
        return "Empty message nothing to triage."
    return None
