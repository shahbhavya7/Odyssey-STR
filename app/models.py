"""The `Ticket` ORM table model.

One row = one routed ticket. Columns mirror the flattened dict returned by
route_ticket(), plus a couple of metadata/Stage-B columns. Uses SQLAlchemy 2.0
Mapped / mapped_column style and reuses the shared Base from app.db.
"""

from datetime import datetime

from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Ticket(Base):
    """A persisted routing result."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_ticket: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)
    assigned_team: Mapped[str] = mapped_column(String, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    needs_human_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    engine: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    processing_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    # Multi-issue (v1.4). Flat columns above hold the PRIMARY issue + ticket priority
    # so existing queries/UI keep working; these hold the full picture.
    issues: Mapped[Any | None] = mapped_column(JSON, nullable=True)  # list of {cat,pri,team,reason}
    all_teams: Mapped[str | None] = mapped_column(String, nullable=True)  # comma-joined, filterable
    primary_team: Mapped[str | None] = mapped_column(String, nullable=True)
    primary_issue_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Stage-B hook (human review loop): unused for now, avoids a later migration.
    human_verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        """Return all columns as a JSON-serializable dict (created_at as ISO text).

        `issues` comes back as a parsed list and `all_teams` as a list of team names,
        so the API/UI see the same shapes route_ticket() produces.
        """
        return {
            "id": self.id,
            "raw_ticket": self.raw_ticket,
            "category": self.category,
            "priority": self.priority,
            "assigned_team": self.assigned_team,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "needs_human_review": self.needs_human_review,
            "engine": self.engine,
            "prompt_version": self.prompt_version,
            "processing_ms": self.processing_ms,
            "error": self.error,
            "issues": self.issues or [],
            "all_teams": self.all_teams.split(",") if self.all_teams else [],
            "primary_team": self.primary_team,
            "primary_issue_index": self.primary_issue_index,
            "human_verdict": self.human_verdict,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
