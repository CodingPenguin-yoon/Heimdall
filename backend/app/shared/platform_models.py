"""SQLAlchemy models for platform-state persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.platform_db import Base


class PlatformMetadata(Base):
    """Key/value metadata for platform-state migrations and markers."""

    __tablename__ = "platform_metadata"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class GitLabProject(Base):
    """Persisted GitLab project inventory."""

    __tablename__ = "gitlab_projects"

    gitlab_project_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path_with_namespace: Mapped[str] = mapped_column(String(512), nullable=False)
    web_url: Mapped[str] = mapped_column(Text, nullable=False)
    http_url_to_repo: Mapped[str] = mapped_column(Text, nullable=False)
    ssh_url_to_repo: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="private")
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_activity_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[str] = mapped_column(Text, nullable=False)


class GitLabProjectSettings(Base):
    """Platform-owned per-project settings separate from sync-owned inventory rows."""

    __tablename__ = "gitlab_project_settings"

    gitlab_project_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staging_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ready_for_bootstrap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    database_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    database_engine: Mapped[str | None] = mapped_column(String(32), nullable=True)
    database_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    migration_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    deploy_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    bootstrap_strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="merge_request")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class PlatformTask(Base):
    """Persisted task summary."""

    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    progress_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    progress_source: Mapped[str] = mapped_column(Text, nullable=False, default="")
    archived: Mapped[bool] = mapped_column(nullable=False, default=False)
    archived_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    logs: Mapped[list["PlatformTaskLog"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PlatformTaskLog.line_no",
    )


class PlatformTaskLog(Base):
    """Persisted task log line."""

    __tablename__ = "task_logs"

    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.task_id", ondelete="CASCADE"),
        primary_key=True,
    )
    line_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    log_line: Mapped[str] = mapped_column(Text, nullable=False)

    task: Mapped[PlatformTask] = relationship(back_populates="logs")
