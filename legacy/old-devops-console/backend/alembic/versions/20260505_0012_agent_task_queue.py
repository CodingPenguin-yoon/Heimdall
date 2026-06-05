"""Add agent task queue table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260505_0012"
down_revision = "20260504_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "agent_tasks" in existing_tables:
        return

    op.create_table(
        "agent_tasks",
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("agent_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("assigned_worker_id", sa.String(length=64), nullable=True),
        sa.Column("repo_url", sa.Text(), nullable=False),
        sa.Column("target_ref", sa.String(length=255), nullable=False),
        sa.Column("workspace_action_request_json", sa.JSON(), nullable=False),
        sa.Column("workspace_action_contract_json", sa.JSON(), nullable=False),
        sa.Column("labels_json", sa.JSON(), nullable=False),
        sa.Column("required_capabilities", sa.JSON(), nullable=False),
        sa.Column("allocation_status", sa.String(length=64), nullable=False, server_default="queued"),
        sa.Column("needs_review_reason", sa.Text(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_worker_id"],
            ["agent_workers.worker_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("task_id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "agent_tasks" in existing_tables:
        op.drop_table("agent_tasks")
