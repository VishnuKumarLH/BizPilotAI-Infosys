"""Milestone 3 agent coordination and memory tables.

Revision ID: 9b4f2a1d7c30
Revises: 6632024d16ff
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "9b4f2a1d7c30"
down_revision = "6632024d16ff"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
)


def upgrade():
    with op.batch_alter_table("agent_execution_log", schema=None) as batch_op:
        batch_op.add_column(sa.Column("workflow_id", sa.String(length=36), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_agent_execution_log_workflow_id"),
            ["workflow_id"],
            unique=False,
        )

    op.create_table(
        "agent_workflow_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("user_query", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("plan_json", JSON_TYPE, nullable=False),
        sa.Column("evidence_json", JSON_TYPE, nullable=False),
        sa.Column("analysis_json", JSON_TYPE, nullable=False),
        sa.Column("decision_json", JSON_TYPE, nullable=False),
        sa.Column("final_response", sa.Text(), nullable=False),
        sa.Column("agents_used_json", JSON_TYPE, nullable=False),
        sa.Column("tools_used_json", JSON_TYPE, nullable=False),
        sa.Column("provider_used", sa.String(length=30), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("warnings_json", JSON_TYPE, nullable=False),
        sa.Column("errors_json", JSON_TYPE, nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id"),
    )
    with op.batch_alter_table("agent_workflow_runs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_agent_workflow_runs_intent"), ["intent"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_agent_workflow_runs_session_id"),
            ["session_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_agent_workflow_runs_status"), ["status"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_agent_workflow_runs_user_id"), ["user_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_agent_workflow_runs_workflow_id"),
            ["workflow_id"],
            unique=True,
        )
        batch_op.create_index(
            "ix_workflow_user_started", ["user_id", "started_at"], unique=False
        )

    op.create_table(
        "agent_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("memory_type", sa.String(length=50), nullable=False),
        sa.Column("memory_key", sa.String(length=120), nullable=False),
        sa.Column("intent", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("tags", JSON_TYPE, nullable=False),
        sa.Column("source_workflow_id", sa.String(length=36), nullable=True),
        sa.Column("importance_score", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id", "memory_type", "memory_key", name="uq_memory_business_key"
        ),
    )
    with op.batch_alter_table("agent_memories", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_agent_memories_business_id"),
            ["business_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_agent_memories_intent"), ["intent"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_agent_memories_memory_type"),
            ["memory_type"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_agent_memories_source_workflow_id"),
            ["source_workflow_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_memory_business_updated", ["business_id", "updated_at"], unique=False
        )

    op.create_table(
        "tool_call_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("input_data", JSON_TYPE, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("output_summary", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("tool_call_logs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_tool_call_logs_tool_name"),
            ["tool_name"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_tool_call_logs_user_id"), ["user_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_tool_call_logs_workflow_id"),
            ["workflow_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_tool_workflow_created", ["workflow_id", "created_at"], unique=False
        )


def downgrade():
    with op.batch_alter_table("tool_call_logs", schema=None) as batch_op:
        batch_op.drop_index("ix_tool_workflow_created")
        batch_op.drop_index(batch_op.f("ix_tool_call_logs_workflow_id"))
        batch_op.drop_index(batch_op.f("ix_tool_call_logs_user_id"))
        batch_op.drop_index(batch_op.f("ix_tool_call_logs_tool_name"))
    op.drop_table("tool_call_logs")

    with op.batch_alter_table("agent_memories", schema=None) as batch_op:
        batch_op.drop_index("ix_memory_business_updated")
        batch_op.drop_index(batch_op.f("ix_agent_memories_source_workflow_id"))
        batch_op.drop_index(batch_op.f("ix_agent_memories_memory_type"))
        batch_op.drop_index(batch_op.f("ix_agent_memories_intent"))
        batch_op.drop_index(batch_op.f("ix_agent_memories_business_id"))
    op.drop_table("agent_memories")

    with op.batch_alter_table("agent_workflow_runs", schema=None) as batch_op:
        batch_op.drop_index("ix_workflow_user_started")
        batch_op.drop_index(batch_op.f("ix_agent_workflow_runs_workflow_id"))
        batch_op.drop_index(batch_op.f("ix_agent_workflow_runs_user_id"))
        batch_op.drop_index(batch_op.f("ix_agent_workflow_runs_status"))
        batch_op.drop_index(batch_op.f("ix_agent_workflow_runs_session_id"))
        batch_op.drop_index(batch_op.f("ix_agent_workflow_runs_intent"))
    op.drop_table("agent_workflow_runs")

    with op.batch_alter_table("agent_execution_log", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_execution_log_workflow_id"))
        batch_op.drop_column("workflow_id")
