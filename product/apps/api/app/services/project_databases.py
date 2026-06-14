from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

from ..config import Settings, get_settings
from ..db import connect, row_to_dict
from . import project_database_secrets

try:  # psycopg is optional unless managed PostgreSQL provisioning is used.
    import psycopg
    from psycopg import conninfo, sql
except ImportError:  # pragma: no cover - exercised in local environments without psycopg.
    psycopg = None  # type: ignore[assignment]
    conninfo = None  # type: ignore[assignment]
    sql = None  # type: ignore[assignment]


UTC = timezone.utc
RETRYABLE_STATUSES = {"pending", "failed", "needs_repair"}
BLOCKED_RETRY_STATUSES = {"active", "orphaned", "purged", "disabled"}
PURGEABLE_STATUSES = {"active", "disabled", "orphaned", "pending", "failed", "needs_repair", "purging", "purge_failed"}


class ProjectDatabaseProvisioningError(RuntimeError):
    pass


class ProjectDatabaseNeedsRepair(ProjectDatabaseProvisioningError):
    pass


class Connector(Protocol):
    def connect(self, dsn: str, *, autocommit: bool = False) -> Any:
        ...


@dataclass(frozen=True)
class PsycopgConnector:
    def connect(self, dsn: str, *, autocommit: bool = False) -> Any:
        if psycopg is None:
            raise RuntimeError("psycopg is required to provision managed project PostgreSQL databases.")
        return psycopg.connect(dsn, autocommit=autocommit)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def password_secret_ref(project_id: str) -> str:
    return f"project-databases/{project_id}/password"


def fetch_project_database(project_id: str, settings: Settings | None = None) -> dict[str, object] | None:
    active_settings = settings or get_settings()
    with connect(active_settings) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM project_databases
            WHERE project_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
    return row_to_dict(row)


def secret_exists(settings: Settings, row: dict[str, object]) -> bool:
    return project_database_secrets.secret_exists(settings, str(row["password_secret_ref"]))


def mark_orphaned(project_id: str, settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    timestamp = utc_now()
    with connect(active_settings) as connection:
        connection.execute(
            """
            UPDATE project_databases
            SET status = ?, orphaned_at = COALESCE(orphaned_at, ?), updated_at = ?
            WHERE project_id = ? AND status NOT IN ('orphaned', 'purged')
            """,
            ("orphaned", timestamp, timestamp, project_id),
        )


def _mark_active(project_database_id: str, settings: Settings) -> None:
    timestamp = utc_now()
    with connect(settings) as connection:
        connection.execute(
            """
            UPDATE project_databases
            SET status = ?, provisioned_at = COALESCE(provisioned_at, ?), last_error = NULL, updated_at = ?
            WHERE id = ?
            """,
            ("active", timestamp, timestamp, project_database_id),
        )


def _mark_failure(project_database_id: str, settings: Settings, status: str, message: str) -> None:
    timestamp = utc_now()
    with connect(settings) as connection:
        connection.execute(
            """
            UPDATE project_databases
            SET status = ?, last_error = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, message, timestamp, project_database_id),
        )


def _mark_purging(project_database_id: str, settings: Settings) -> None:
    timestamp = utc_now()
    with connect(settings) as connection:
        connection.execute(
            """
            UPDATE project_databases
            SET status = ?, last_error = NULL, updated_at = ?
            WHERE id = ?
            """,
            ("purging", timestamp, project_database_id),
        )


def _mark_purged(project_database_id: str, settings: Settings) -> None:
    timestamp = utc_now()
    with connect(settings) as connection:
        connection.execute(
            """
            UPDATE project_databases
            SET status = ?, last_error = NULL, updated_at = ?
            WHERE id = ?
            """,
            ("purged", timestamp, project_database_id),
        )


def _first_value(row: object) -> object | None:
    if row is None:
        return None
    if isinstance(row, dict):
        if not row:
            return None
        return next(iter(row.values()))
    try:
        return row[0]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return None


def _sql(template: str) -> Any:
    if sql is None:
        raise RuntimeError("psycopg.sql is required to provision managed project PostgreSQL databases.")
    return sql.SQL(template)


def _identifier(value: str) -> Any:
    if sql is None:
        raise RuntimeError("psycopg.sql is required to provision managed project PostgreSQL databases.")
    return sql.Identifier(value)


def _literal(value: str) -> Any:
    if sql is None:
        raise RuntimeError("psycopg.sql is required to provision managed project PostgreSQL databases.")
    return sql.Literal(value)


def _target_conninfo(admin_url: str, database_name: str) -> str:
    if conninfo is None:
        raise RuntimeError("psycopg.conninfo is required to provision managed project PostgreSQL databases.")
    return conninfo.make_conninfo(admin_url, dbname=database_name)


def _is_duplicate_error(exc: BaseException, sqlstates: set[str]) -> bool:
    return getattr(exc, "sqlstate", None) in sqlstates


def _admin_url_password(admin_url: str | None) -> str | None:
    if not admin_url:
        return None
    try:
        return urlsplit(admin_url).password
    except ValueError:
        return None


def _app_database_url(row: dict[str, object], password: str) -> str:
    role_name = quote(str(row["role_name"]), safe="")
    encoded_password = quote(password, safe="")
    database_name = quote(str(row["database_name"]), safe="")
    return f"postgresql://{role_name}:{encoded_password}@{row['app_host']}:{row['app_port']}/{database_name}"


def _error_redaction_values(settings: Settings, password: str | None, row: dict[str, object] | None) -> list[str]:
    admin_url = (settings.project_database_admin_url or "").strip()
    values = [
        admin_url,
        _admin_url_password(admin_url),
    ]
    if password:
        values.extend([password, quote(password, safe="")])
        if row is not None:
            values.append(_app_database_url(row, password))
    if admin_url and row is not None and conninfo is not None:
        try:
            values.append(_target_conninfo(admin_url, str(row["database_name"])))
        except Exception:
            pass
    return [value for value in values if value]


def _redact_error(
    message: str,
    settings: Settings,
    password: str | None,
    row: dict[str, object] | None = None,
) -> str:
    redacted = message
    for secret in _error_redaction_values(settings, password, row):
        redacted = redacted.replace(secret, "[redacted]")
    return redacted


def _role_exists(connection: Any, role_name: str) -> bool:
    cursor = connection.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role_name,))
    return _first_value(cursor.fetchone()) is not None


def _database_owner(connection: Any, database_name: str) -> str | None:
    cursor = connection.execute(
        """
        SELECT r.rolname
        FROM pg_database d
        JOIN pg_roles r ON r.oid = d.datdba
        WHERE d.datname = %s
        """,
        (database_name,),
    )
    owner = _first_value(cursor.fetchone())
    return str(owner) if owner is not None else None


def _ensure_role(connection: Any, role_name: str, password: str) -> None:
    if _role_exists(connection, role_name):
        connection.execute(
            _sql("ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                _identifier(role_name),
                _literal(password),
            )
        )
        return
    try:
        connection.execute(
            _sql("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                _identifier(role_name),
                _literal(password),
            )
        )
    except Exception as exc:
        if not _is_duplicate_error(exc, {"42710"}):
            raise
        connection.execute(
            _sql("ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                _identifier(role_name),
                _literal(password),
            )
        )


def _ensure_database(connection: Any, database_name: str, role_name: str) -> None:
    owner = _database_owner(connection, database_name)
    if owner == role_name:
        return
    if owner is not None:
        raise ProjectDatabaseNeedsRepair("Existing database is not owned by the managed project role.")

    try:
        connection.execute(
            _sql("CREATE DATABASE {} OWNER {}").format(_identifier(database_name), _identifier(role_name))
        )
    except Exception as exc:
        if not _is_duplicate_error(exc, {"42P04"}):
            raise
        owner = _database_owner(connection, database_name)
        if owner != role_name:
            raise ProjectDatabaseNeedsRepair("Existing database is not owned by the managed project role.") from exc


def _apply_database_grants(connection: Any, database_name: str, role_name: str) -> None:
    connection.execute(_sql("REVOKE CONNECT, TEMPORARY ON DATABASE {} FROM PUBLIC").format(_identifier(database_name)))
    connection.execute(
        _sql("GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}").format(
            _identifier(database_name),
            _identifier(role_name),
        )
    )


def _apply_schema_grants(connection: Any, role_name: str) -> None:
    connection.execute(_sql("REVOKE CREATE ON SCHEMA {} FROM PUBLIC").format(_identifier("public")))
    connection.execute(
        _sql("GRANT USAGE, CREATE ON SCHEMA {} TO {}").format(
            _identifier("public"),
            _identifier(role_name),
        )
    )


def _terminate_sessions(connection: Any, database_name: str, role_name: str) -> None:
    connection.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE pid <> pg_backend_pid()
          AND (datname = %s OR usename = %s)
        """,
        (database_name, role_name),
    )


def _database_session_count(connection: Any, database_name: str) -> int:
    cursor = connection.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE datname = %s", (database_name,))
    value = _first_value(cursor.fetchone())
    return int(value or 0)


def _run_postgres_purge(
    row: dict[str, object],
    *,
    settings: Settings,
    connector: Connector,
) -> None:
    admin_url, _, _, _ = settings.require_project_database_settings()
    database_name = str(row["database_name"])
    role_name = str(row["role_name"])

    with connector.connect(admin_url, autocommit=True) as admin_connection:
        owner = _database_owner(admin_connection, database_name)
        role_exists = _role_exists(admin_connection, role_name)
        if owner is not None and owner != role_name:
            raise ProjectDatabaseNeedsRepair("Existing database is not owned by the managed project role.")

        if owner is not None:
            admin_connection.execute(
                _sql("ALTER DATABASE {} WITH ALLOW_CONNECTIONS false").format(_identifier(database_name))
            )
            admin_connection.execute(
                _sql("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(_identifier(database_name))
            )
            if role_exists:
                admin_connection.execute(
                    _sql("REVOKE CONNECT ON DATABASE {} FROM {}").format(
                        _identifier(database_name),
                        _identifier(role_name),
                    )
                )
            _terminate_sessions(admin_connection, database_name, role_name)
            if _database_session_count(admin_connection, database_name) > 0:
                raise ProjectDatabaseProvisioningError("Managed project database still has active sessions.")
            admin_connection.execute(_sql("DROP DATABASE IF EXISTS {}").format(_identifier(database_name)))
        elif role_exists:
            _terminate_sessions(admin_connection, database_name, role_name)

        if role_exists:
            admin_connection.execute(_sql("DROP ROLE IF EXISTS {}").format(_identifier(role_name)))


def _run_postgres_provisioning(
    row: dict[str, object],
    *,
    settings: Settings,
    connector: Connector,
    password: str,
) -> None:
    admin_url, _, _, _ = settings.require_project_database_settings()
    database_name = str(row["database_name"])
    role_name = str(row["role_name"])

    with connector.connect(admin_url, autocommit=True) as admin_connection:
        _ensure_role(admin_connection, role_name, password)
        _ensure_database(admin_connection, database_name, role_name)
        _apply_database_grants(admin_connection, database_name, role_name)

    with connector.connect(_target_conninfo(admin_url, database_name), autocommit=False) as target_connection:
        _apply_schema_grants(target_connection, role_name)


def provision_project_database(
    project_id: str,
    *,
    settings: Settings | None = None,
    connector: Connector | None = None,
) -> None:
    active_settings = settings or get_settings()
    row = fetch_project_database(project_id, active_settings)
    if row is None:
        raise ProjectDatabaseProvisioningError(f"Project database metadata for '{project_id}' was not found.")
    if str(row["status"]) == "active":
        return

    password: str | None = None
    try:
        password = project_database_secrets.read_or_create_secret(active_settings, str(row["password_secret_ref"]))
        _run_postgres_provisioning(
            row,
            settings=active_settings,
            connector=connector or PsycopgConnector(),
            password=password,
        )
    except ProjectDatabaseNeedsRepair as exc:
        _mark_failure(
            str(row["id"]),
            active_settings,
            "needs_repair",
            _redact_error(str(exc), active_settings, password, row),
        )
        return
    except Exception as exc:
        _mark_failure(str(row["id"]), active_settings, "failed", _redact_error(str(exc), active_settings, password, row))
        return

    _mark_active(str(row["id"]), active_settings)


def purge_project_database(
    row: dict[str, object],
    *,
    settings: Settings | None = None,
    connector: Connector | None = None,
) -> None:
    active_settings = settings or get_settings()
    project_database_id = str(row["id"])
    database_status = str(row["status"])
    if database_status == "purged":
        return
    if database_status not in PURGEABLE_STATUSES:
        raise ProjectDatabaseProvisioningError(f"Project database status '{database_status}' cannot be purged.")

    _mark_purging(project_database_id, active_settings)
    password: str | None = None
    try:
        try:
            password = project_database_secrets.read_secret(active_settings, str(row["password_secret_ref"]))
        except FileNotFoundError:
            password = None
        _run_postgres_purge(row, settings=active_settings, connector=connector or PsycopgConnector())
        project_database_secrets.delete_secret(active_settings, str(row["password_secret_ref"]))
    except Exception as exc:
        _mark_failure(
            project_database_id,
            active_settings,
            "purge_failed",
            _redact_error(str(exc), active_settings, password, row),
        )
        return

    _mark_purged(project_database_id, active_settings)
