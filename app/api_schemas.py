"""Request/response shapes for the HTTP API.

These are the API's public contract, kept separate from the internal RoutedTicket
and the ORM model so the wire format can evolve independently of the storage layer.
"""

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    """Incoming body for POST /tickets."""

    text: str = Field(
        min_length=1,
        description="The raw customer support message to route.",
    )


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
    human_verdict: str | None
    created_at: str


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
