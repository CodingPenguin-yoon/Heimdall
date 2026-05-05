"""Add agent worker registry table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260504_0011"
down_revision = "20260426_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "agent_workers" in existing_tables:
        return

    op.create_table(
        "agent_workers",
        sa.Column("worker_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("host_ip", sa.String(length=64), nullable=True),
        sa.Column("ssh_user", sa.String(length=255), nullable=True),
        sa.Column("agent_types", sa.JSON(), nullable=False),
        sa.Column("agent_auth_status", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("labels_json", sa.JSON(), nullable=False),
        sa.Column("current_task_id", sa.String(length=64), nullable=True),
        sa.Column("last_checked_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("worker_id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "agent_workers" in existing_tables:
        op.drop_table("agent_workers")
