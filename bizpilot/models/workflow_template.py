"""SQLAlchemy model for Workflow Templates."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import JSON_TYPE, TimestampMixin, utc_now

if TYPE_CHECKING:
    from .base import User
    from .workflow_job import WorkflowJob


class WorkflowTemplate(TimestampMixin, db.Model):
    __tablename__ = "workflow_templates"
    __table_args__ = (Index("ix_template_user_active", "user_id", "is_active"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(db.Text)
    trigger_type: Mapped[str] = mapped_column(
        db.String(50), default="schedule", nullable=False
    )
    agent_sequence: Mapped[list] = mapped_column(
        JSON_TYPE,
        default=lambda: [
            "planning_agent",
            "research_agent",
            "analysis_decision_agent",
            "response_agent",
        ],
        nullable=False,
    )
    parameters: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    schedule: Mapped[str | None] = mapped_column(db.String(100))
    webhook_url: Mapped[str | None] = mapped_column(db.String(500))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship()
    jobs: Mapped[list["WorkflowJob"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "trigger_type": self.trigger_type,
            "agent_sequence": self.agent_sequence,
            "parameters": self.parameters,
            "schedule": self.schedule,
            "webhook_url": self.webhook_url,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
