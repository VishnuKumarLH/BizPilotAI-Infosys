"""Milestone 4 workflow lifecycle events.

Revision ID: c8f7e2b4a901
Revises: 9b4f2a1d7c30
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c8f7e2b4a901"
down_revision = "9b4f2a1d7c30"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
)


def upgrade():
    with op.batch_alter_table("agent_workflow_runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "lifecycle_events_json",
                JSON_TYPE,
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
    with op.batch_alter_table("agent_workflow_runs", schema=None) as batch_op:
        batch_op.alter_column("lifecycle_events_json", server_default=None)


def downgrade():
    with op.batch_alter_table("agent_workflow_runs", schema=None) as batch_op:
        batch_op.drop_column("lifecycle_events_json")
