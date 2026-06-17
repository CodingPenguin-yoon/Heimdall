from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Union

from .config import Settings, get_settings

try:  # psycopg is required only when HEIMDALL_DATABASE_URL targets PostgreSQL.
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - exercised only in environments without optional dependency installed.
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]


DATABASE_INTEGRITY_ERRORS: tuple[type[BaseException], ...] = (sqlite3.IntegrityError,)
if psycopg is not None:
    DATABASE_INTEGRITY_ERRORS = (*DATABASE_INTEGRITY_ERRORS, psycopg.IntegrityError)


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
    CREATE TABLE IF NOT EXISTS project_databases (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        database_name TEXT NOT NULL,
        role_name TEXT NOT NULL,
        password_secret_ref TEXT NOT NULL,
        app_host TEXT NOT NULL,
        app_port INTEGER NOT NULL,
        network_name TEXT NOT NULL,
        status TEXT NOT NULL,
        retention_policy TEXT NOT NULL,
        orphaned_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        provisioned_at TEXT,
        last_error TEXT,
        UNIQUE(project_id),
        UNIQUE(database_name),
        UNIQUE(role_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_database_bindings (
        id TEXT PRIMARY KEY,
        project_database_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        service_id TEXT,
        env_var_name TEXT NOT NULL,
        required_secret_name TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(project_id, service_id, env_var_name),
        FOREIGN KEY(project_database_id) REFERENCES project_databases(id) ON DELETE CASCADE,
        FOREIGN KEY(service_id) REFERENCES project_services(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_service_env_bundles (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        service_id TEXT NOT NULL,
        active_ref TEXT NOT NULL,
        key_names_json TEXT NOT NULL DEFAULT '[]',
        checksum_sha256 TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(project_id, service_id),
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY(service_id) REFERENCES project_services(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_service_volumes (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        service_id TEXT NOT NULL,
        service_display_name_snapshot TEXT NOT NULL,
        name TEXT NOT NULL,
        target_path TEXT NOT NULL,
        read_only INTEGER NOT NULL DEFAULT 0,
        source_relative_path TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(project_id, service_id, name),
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS release_service_volume_mounts (
        id TEXT PRIMARY KEY,
        release_id TEXT NOT NULL,
        release_service_id TEXT,
        project_id TEXT NOT NULL,
        service_id TEXT NOT NULL,
        project_service_volume_id TEXT NOT NULL,
        service_display_name_snapshot TEXT NOT NULL,
        volume_name_snapshot TEXT NOT NULL,
        target_path TEXT NOT NULL,
        read_only INTEGER NOT NULL DEFAULT 0,
        source_relative_path TEXT NOT NULL,
        host_source_path TEXT NOT NULL,
        container_source_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(release_id, project_service_volume_id),
        FOREIGN KEY(release_id) REFERENCES releases(id) ON DELETE CASCADE,
        FOREIGN KEY(project_service_volume_id) REFERENCES project_service_volumes(id)
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

POSTGRES_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT NOT NULL,
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
        updated_at TEXT NOT NULL,
        CONSTRAINT projects_slug_unique UNIQUE (slug)
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
        CONSTRAINT project_services_project_name_unique UNIQUE(project_id, name),
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_databases (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        database_name TEXT NOT NULL,
        role_name TEXT NOT NULL,
        password_secret_ref TEXT NOT NULL,
        app_host TEXT NOT NULL,
        app_port INTEGER NOT NULL,
        network_name TEXT NOT NULL,
        status TEXT NOT NULL,
        retention_policy TEXT NOT NULL,
        orphaned_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        provisioned_at TEXT,
        last_error TEXT,
        CONSTRAINT project_databases_project_id_unique UNIQUE(project_id),
        CONSTRAINT project_databases_database_name_unique UNIQUE(database_name),
        CONSTRAINT project_databases_role_name_unique UNIQUE(role_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_database_bindings (
        id TEXT PRIMARY KEY,
        project_database_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        service_id TEXT,
        env_var_name TEXT NOT NULL,
        required_secret_name TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CONSTRAINT project_database_bindings_project_service_env_unique UNIQUE(project_id, service_id, env_var_name),
        FOREIGN KEY(project_database_id) REFERENCES project_databases(id) ON DELETE CASCADE,
        FOREIGN KEY(service_id) REFERENCES project_services(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_service_env_bundles (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        service_id TEXT NOT NULL,
        active_ref TEXT NOT NULL,
        key_names_json TEXT NOT NULL DEFAULT '[]',
        checksum_sha256 TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CONSTRAINT project_service_env_bundles_project_service_unique UNIQUE(project_id, service_id),
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY(service_id) REFERENCES project_services(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_service_volumes (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        service_id TEXT NOT NULL,
        service_display_name_snapshot TEXT NOT NULL,
        name TEXT NOT NULL,
        target_path TEXT NOT NULL,
        read_only INTEGER NOT NULL DEFAULT 0,
        source_relative_path TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CONSTRAINT project_service_volumes_project_service_name_unique UNIQUE(project_id, service_id, name),
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS port_allocations (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        host TEXT NOT NULL,
        port INTEGER NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CONSTRAINT port_allocations_project_id_unique UNIQUE(project_id),
        CONSTRAINT port_allocations_host_port_unique UNIQUE(host, port),
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
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
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
        CONSTRAINT release_services_release_service_name_unique UNIQUE(release_id, service_name),
        FOREIGN KEY(release_id) REFERENCES releases(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS release_service_volume_mounts (
        id TEXT PRIMARY KEY,
        release_id TEXT NOT NULL,
        release_service_id TEXT,
        project_id TEXT NOT NULL,
        service_id TEXT NOT NULL,
        project_service_volume_id TEXT NOT NULL,
        service_display_name_snapshot TEXT NOT NULL,
        volume_name_snapshot TEXT NOT NULL,
        target_path TEXT NOT NULL,
        read_only INTEGER NOT NULL DEFAULT 0,
        source_relative_path TEXT NOT NULL,
        host_source_path TEXT NOT NULL,
        container_source_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        CONSTRAINT release_volume_mounts_release_volume_unique UNIQUE(release_id, project_service_volume_id),
        FOREIGN KEY(release_id) REFERENCES releases(id) ON DELETE CASCADE,
        FOREIGN KEY(project_service_volume_id) REFERENCES project_service_volumes(id)
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


def adapt_qmark_placeholders(statement: str) -> str:
    result: list[str] = []
    index = 0
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False

    while index < len(statement):
        char = statement[index]
        next_char = statement[index + 1] if index + 1 < len(statement) else ""

        if in_line_comment:
            result.append(char)
            if char == "\n":
                in_line_comment = False
            index += 1
            continue

        if in_block_comment:
            result.append(char)
            if char == "*" and next_char == "/":
                result.append(next_char)
                in_block_comment = False
                index += 2
            else:
                index += 1
            continue

        if in_single_quote:
            result.append(char)
            if char == "'" and next_char == "'":
                result.append(next_char)
                index += 2
            else:
                if char == "'":
                    in_single_quote = False
                index += 1
            continue

        if in_double_quote:
            result.append(char)
            if char == '"' and next_char == '"':
                result.append(next_char)
                index += 2
            else:
                if char == '"':
                    in_double_quote = False
                index += 1
            continue

        if char == "-" and next_char == "-":
            result.extend((char, next_char))
            in_line_comment = True
            index += 2
            continue

        if char == "/" and next_char == "*":
            result.extend((char, next_char))
            in_block_comment = True
            index += 2
            continue

        if char == "'":
            result.append(char)
            in_single_quote = True
        elif char == '"':
            result.append(char)
            in_double_quote = True
        elif char == "?":
            result.append("%s")
        else:
            result.append(char)
        index += 1

    return "".join(result)


class PostgresConnection:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def __enter__(self) -> "PostgresConnection":
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> object:
        return self._connection.__exit__(exc_type, exc, traceback)

    def execute(self, statement: str, parameters: object | None = None) -> Any:
        return self._connection.execute(adapt_qmark_placeholders(statement), parameters)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


DBConnection = Union[sqlite3.Connection, PostgresConnection]
DBRow = Union[sqlite3.Row, dict[str, Any]]


def _drop_legacy_child_indexes(connection: DBConnection) -> None:
    connection.execute("DROP INDEX IF EXISTS idx_project_services_one_child_per_project")


def _schema_statements(settings: Settings) -> list[str]:
    if settings.is_postgres_database:
        return POSTGRES_SCHEMA_STATEMENTS
    return SCHEMA_STATEMENTS


def connect(settings: Settings | None = None) -> DBConnection:
    active_settings = settings or get_settings()
    if active_settings.is_postgres_database:
        if psycopg is None or dict_row is None:
            raise RuntimeError("PostgreSQL database URLs require psycopg to be installed.")
        return PostgresConnection(psycopg.connect(active_settings.database_url, row_factory=dict_row))

    connection = sqlite3.connect(active_settings.database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    active_settings.ensure_runtime_dirs()
    with connect(active_settings) as connection:
        for statement in _schema_statements(active_settings):
            connection.execute(statement)
        _drop_legacy_child_indexes(connection)


def row_to_dict(row: DBRow | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return {key: row[key] for key in row.keys()}


def is_unique_constraint_violation(
    exc: BaseException,
    *,
    constraint_names: set[str],
    sqlite_fragments: set[str],
) -> bool:
    if isinstance(exc, sqlite3.IntegrityError):
        message = str(exc).lower()
        return any(fragment.lower() in message for fragment in sqlite_fragments)

    if psycopg is not None and isinstance(exc, psycopg.IntegrityError):
        if getattr(exc, "sqlstate", None) != "23505":
            return False
        diag = getattr(exc, "diag", None)
        constraint_name = getattr(diag, "constraint_name", None)
        return constraint_name in constraint_names

    return False


def resolve_log_path(relative_path: str, settings: Settings | None = None) -> Path:
    active_settings = settings or get_settings()
    return active_settings.runtime_dir / "logs" / relative_path
