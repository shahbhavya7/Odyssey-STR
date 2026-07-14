"""The data contract: what a triage result must look like.

Enums make invalid values impossible. A ticket carries a LIST of issues (a single
issue is just a list of length 1 — one code path). Ticket-level fields summarize
the list: priority = the highest issue severity, primary_team = the owner of the
most critical issue. The contract is STRICT: unknown keys are rejected, and a
self-contradictory result (e.g. priority not matching the issues) fails validation,
so the client treats it as a bad response and repairs or falls back.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Most issues we extract from one message. Extras are folded into the most
# relevant issue and the ticket is flagged for review (never silently dropped).
MAX_ISSUES = 5


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


# Priority severity for max() comparison. Higher number = more severe.
_SEVERITY = {Priority.LOW: 1, Priority.MEDIUM: 2, Priority.HIGH: 3}


def severity_rank(priority: Priority) -> int:
    """Return the numeric severity of a priority (High=3 > Medium=2 > Low=1)."""
    return _SEVERITY[priority]


class Issue(BaseModel):
    """One distinct problem inside a ticket: its category, owning team, and reason."""

    model_config = ConfigDict(extra="forbid")

    category: Category = Field(description="Which kind of issue this is.")
    priority: Priority = Field(
        description="Business-impact severity of THIS issue (High/Medium/Low)."
    )
    assigned_team: Team = Field(description="The team that should handle this issue.")
    reasoning: str = Field(
        max_length=200, description="One-line explanation for this issue's routing."
    )


class TriageResult(BaseModel):
    """The validated result of triaging one message.

    `is_ticket` is the gate. A real ticket has 1..MAX_ISSUES issues plus ticket-level
    priority/primary_team; a non-ticket (gibberish/greeting) has an empty list and
    null ticket-level fields, and is never stored.
    """

    model_config = ConfigDict(extra="forbid")

    is_ticket: bool = Field(
        description="False when the message is gibberish / not a real support request."
    )
    issues: list[Issue] = Field(
        default_factory=list,
        description="Each distinct problem. Empty ONLY when is_ticket is false.",
    )
    priority: Priority | None = Field(
        default=None, description="Ticket priority = max issue severity. Null if not a ticket."
    )
    primary_team: Team | None = Field(
        default=None, description="Owner = team of the most critical issue. Null if not a ticket."
    )
    primary_issue_index: int | None = Field(
        default=None, description="Index of the issue that drove priority/owner."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Ticket-level confidence, 0.0 (guess) to 1.0 (certain)."
    )
    needs_human_review: bool = Field(
        description="True when a person should double-check this routing."
    )
    reasoning: str = Field(
        max_length=200, description="One short overall summary of the routing."
    )

    @model_validator(mode="after")
    def _check_consistency(self) -> "TriageResult":
        """Enforce the is_ticket contract and ticket-level/issue coherence."""
        if not self.is_ticket:
            if self.issues:
                raise ValueError("is_ticket is false but issues were provided.")
            if any(v is not None for v in (self.priority, self.primary_team,
                                           self.primary_issue_index)):
                raise ValueError("is_ticket is false but ticket-level fields were set.")
            return self

        # is_ticket is true from here on.
        if not (1 <= len(self.issues) <= MAX_ISSUES):
            raise ValueError(f"a ticket must have 1..{MAX_ISSUES} issues.")
        if self.priority is None or self.primary_team is None \
                or self.primary_issue_index is None:
            raise ValueError("a ticket must set priority, primary_team, primary_issue_index.")
        if not (0 <= self.primary_issue_index < len(self.issues)):
            raise ValueError("primary_issue_index is out of range.")

        max_sev = max(severity_rank(i.priority) for i in self.issues)
        if severity_rank(self.priority) != max_sev:
            raise ValueError("ticket priority must equal the maximum issue severity.")
        if self.primary_team != self.issues[self.primary_issue_index].assigned_team:
            raise ValueError("primary_team must equal the primary issue's assigned_team.")
        return self


def all_teams(result: TriageResult) -> list[str]:
    """Ordered, de-duplicated list of every team an issue is routed to."""
    seen: list[str] = []
    for issue in result.issues:
        value = issue.assigned_team.value
        if value not in seen:
            seen.append(value)
    return seen


def safe_fallback(reason: str) -> TriageResult:
    """Return a valid single-issue *ticket* when routing fails.

    A model outage must NEVER discard a real ticket. This escalates it to a human
    (General / Medium / Customer Support, flagged for review).
    """
    reason = reason[:200]
    return TriageResult(
        is_ticket=True,
        issues=[
            Issue(
                category=Category.GENERAL,
                priority=Priority.MEDIUM,
                assigned_team=Team.CUSTOMER_SUPP,
                reasoning=reason,
            )
        ],
        priority=Priority.MEDIUM,
        primary_team=Team.CUSTOMER_SUPP,
        primary_issue_index=0,
        confidence=0.0,
        needs_human_review=True,
        reasoning=reason,
    )


def rejected_result(reason: str) -> TriageResult:
    """Return a valid *non-ticket* result (gibberish / greeting / not a request)."""
    return TriageResult(
        is_ticket=False,
        issues=[],
        priority=None,
        primary_team=None,
        primary_issue_index=None,
        confidence=0.0,
        needs_human_review=False,
        reasoning=reason[:200],
    )
