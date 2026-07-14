"""The data contract: what a triage result must look like.

Enums make invalid values impossible — the model cannot return a category,
priority, or team that isn't on these lists. The contract is STRICT: unknown
keys are rejected (extra="forbid"), and a self-contradictory result (e.g.
is_ticket=false but a category set) fails validation, so the client treats it
as a bad response and repairs or falls back.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Category(str, Enum):
    """The fixed set of ticket categories."""

    BILLING = "Billing & Payments"
    ACCOUNT = "Account & Access"
    HOWTO = "How-To / Usage"
    BUG = "Bug & Outage"
    FEATURE = "Feature Request"
    GENERAL = "General / Other"


class Priority(str, Enum):
    """How urgent a ticket is, judged by business impact."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Team(str, Enum):
    """The fixed set of teams a ticket can be assigned to."""

    BILLING = "Billing Team"
    ACCOUNT_MGMT = "Account Management"
    CUSTOMER_SUPP = "Customer Support"
    PRODUCT = "Product"
    FRONTEND = "Frontend / UI-UX"
    BACKEND = "Backend / API"
    DEVOPS = "DevOps / Infrastructure"


class TriageResult(BaseModel):
    """The validated result of triaging one message.

    `is_ticket` is the gate: a genuine support request is classified (all routing
    fields set); anything gibberish/spam/not-a-request is rejected (routing fields
    stay null and it is never stored).
    """

    # STRICT: reject unknown keys outright — a stray field means a bad response.
    model_config = ConfigDict(extra="forbid")

    is_ticket: bool = Field(
        description="False when the message is gibberish / not a real support request."
    )
    category: Category | None = Field(
        default=None, description="Issue category — null for a non-ticket."
    )
    priority: Priority | None = Field(
        default=None, description="Urgency by business impact — null for a non-ticket."
    )
    assigned_team: Team | None = Field(
        default=None, description="Owning team — null for a non-ticket."
    )
    reasoning: str = Field(
        max_length=200,
        description="One-line explanation of the classification or rejection.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="How sure the router is, from 0.0 (guess) to 1.0 (certain).",
    )
    needs_human_review: bool = Field(
        description="True when a person should double-check this routing."
    )

    @model_validator(mode="after")
    def _check_consistency(self) -> "TriageResult":
        """Routing fields must be all-set for a ticket, all-null for a non-ticket."""
        routing = (self.category, self.priority, self.assigned_team)
        if self.is_ticket and any(field is None for field in routing):
            raise ValueError(
                "is_ticket is true but category/priority/assigned_team is missing."
            )
        if not self.is_ticket and any(field is not None for field in routing):
            raise ValueError(
                "is_ticket is false but a category/priority/assigned_team was set."
            )
        return self


def safe_fallback(reason: str) -> TriageResult:
    """Return a valid *ticket* result when routing fails.

    A model outage must NEVER discard a real ticket. This escalates it to a human
    (is_ticket=True, General / Medium / Customer Support, flagged for review).
    """
    return TriageResult(
        is_ticket=True,
        category=Category.GENERAL,
        priority=Priority.MEDIUM,
        assigned_team=Team.CUSTOMER_SUPP,
        reasoning=reason[:200],
        confidence=0.0,
        needs_human_review=True,
    )


def rejected_result(reason: str) -> TriageResult:
    """Return a valid *non-ticket* result (gibberish / not a support request).

    Routing fields stay null; the caller will show only the reasoning and will
    NOT store it in the database.
    """
    return TriageResult(
        is_ticket=False,
        category=None,
        priority=None,
        assigned_team=None,
        reasoning=reason[:200],
        confidence=0.0,
        needs_human_review=False,
    )
