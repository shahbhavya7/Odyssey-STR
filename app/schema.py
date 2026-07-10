"""The data contract: what a routed ticket must look like.

Enums make invalid values impossible — the model cannot return a category,
priority, or team that isn't on these lists.
"""

from enum import Enum

from pydantic import BaseModel, Field


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


class RoutedTicket(BaseModel):
    """The validated result of routing one support ticket."""

    category: Category = Field(
        description="Which kind of issue this ticket is about."
    )
    priority: Priority = Field(
        description="Urgency by business impact: High, Medium, or Low."
    )
    assigned_team: Team = Field(
        description="The team that should handle this ticket."
    )
    reasoning: str = Field(
        max_length=200,
        description="One-line explanation of why it was routed this way.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="How sure the router is, from 0.0 (guess) to 1.0 (certain).",
    )
    needs_human_review: bool = Field(
        description="True when a person should double-check this routing."
    )


def safe_fallback(reason: str) -> RoutedTicket:
    """Return a valid escalation result when routing fails.

    Guarantees the service always produces a usable RoutedTicket, even on
    garbage input or a dead model — it just flags it for a human.
    """
    return RoutedTicket(
        category=Category.GENERAL,
        priority=Priority.MEDIUM,
        assigned_team=Team.CUSTOMER_SUPP,
        reasoning=reason[:200],
        confidence=0.0,
        needs_human_review=True,
    )
