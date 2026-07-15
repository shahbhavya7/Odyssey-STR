"""Provider-agnostic LLM client with retry, repair, and a mock fallback.

Both Ollama and OpenAI are driven through the same `openai` SDK Ollama exposes
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


def _make_client_for(provider: str, api_key: str | None = None) -> OpenAI:
    """Build an OpenAI-SDK client for a specific provider.

    All three providers speak the OpenAI wire format: Groq and Ollama via a custom
    base_url, OpenAI via the default endpoint. Groq is the default provider.
    """
    if provider == "groq":
        key = api_key or settings.groq_api_key
        if not key:
            raise LLMError("Groq API key missing set GROQ_API_KEY in .env.")
        return OpenAI(base_url=settings.groq_base_url, api_key=key)
    if provider == "ollama":
        # Ollama ignores the key but the SDK requires a non-empty string.
        return OpenAI(base_url=settings.ollama_base_url, api_key="ollama")
    key = api_key or settings.openai_api_key
    if not key:
        raise LLMError("OpenAI API key missing set OPENAI_API_KEY in .env.")
    return OpenAI(api_key=key)


def _make_client() -> OpenAI:
    """Build an OpenAI-SDK client pointed at the active provider (from settings)."""
    return _make_client_for(settings.provider)


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


def _run_route_loop(
    ticket_text: str,
    client: OpenAI,
    model: str,
    engine_name: str,
    max_retries: int,
    temperature: float | None,
) -> tuple[TriageResult, str]:
    """The shared retry+repair loop. Talks to one client/model; raises LLMError.

    This is the ONLY place the prompt is sent and the response validated, so the
    live app and the benchmark harness share exactly one code path. `temperature`
    is omitted from the request when None (some models only accept their default).
    """
    messages = build_messages(ticket_text)
    last_error = "unknown error"

    # One initial attempt plus up to max_retries additional attempts.
    for attempt in range(max_retries + 1):
        try:
            kwargs: dict = {
                "model": model,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
            if temperature is not None:
                kwargs["temperature"] = temperature
            response = client.chat.completions.create(**kwargs)
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

        if attempt < max_retries:
            time.sleep(1.5 * (attempt + 1))

    raise LLMError(f"Model failed after {max_retries + 1} attempts: {last_error}")


def route_with_llm(ticket_text: str) -> tuple[TriageResult, str]:
    """Route one ticket through the ACTIVE provider/model (from settings).

    Returns (TriageResult, engine_name). Uses the offline mock when configured.
    """
    if settings.use_mock:
        return _mock_route(ticket_text), "mock"
    return _run_route_loop(
        ticket_text,
        _make_client(),
        settings.active_model,
        f"{settings.provider}:{settings.active_model}",
        settings.max_retries,
        settings.temperature,
    )


def route_with_llm_config(
    ticket_text: str, provider: str, model: str, api_key: str | None = None
) -> tuple[TriageResult, str]:
    """Route through a SPECIFIC provider/model (for the benchmark harness).

    Reuses the same prompt + validation + retry/repair path as the live app; only
    the client/model differ. Raises LLMError (e.g. missing OpenAI key) so the caller
    can record a clean miss. gpt-5* models only accept their default temperature, so
    it is omitted for them.
    """
    temperature: float | None = settings.temperature
    if provider == "openai" and model.startswith("gpt-5"):
        temperature = None
    client = _make_client_for(provider, api_key)
    return _run_route_loop(
        ticket_text, client, model, f"{provider}:{model}", settings.max_retries, temperature
    )


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

    Not smart just enough to keep the whole app runnable offline. Extremely short
    input is treated as a non-ticket; ambiguous or unmatched input is flagged for
    review. (Real gibberish detection is the live model's job see app/prompts.py.)
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
            reasoning="Hello! Happy to help tell us what you need and we'll route it.",
            confidence=0.0,
            needs_human_review=False,
        )
    # Single-issue result. (The mock never splits real multi-issue is the model's job.)
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
__all__ = ["route_with_llm", "route_with_llm_config", "LLMError", "PROMPT_VERSION"]
