"""Request/response shapes for the HTTP API.

These are the API's public contract, kept separate from the internal TriageResult
and the ORM model so the wire format can evolve independently of the storage layer.
"""

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    """Incoming body for POST /tickets."""

    text: str = Field(
        min_length=1,
        description="The raw customer support message to route.",
    )


class IssueOut(BaseModel):
    """One distinct issue inside a ticket."""

    category: str
    priority: str
    assigned_team: str
    reasoning: str


class TicketOut(BaseModel):
    """One routed+saved ticket, mirroring Ticket.to_dict()."""

    # Read values straight off ORM Ticket objects.
    model_config = ConfigDict(from_attributes=True)

    id: int
    raw_ticket: str
    category: str
    priority: str
    assigned_team: str
    reasoning: str
    confidence: float
    needs_human_review: bool
    engine: str
    prompt_version: str
    processing_ms: int
    error: str | None
    # Multi-issue view (flat fields above stay pointed at the primary issue).
    issues: list[IssueOut] = []
    all_teams: list[str] = []
    primary_team: str | None = None
    primary_issue_index: int | None = None
    human_verdict: str | None
    created_at: str
    duplicate: bool = Field(
        default=False,
        description="True when this row already existed and was returned as-is "
        "(the submitted text was an exact duplicate).",
    )


class TriageOut(BaseModel):
    """Response for POST /tickets — covers BOTH a stored ticket and a rejection.

    A non-ticket (gibberish) is returned with stored=false, is_ticket=false, and null
    routing fields — the UI renders reasoning only and nothing is written to the DB.
    """

    stored: bool = Field(description="True when a row was created/matched in the DB.")
    is_ticket: bool = Field(description="False when the message was rejected as a non-ticket.")
    duplicate: bool = Field(
        default=False, description="True when an identical ticket already existed."
    )

    id: int | None = None
    raw_ticket: str
    category: str | None = None
    priority: str | None = None
    assigned_team: str | None = None
    reasoning: str
    confidence: float
    needs_human_review: bool
    engine: str
    prompt_version: str
    processing_ms: int
    error: str | None = None
    # Multi-issue view.
    issues: list[IssueOut] = []
    all_teams: list[str] = []
    primary_team: str | None = None
    primary_issue_index: int | None = None
    primary_reasoning: str | None = None
    human_verdict: str | None = None
    created_at: str | None = None


class TicketListOut(BaseModel):
    """Response for GET /tickets."""

    count: int
    items: list[TicketOut]


class HealthOut(BaseModel):
    """Response for GET /health."""

    status: str
    provider: str
    model: str
    db_ok: bool
    db_kind: str
