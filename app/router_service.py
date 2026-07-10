"""The reusable routing service: route_ticket().

This is the single entry point the CLI, API, and UI all call. It owns the
non-model reliability logic: input validation, truncation, PII redaction,
timing, and turning any failure into a safe fallback dict — it NEVER raises.
"""

import re
import time

from app.config import settings
from app.llm_client import LLMError, route_with_llm
from app.prompts import PROMPT_VERSION
from app.schema import RoutedTicket, safe_fallback

# PII patterns, redacted before any text leaves for the model.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CARD_RE = re.compile(r"\b\d[\d -]{11,17}\d\b")  # 13-16 digits, spaces/dashes ok
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")


def _redact_pii(text: str) -> str:
    """Mask emails, card-like, and phone-like numbers before sending to a model."""
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _CARD_RE.sub("[CARD]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    return text


def _to_dict(
    ticket: RoutedTicket,
    raw_ticket: str,
    engine: str,
    processing_ms: int,
    error: str | None,
) -> dict:
    """Flatten a RoutedTicket plus metadata into a plain JSON-ready dict."""
    return {
        "raw_ticket": raw_ticket,
        "category": ticket.category.value,
        "priority": ticket.priority.value,
        "assigned_team": ticket.assigned_team.value,
        "reasoning": ticket.reasoning,
        "confidence": ticket.confidence,
        "needs_human_review": ticket.needs_human_review,
        "engine": engine,
        "prompt_version": PROMPT_VERSION,
        "processing_ms": processing_ms,
        "error": error,
    }


def route_ticket(raw_text: str) -> dict:
    """Route one support ticket to a structured result. Never raises.

    Inputs: the raw customer message.
    Output: a dict with raw_ticket, category, priority, assigned_team, reasoning,
    confidence, needs_human_review, engine, prompt_version, processing_ms, error.
    """
    start = time.perf_counter()

    def elapsed_ms() -> int:
        return int((time.perf_counter() - start) * 1000)

    # Empty input: escalate without ever calling the model.
    if not raw_text or not raw_text.strip():
        fallback = safe_fallback("Empty ticket — nothing to route.")
        return _to_dict(fallback, raw_text, "fallback", elapsed_ms(), "empty_input")

    # Truncate over-long input, then redact PII before it leaves the process.
    trimmed = raw_text[: settings.max_input_chars]
    redacted = _redact_pii(trimmed)

    try:
        ticket, engine = route_with_llm(redacted)
        return _to_dict(ticket, raw_text, engine, elapsed_ms(), None)
    except LLMError as err:
        fallback = safe_fallback("Routing engine unavailable — escalated to a human.")
        return _to_dict(fallback, raw_text, "fallback", elapsed_ms(), str(err))
