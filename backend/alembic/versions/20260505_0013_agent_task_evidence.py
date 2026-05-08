"""Add agent task evidence tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260505_0013"
down_revision = "20260505_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "agent_task_events" not in existing_tables:
        op.create_table(
            "agent_task_events",
            sa.Column("task_id", sa.String(length=64), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
            sa.Column("source", sa.String(length=64), nullable=False, server_default="worker"),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.task_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("task_id", "sequence"),
        )

    if "agent_task_artifacts" not in existing_tables:
        op.create_table(
            "agent_task_artifacts",
            sa.Column("artifact_id", sa.String(length=64), nullable=False),
            sa.Column("task_id", sa.String(length=64), nullable=False),
            sa.Column("artifact_type", sa.String(length=32), nullable=False),
            sa.Column("relative_path", sa.Text(), nullable=False),
            sa.Column("path", sa.Text(), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column("media_type", sa.String(length=128), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("sha256", sa.String(length=64), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.task_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("task_id", "artifact_id"),
        )

    if "agent_task_verification_reports" not in existing_tables:
        op.create_table(
            "agent_task_verification_reports",
            sa.Column("report_id", sa.String(length=64), nullable=False),
            sa.Column("task_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("checks_json", sa.JSON(), nullable=False),
            sa.Column("artifact_ids", sa.JSON(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.task_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("task_id", "report_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table_name in (
        "agent_task_verification_reports",
        "agent_task_artifacts",
        "agent_task_events",
    ):
        if table_name in existing_tables:
            op.drop_table(table_name)
