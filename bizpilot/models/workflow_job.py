"""SQLAlchemy model for Workflow Jobs."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import JSON_TYPE, TimestampMixin, utc_now

if TYPE_CHECKING:
    from .base import User
    from .workflow_template import WorkflowTemplate


class WorkflowJob(TimestampMixin, db.Model):
    __tablename__ = "workflow_jobs"
    __table_args__ = (
        Index("ix_job_user_status", "user_id", "status"),
        Index("ix_job_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(
        db.String(36), unique=True, nullable=False, index=True
    )
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_templates.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        db.String(20), default="pending", nullable=False, index=True
    )
    progress: Mapped[int] = mapped_column(default=0, nullable=False)
    result: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(db.Text)
    trigger_source: Mapped[str] = mapped_column(
        db.String(50), default="api", nullable=False
    )
    webhook_url: Mapped[str | None] = mapped_column(db.String(500))
    webhook_status: Mapped[str | None] = mapped_column(db.String(50))
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    execution_time_ms: Mapped[int] = mapped_column(default=0, nullable=False)

    user: Mapped["User"] = relationship()
    template: Mapped["WorkflowTemplate | None"] = relationship(back_populates="jobs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "template_id": self.template_id,
            "template_name": self.template.name if self.template else None,
            "user_id": self.user_id,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "decision_summary": (
                self.result.get("final_response")
                or self.result.get("summary")
                or self.result.get("decision", {}).get("final_decision", "")
            ),
            "error_message": self.error_message,
            "trigger_source": self.trigger_source,
            "webhook_url": self.webhook_url,
            "webhook_status": self.webhook_status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "created_at": self.created_at.isoformat(),
        }
