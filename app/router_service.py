"""The reusable routing service: route_ticket().

This is the single entry point the CLI, API, and UI all call. It owns the
non-model reliability logic: guardrail pre-checks, sanitization (truncate +
PII redaction), timing, non-English review guards, and turning any failure into
a safe fallback dict — it NEVER raises.

Input safety (empty-reject, length cap, PII redaction) lives in app.guardrails.
Gibberish / not-a-ticket detection is the model's job (is_ticket=false).
"""

import re
import time

from langdetect import DetectorFactory, LangDetectException, detect

from collections.abc import Callable

from app import guardrails
from app.llm_client import LLMError, route_with_llm, route_with_llm_config
from app.prompts import PROMPT_VERSION
from app.schema import (
    MAX_ISSUES,
    TriageResult,
    all_teams,
    rejected_result,
    safe_fallback,
)

# Deterministic language detection (langdetect is random-seeded by default).
DetectorFactory.seed = 0

# Confidence ceiling applied whenever a reliability guard fires.
_REVIEW_CONFIDENCE_CAP = 0.4

# Distinctly-English function words (chosen to avoid collisions with Romance
# languages, so e.g. "me"/"a"/"no" are deliberately excluded).
_EN_STOPWORDS = frozenset(
    {
        "the", "you", "your", "our", "for", "are", "is", "and", "to", "of", "it",
        "my", "we", "can", "how", "please", "do", "does", "with", "this", "that",
        "i", "what", "where", "when", "will", "would", "should", "have", "has",
    }
)


def _is_non_english(text: str) -> bool:
    """Best-effort check: is this message not in English?

    Deterministic and precision-oriented. Guards against langdetect's known
    misfires on short text: a message containing two or more distinctly-English
    words is treated as English regardless of the detector. One-word messages
    are skipped (handled by other review rules), and a detection failure is
    treated as "not sure" rather than forcing a flag.
    """
    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    if len(tokens) < 2:
        return False
    if sum(tok in _EN_STOPWORDS for tok in tokens) >= 2:
        return False
    try:
        return detect(text) != "en"
    except LangDetectException:
        return False


def _apply_review_guards(ticket: TriageResult, text: str) -> TriageResult:
    """Force human review for cases the model tends to miss (deterministic net).

    - Non-English input on a real ticket: even a confident foreign-language route is
      confirmed by a human.
    - A ticket maxed out at MAX_ISSUES issues: it likely had extras folded in (we can't
      tell after the fact), and that many distinct issues warrants a human either way.

    Non-tickets are left untouched.
    """
    if not ticket.is_ticket:
        return ticket
    if _is_non_english(text):
        return ticket.model_copy(
            update={
                "needs_human_review": True,
                "confidence": min(ticket.confidence, _REVIEW_CONFIDENCE_CAP),
            }
        )
    if len(ticket.issues) >= MAX_ISSUES:
        return ticket.model_copy(update={"needs_human_review": True})
    return ticket


def _to_dict(
    ticket: TriageResult,
    raw_ticket: str,
    engine: str,
    processing_ms: int,
    error: str | None,
) -> dict:
    """Flatten a TriageResult plus metadata into a plain JSON-ready dict.

    Carries BOTH the full multi-issue view (issues, all_teams, primary_*) AND flat
    back-compat fields (category/priority/assigned_team/reasoning) pointed at the
    PRIMARY issue + ticket priority, so existing DB columns, filters, and UI keep
    working. For a non-ticket, all routing fields are null and issues is [].
    """
    issues = [
        {
            "category": issue.category.value,
            "priority": issue.priority.value,
            "assigned_team": issue.assigned_team.value,
            "reasoning": issue.reasoning,
        }
        for issue in ticket.issues
    ]
    idx = ticket.primary_issue_index
    primary = ticket.issues[idx] if (ticket.is_ticket and idx is not None) else None

    return {
        "raw_ticket": raw_ticket,
        "is_ticket": ticket.is_ticket,
        # Full multi-issue view.
        "issues": issues,
        "all_teams": all_teams(ticket),  # ordered unique list of concerned teams
        "primary_team": ticket.primary_team.value if ticket.primary_team else None,
        "primary_issue_index": idx,
        "primary_reasoning": primary.reasoning if primary else None,
        # Flat back-compat fields (primary issue + ticket priority).
        "category": primary.category.value if primary else None,
        "priority": ticket.priority.value if ticket.priority else None,
        "assigned_team": ticket.primary_team.value if ticket.primary_team else None,
        "reasoning": ticket.reasoning,
        # Ticket-level metadata.
        "confidence": ticket.confidence,
        "needs_human_review": ticket.needs_human_review,
        "engine": engine,
        "prompt_version": PROMPT_VERSION,
        "processing_ms": processing_ms,
        "error": error,
    }


def _route(
    raw_text: str,
    llm_fn: Callable[[str], tuple[TriageResult, str]],
) -> dict:
    """Shared routing pipeline. Never raises.

    Runs the same guardrails → LLM → review-guards → flatten path regardless of
    which model backs `llm_fn`, so the live app and the benchmark harness behave
    identically. Does NOT touch the database.
    """
    start = time.perf_counter()

    def elapsed_ms() -> int:
        return int((time.perf_counter() - start) * 1000)

    # Guardrail pre-check: reject the unambiguous cases without a model call.
    reason = guardrails.pre_check(raw_text)
    if reason:
        rejected = rejected_result(reason)
        return _to_dict(rejected, raw_text, "guardrail", elapsed_ms(), "rejected_pre_llm")

    # Sanitize (truncate + redact PII) before the text leaves the process.
    clean = guardrails.sanitize(raw_text)

    try:
        ticket, engine = llm_fn(clean)
        ticket = _apply_review_guards(ticket, clean)
        return _to_dict(ticket, raw_text, engine, elapsed_ms(), None)
    except LLMError as err:
        # A dead model must not discard a real ticket — escalate to a human.
        fallback = safe_fallback("Routing engine unavailable — escalated to a human.")
        return _to_dict(fallback, raw_text, "fallback", elapsed_ms(), str(err))


def route_ticket(raw_text: str) -> dict:
    """Route one support message using the ACTIVE provider/model. Never raises.

    Output dict always carries is_ticket + the full multi-issue view. A non-ticket
    (gibberish/empty) has null routing fields and is NOT meant to be stored.
    """
    return _route(raw_text, route_with_llm)


def route_ticket_with(raw_text: str, provider: str, model: str) -> dict:
    """Route using a SPECIFIC provider/model (benchmark harness). Never raises.

    Same pipeline and output shape as route_ticket(); only the model differs. A
    missing OpenAI key surfaces as a fallback dict (engine="fallback"), not a crash.
    """
    return _route(raw_text, lambda text: route_with_llm_config(text, provider, model))
