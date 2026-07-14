"""Provider-agnostic LLM client with retry, repair, and a mock fallback.

Both Ollama and OpenAI are driven through the same `openai` SDK — Ollama exposes
an OpenAI-compatible endpoint, so there is a single code path. The only reliability
logic that talks to a model lives here.
"""

import json
import time

from openai import OpenAI
from pydantic import ValidationError

from app.config import settings
from app.prompts import PROMPT_VERSION, build_messages
from app.schema import Category, Issue, Priority, Team, TriageResult


class LLMError(Exception):
    """Raised when the model cannot produce a valid TriageResult after retries."""


# Top-level keys the model must return; used to build the corrective repair message.
_REQUIRED_KEYS = (
    "is_ticket",
    "issues",
    "priority",
    "primary_team",
    "primary_issue_index",
    "confidence",
    "needs_human_review",
    "reasoning",
)


def _make_client() -> OpenAI:
    """Build an OpenAI-SDK client pointed at the active provider."""
    if settings.provider == "ollama":
        # Ollama ignores the key but the SDK requires a non-empty string.
        return OpenAI(base_url=settings.ollama_base_url, api_key="ollama")
    return OpenAI(api_key=settings.openai_api_key)


def _repair_message() -> dict[str, str]:
    """A corrective nudge appended after a bad/unparseable response."""
    keys = ", ".join(_REQUIRED_KEYS)
    return {
        "role": "user",
        "content": (
            f"Your previous reply was not a single valid JSON object. Return ONLY a "
            f"JSON object with exactly these top-level keys: {keys}. No extra keys, no "
            f"markdown, no backticks, no extra text. 'issues' is an array of objects, "
            f"each with exactly category, priority, assigned_team, reasoning. When "
            f"is_ticket is false, issues must be [] and priority/primary_team/"
            f"primary_issue_index null. When is_ticket is true, provide 1..5 issues, and "
            f"the ticket 'priority' MUST equal the highest issue priority (High>Medium>"
            f"Low), with primary_issue_index pointing to that issue and primary_team "
            f"equal to its assigned_team."
        ),
    }


def route_with_llm(ticket_text: str) -> tuple[TriageResult, str]:
    """Route one ticket through the model. Returns (TriageResult, engine_name).

    Retries up to settings.max_retries on network errors, empty content, JSON
    parse errors, or schema-validation errors, appending a corrective message
    after a bad response. Raises LLMError if every attempt fails.
    """
    if settings.use_mock:
        return _mock_route(ticket_text), "mock"

    engine_name = f"{settings.provider}:{settings.active_model}"
    client = _make_client()
    messages = build_messages(ticket_text)
    last_error = "unknown error"

    # One initial attempt plus up to max_retries additional attempts.
    for attempt in range(settings.max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=settings.active_model,
                messages=messages,
                temperature=settings.temperature,
                response_format={"type": "json_object"},
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("empty content from model")

            data = json.loads(content)
            # Strict validation: extra keys or a self-contradictory is_ticket/routing
            # combination raise ValidationError -> caught below -> repair/retry.
            ticket = TriageResult(**data)
            return ticket, engine_name

        except (json.JSONDecodeError, ValidationError, ValueError) as err:
            # Bad shape/content -> add a corrective message and try again.
            last_error = f"{type(err).__name__}: {err}"
            messages = messages + [_repair_message()]
        except Exception as err:  # network / API errors
            last_error = f"{type(err).__name__}: {err}"

        if attempt < settings.max_retries:
            time.sleep(1.5 * (attempt + 1))

    raise LLMError(f"Model failed after {settings.max_retries + 1} attempts: {last_error}")


# --- Mock path -----------------------------------------------------------------

# Greeting words that, on their own, mark a message as small talk (mock only).
_MOCK_GREETINGS = frozenset(
    {"hi", "hello", "hey", "hiya", "howdy", "yo", "sup", "hola", "greetings",
     "thanks", "thank", "good", "morning", "afternoon", "evening"}
)

# Ordered keyword rules: first match wins. Keeps the app usable with no model.
_MOCK_RULES: list[tuple[tuple[str, ...], Category, Priority, Team]] = [
    (("refund", "charge", "charged", "invoice", "payment", "billing", "plan"),
     Category.BILLING, Priority.HIGH, Team.BILLING),
    (("login", "log in", "password", "sign in", "locked", "2fa", "access"),
     Category.ACCOUNT, Priority.MEDIUM, Team.ACCOUNT_MGMT),
    (("down", "outage", "won't load", "wont load", "cannot load", "timing out",
      "timeout", "unavailable"),
     Category.BUG, Priority.HIGH, Team.DEVOPS),
    (("500", "api", "error", "wrong data", "not saving", "integration"),
     Category.BUG, Priority.HIGH, Team.BACKEND),
    (("button", "typo", "layout", "styling", "display", "greyed", "grayed", "ui"),
     Category.BUG, Priority.LOW, Team.FRONTEND),
    (("add ", "please add", "feature", "would be nice", "dark mode"),
     Category.FEATURE, Priority.LOW, Team.PRODUCT),
    (("how do i", "how to", "how can i"),
     Category.HOWTO, Priority.LOW, Team.CUSTOMER_SUPP),
]


def _mock_route(ticket_text: str) -> TriageResult:
    """Deterministic keyword router used when no model is available.

    Not smart — just enough to keep the whole app runnable offline. Extremely short
    input is treated as a non-ticket; ambiguous or unmatched input is flagged for
    review. (Real gibberish detection is the live model's job — see app/prompts.py.)
    """
    text = ticket_text.lower()
    if len(ticket_text.strip()) < 3:
        return TriageResult(
            is_ticket=False,
            reasoning="Mock: message too short to be a support request.",
            confidence=0.0,
            needs_human_review=False,
        )
    # Bare greeting / small talk with no request -> friendly non-ticket.
    stripped = text.strip().strip("!.?,:; ")
    first = stripped.split()[0] if stripped.split() else ""
    if len(stripped.split()) <= 4 and first in _MOCK_GREETINGS:
        return TriageResult(
            is_ticket=False,
            reasoning="Hello! Happy to help — tell us what you need and we'll route it.",
            confidence=0.0,
            needs_human_review=False,
        )
    # Single-issue result. (The mock never splits — real multi-issue is the model's job.)
    for keywords, category, priority, team in _MOCK_RULES:
        if any(kw in text for kw in keywords):
            return _single_issue(category, priority, team,
                                 "Mock keyword match (no live model).", 0.5, False)
    return _single_issue(Category.GENERAL, Priority.LOW, Team.CUSTOMER_SUPP,
                         "Mock router found no keyword match.", 0.3, True)


def _single_issue(
    category: Category,
    priority: Priority,
    team: Team,
    reasoning: str,
    confidence: float,
    review: bool,
) -> TriageResult:
    """Build a valid single-issue TriageResult (used by the mock path)."""
    return TriageResult(
        is_ticket=True,
        issues=[Issue(category=category, priority=priority,
                      assigned_team=team, reasoning=reasoning)],
        priority=priority,
        primary_team=team,
        primary_issue_index=0,
        confidence=confidence,
        needs_human_review=review,
        reasoning=reasoning,
    )


# Keep the prompt version importable alongside the client for convenience.
__all__ = ["route_with_llm", "LLMError", "PROMPT_VERSION"]
