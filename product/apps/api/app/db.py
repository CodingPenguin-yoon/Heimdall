from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .config import Settings, get_settings


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        repo_url TEXT NOT NULL,
        default_branch TEXT NOT NULL,
        tracked_branch TEXT NOT NULL,
        deploy_mode TEXT NOT NULL,
        build_context_path TEXT NOT NULL,
        dockerfile_path TEXT,
        compose_file_path TEXT,
        container_port INTEGER NOT NULL,
        preview_host TEXT NOT NULL,
        preview_port INTEGER NOT NULL,
        preview_url TEXT NOT NULL,
        health_check_path TEXT,
        health_check_url TEXT,
        auto_deploy_enabled INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL,
        current_release_id TEXT,
        current_commit_sha TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_services (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        name TEXT NOT NULL,
        build_context_path TEXT NOT NULL,
        dockerfile_path TEXT NOT NULL,
        container_port INTEGER NOT NULL,
        is_public INTEGER NOT NULL DEFAULT 0,
        health_check_path TEXT,
        startup_order INTEGER NOT NULL DEFAULT 0,
        build_env_json TEXT NOT NULL DEFAULT '{}',
        runtime_env_json TEXT NOT NULL DEFAULT '{}',
        required_secrets_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(project_id, name),
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS port_allocations (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL UNIQUE,
        host TEXT NOT NULL,
        port INTEGER NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(host, port),
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS deployments (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        trigger_type TEXT NOT NULL,
        requested_ref TEXT,
        requested_commit_sha TEXT,
        resolved_commit_sha TEXT,
        image_tag TEXT,
        previous_release_id TEXT,
        target_release_id TEXT,
        status TEXT NOT NULL,
        status_message TEXT,
        is_dry_run INTEGER NOT NULL DEFAULT 0,
        started_at TEXT,
        finished_at TEXT,
        duration_ms INTEGER,
        log_path TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY(previous_release_id) REFERENCES releases(id),
        FOREIGN KEY(target_release_id) REFERENCES releases(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS releases (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        deployment_id TEXT NOT NULL,
        commit_sha TEXT NOT NULL,
        short_commit_sha TEXT NOT NULL,
        image_tag TEXT NOT NULL,
        image_id TEXT,
        status TEXT NOT NULL,
        is_current INTEGER NOT NULL DEFAULT 0,
        is_dry_run INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        activated_at TEXT,
        last_used_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY(deployment_id) REFERENCES deployments(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS release_services (
        id TEXT PRIMARY KEY,
        release_id TEXT NOT NULL,
        service_name TEXT NOT NULL,
        image_tag TEXT NOT NULL,
        image_id TEXT,
        container_name TEXT,
        container_port INTEGER NOT NULL,
        is_public INTEGER NOT NULL DEFAULT 0,
        preview_url TEXT,
        internal_url TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(release_id, service_name),
        FOREIGN KEY(release_id) REFERENCES releases(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS webhook_events (
        id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        event_type TEXT,
        delivery_id TEXT,
        project_id TEXT,
        branch TEXT,
        commit_sha TEXT,
        status TEXT NOT NULL,
        received_at TEXT NOT NULL,
        deployment_id TEXT,
        error_message TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL,
        FOREIGN KEY(deployment_id) REFERENCES deployments(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_webhook_registrations (
        project_id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        provider_project_id TEXT NOT NULL,
        provider_webhook_id TEXT,
        webhook_url TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT,
        active INTEGER NOT NULL DEFAULT 0,
        events TEXT NOT NULL DEFAULT '[]',
        registered_at TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_releases_current_per_project
    ON releases(project_id)
    WHERE is_current = 1
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_webhook_events_provider_delivery
    ON webhook_events(provider, delivery_id)
    WHERE delivery_id IS NOT NULL
    """,
]


def connect(settings: Settings | None = None) -> sqlite3.Connection:
    active_settings = settings or get_settings()
    connection = sqlite3.connect(active_settings.database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    active_settings.ensure_runtime_dirs()
    with connect(active_settings) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def resolve_log_path(relative_path: str, settings: Settings | None = None) -> Path:
    active_settings = settings or get_settings()
    return active_settings.runtime_dir / "logs" / relative_path
