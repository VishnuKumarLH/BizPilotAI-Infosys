"""Milestone 4 automation workflow templates and jobs tables.

Revision ID: e4f8b9c2d102
Revises: c8f7e2b4a901
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e4f8b9c2d102"
down_revision = "c8f7e2b4a901"
branch_labels = None
depends_on = None

JSON_TYPE = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
)


def upgrade():
    op.create_table(
        "workflow_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.String(length=50), nullable=False, server_default="schedule"),
        sa.Column("agent_sequence", JSON_TYPE, nullable=False),
        sa.Column("parameters", JSON_TYPE, nullable=False),
        sa.Column("schedule", sa.String(length=100), nullable=True),
        sa.Column("webhook_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_template_user_active", "workflow_templates", ["user_id", "is_active"], unique=False
    )
    op.create_index(op.f("ix_workflow_templates_user_id"), "workflow_templates", ["user_id"], unique=False)

    op.create_table(
        "workflow_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result", JSON_TYPE, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("trigger_source", sa.String(length=50), nullable=False, server_default="api"),
        sa.Column("webhook_url", sa.String(length=500), nullable=True),
        sa.Column("webhook_status", sa.String(length=50), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["workflow_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_jobs_job_id"), "workflow_jobs", ["job_id"], unique=True)
    op.create_index(op.f("ix_workflow_jobs_template_id"), "workflow_jobs", ["template_id"], unique=False)
    op.create_index(op.f("ix_workflow_jobs_user_id"), "workflow_jobs", ["user_id"], unique=False)
    op.create_index("ix_job_user_status", "workflow_jobs", ["user_id", "status"], unique=False)
    op.create_index("ix_job_created_at", "workflow_jobs", ["created_at"], unique=False)

    with op.batch_alter_table("agent_execution_log", schema=None) as batch_op:
        batch_op.alter_column("message_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    with op.batch_alter_table("agent_execution_log", schema=None) as batch_op:
        batch_op.alter_column("message_id", existing_type=sa.Integer(), nullable=False)

    op.drop_table("workflow_jobs")
    op.drop_table("workflow_templates")
