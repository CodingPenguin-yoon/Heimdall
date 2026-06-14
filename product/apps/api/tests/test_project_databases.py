from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.db import connect, init_db
from app.services import project_database_secrets, project_databases


class FakeComposable:
    def __init__(self, template: str, args=()):
        self.template = template
        self.args = tuple(args)

    def format(self, *args):
        return FakeComposable(self.template, args)


@dataclass(frozen=True)
class FakeIdentifier:
    value: str


@dataclass(frozen=True)
class FakeLiteral:
    value: str


class FakeSql:
    @staticmethod
    def SQL(template: str) -> FakeComposable:
        return FakeComposable(template)

    @staticmethod
    def Identifier(value: str) -> FakeIdentifier:
        return FakeIdentifier(value)

    @staticmethod
    def Literal(value: str) -> FakeLiteral:
        return FakeLiteral(value)


class FakeConninfo:
    def __init__(self):
        self.calls = []

    def make_conninfo(self, admin_url: str, **kwargs) -> str:
        self.calls.append((admin_url, kwargs))
        return f"{admin_url} dbname={kwargs['dbname']}"


class FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self, connector, dsn: str, autocommit: bool):
        self.connector = connector
        self.dsn = dsn
        self.autocommit = autocommit
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement, parameters=None):
        self.executed.append((statement, parameters))
        if isinstance(statement, str) and "FROM pg_roles" in statement:
            return FakeCursor((1,) if self.connector.role_exists else None)
        if isinstance(statement, str) and "FROM pg_database" in statement:
            owner = self.connector.database_owner
            return FakeCursor((owner,) if owner else None)
        if isinstance(statement, str) and "pg_terminate_backend" in statement:
            self.connector.terminate_session_calls.append(parameters)
            if not self.connector.keep_sessions:
                self.connector.database_session_count = 0
            return FakeCursor(None)
        if isinstance(statement, str) and "COUNT(*) FROM pg_stat_activity" in statement:
            return FakeCursor((self.connector.database_session_count,))
        if isinstance(statement, FakeComposable):
            if statement.template.startswith("CREATE ROLE"):
                if self.connector.fail_on_create_role:
                    raise RuntimeError(self.connector.failure_message)
                self.connector.role_exists = True
            if statement.template.startswith("ALTER ROLE"):
                if self.connector.fail_on_alter_role:
                    raise RuntimeError(self.connector.failure_message)
                self.connector.role_exists = True
            if statement.template.startswith("CREATE DATABASE"):
                self.connector.create_database_autocommit_values.append(self.autocommit)
                self.connector.database_owner = self.connector.role_name
            if statement.template.startswith("DROP DATABASE"):
                self.connector.drop_database_autocommit_values.append(self.autocommit)
                self.connector.database_owner = None
            if statement.template.startswith("DROP ROLE"):
                if self.connector.fail_on_drop_role:
                    raise RuntimeError(self.connector.failure_message)
                self.connector.role_exists = False
        return FakeCursor(None)


class FakeConnector:
    def __init__(
        self,
        *,
        role_exists: bool = False,
        database_owner: str | None = None,
        fail_on_create_role: bool = False,
        fail_on_alter_role: bool = False,
        fail_on_drop_role: bool = False,
        failure_message: str = "failure",
        database_session_count: int = 0,
        keep_sessions: bool = False,
    ):
        self.role_exists = role_exists
        self.database_owner = database_owner
        self.fail_on_create_role = fail_on_create_role
        self.fail_on_alter_role = fail_on_alter_role
        self.fail_on_drop_role = fail_on_drop_role
        self.failure_message = failure_message
        self.database_session_count = database_session_count
        self.keep_sessions = keep_sessions
        self.role_name = ""
        self.connections = []
        self.create_database_autocommit_values = []
        self.drop_database_autocommit_values = []
        self.terminate_session_calls = []

    def connect(self, dsn: str, *, autocommit: bool = False) -> FakeConnection:
        connection = FakeConnection(self, dsn, autocommit)
        self.connections.append(connection)
        return connection


def make_settings(tmp_path) -> Settings:
    return Settings(
        runtime_dir=tmp_path / "runtime",
        database_url=f"sqlite:///{tmp_path / 'heimdall.db'}",
        public_base_url="http://127.0.0.1:8000",
        preview_host="127.0.0.1",
        preview_port_start=18000,
        preview_port_end=18010,
        github_api_token=None,
        github_webhook_secret=None,
        gitlab_base_url=None,
        gitlab_api_token=None,
        gitlab_webhook_secret=None,
        project_database_admin_url="postgres://admin:admin-secret@project-postgres:5432/postgres",
    )


def insert_project_database(
    settings: Settings,
    project_id: str = "project_abc",
    *,
    status: str = "pending",
) -> dict[str, str]:
    init_db(settings)
    row = {
        "id": "pdb_abc",
        "project_id": project_id,
        "database_name": f"hm_{project_id}_db",
        "role_name": f"hm_{project_id}_role",
        "password_secret_ref": f"project-databases/{project_id}/password",
        "app_host": "project-postgres",
        "app_port": 5432,
        "network_name": "heimdall-project-db",
        "status": status,
        "retention_policy": "retain",
        "created_at": "2026-06-08T00:00:00+00:00",
        "updated_at": "2026-06-08T00:00:00+00:00",
    }
    with connect(settings) as connection:
        connection.execute(
            """
            INSERT INTO project_databases (
                id, project_id, database_name, role_name, password_secret_ref, app_host,
                app_port, network_name, status, retention_policy, created_at, updated_at
            )
            VALUES (
                :id, :project_id, :database_name, :role_name, :password_secret_ref, :app_host,
                :app_port, :network_name, :status, :retention_policy, :created_at, :updated_at
            )
            """,
            row,
        )
    return row


def patch_psycopg_helpers(monkeypatch):
    fake_conninfo = FakeConninfo()
    monkeypatch.setattr(project_databases, "sql", FakeSql)
    monkeypatch.setattr(project_databases, "conninfo", fake_conninfo)
    return fake_conninfo


def all_executed(connector: FakeConnector):
    return [item for connection in connector.connections for item in connection.executed]


def test_provisioner_uses_composable_identifier_sql_and_marks_active(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    row = insert_project_database(settings)
    fake_conninfo = patch_psycopg_helpers(monkeypatch)
    connector = FakeConnector()
    connector.role_name = row["role_name"]

    project_databases.provision_project_database(row["project_id"], settings=settings, connector=connector)

    executed = all_executed(connector)
    ddl = [statement for statement, _ in executed if isinstance(statement, FakeComposable)]
    raw_sql = [(statement, parameters) for statement, parameters in executed if isinstance(statement, str)]
    assert any(statement.template.startswith("CREATE ROLE") for statement in ddl)
    create_role_templates = [statement.template for statement in ddl if statement.template.startswith("CREATE ROLE")]
    assert all("NOSUPERUSER" in template for template in create_role_templates)
    assert all("NOCREATEDB" in template for template in create_role_templates)
    assert all("NOCREATEROLE" in template for template in create_role_templates)
    assert any(statement.template.startswith("CREATE DATABASE") for statement in ddl)
    assert all(isinstance(arg, (FakeIdentifier, FakeLiteral)) for statement in ddl for arg in statement.args)
    assert all(row["database_name"] not in statement and row["role_name"] not in statement for statement, _ in raw_sql)
    assert any(parameters == (row["role_name"],) for _, parameters in raw_sql)
    assert any(parameters == (row["database_name"],) for _, parameters in raw_sql)
    assert connector.create_database_autocommit_values == [True]
    assert fake_conninfo.calls == [
        (settings.project_database_admin_url, {"dbname": row["database_name"]}),
    ]

    with connect(settings) as connection:
        stored = connection.execute("SELECT status, provisioned_at, last_error FROM project_databases").fetchone()
    assert stored["status"] == "active"
    assert stored["provisioned_at"] is not None
    assert stored["last_error"] is None


def test_provisioner_runs_revoke_and_grant_order(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    row = insert_project_database(settings)
    patch_psycopg_helpers(monkeypatch)
    connector = FakeConnector(role_exists=True, database_owner=row["role_name"])
    connector.role_name = row["role_name"]

    project_databases.provision_project_database(row["project_id"], settings=settings, connector=connector)

    templates = [
        statement.template
        for statement, _ in all_executed(connector)
        if isinstance(statement, FakeComposable)
    ]
    assert templates.index("REVOKE CONNECT, TEMPORARY ON DATABASE {} FROM PUBLIC") < templates.index(
        "GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}"
    )
    assert templates.index("REVOKE CREATE ON SCHEMA {} FROM PUBLIC") < templates.index(
        "GRANT USAGE, CREATE ON SCHEMA {} TO {}"
    )


def test_provisioner_marks_failed_with_redacted_error(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    row = insert_project_database(settings)
    patch_psycopg_helpers(monkeypatch)
    password = "raw-generated-password"
    project_database_secrets.write_secret(settings, row["password_secret_ref"], password)
    connector = FakeConnector(
        fail_on_create_role=True,
        failure_message=f"could not connect {settings.project_database_admin_url} password={password}",
    )
    connector.role_name = row["role_name"]

    project_databases.provision_project_database(row["project_id"], settings=settings, connector=connector)

    with connect(settings) as connection:
        stored = connection.execute("SELECT status, last_error FROM project_databases").fetchone()
    assert stored["status"] == "failed"
    assert "[redacted]" in stored["last_error"]
    assert settings.project_database_admin_url not in stored["last_error"]
    assert password not in stored["last_error"]


def test_retry_reuses_existing_secret_and_can_mark_active(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    row = insert_project_database(settings)
    patch_psycopg_helpers(monkeypatch)
    failing = FakeConnector(fail_on_create_role=True, failure_message="first failure")
    failing.role_name = row["role_name"]

    project_databases.provision_project_database(row["project_id"], settings=settings, connector=failing)
    password = project_database_secrets.read_secret(settings, row["password_secret_ref"])

    successful = FakeConnector()
    successful.role_name = row["role_name"]
    project_databases.provision_project_database(row["project_id"], settings=settings, connector=successful)

    assert project_database_secrets.read_secret(settings, row["password_secret_ref"]) == password
    with connect(settings) as connection:
        stored = connection.execute("SELECT status, last_error FROM project_databases").fetchone()
    assert stored["status"] == "active"
    assert stored["last_error"] is None


def test_existing_role_and_database_count_as_success_after_owner_verification(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    row = insert_project_database(settings)
    patch_psycopg_helpers(monkeypatch)
    connector = FakeConnector(role_exists=True, database_owner=row["role_name"])
    connector.role_name = row["role_name"]

    project_databases.provision_project_database(row["project_id"], settings=settings, connector=connector)

    templates = [
        statement.template
        for statement, _ in all_executed(connector)
        if isinstance(statement, FakeComposable)
    ]
    alter_role_templates = [template for template in templates if template.startswith("ALTER ROLE")]
    assert alter_role_templates
    assert all("NOSUPERUSER" in template for template in alter_role_templates)
    assert all("NOCREATEDB" in template for template in alter_role_templates)
    assert all("NOCREATEROLE" in template for template in alter_role_templates)
    assert "CREATE DATABASE {} OWNER {}" not in templates
    with connect(settings) as connection:
        stored = connection.execute("SELECT status FROM project_databases").fetchone()
    assert stored["status"] == "active"


def test_purge_drops_database_then_role_deletes_secret_and_marks_purged(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    row = insert_project_database(settings, status="active")
    password = "raw-generated-password"
    project_database_secrets.write_secret(settings, row["password_secret_ref"], password)
    patch_psycopg_helpers(monkeypatch)
    connector = FakeConnector(role_exists=True, database_owner=row["role_name"], database_session_count=2)
    connector.role_name = row["role_name"]

    project_databases.purge_project_database(row, settings=settings, connector=connector)

    executed = all_executed(connector)
    templates = [
        statement.template
        for statement, _ in executed
        if isinstance(statement, FakeComposable)
    ]
    assert connector.connections[0].autocommit is True
    assert connector.drop_database_autocommit_values == [True]
    assert connector.terminate_session_calls == [(row["database_name"], row["role_name"])]
    assert "ALTER DATABASE {} WITH ALLOW_CONNECTIONS false" in templates
    assert "REVOKE CONNECT ON DATABASE {} FROM PUBLIC" in templates
    assert "REVOKE CONNECT ON DATABASE {} FROM {}" in templates
    assert templates.index("DROP DATABASE IF EXISTS {}") < templates.index("DROP ROLE IF EXISTS {}")
    assert all("FORCE" not in template and "CASCADE" not in template for template in templates)
    assert all(
        isinstance(arg, FakeIdentifier)
        for statement, _ in executed
        if isinstance(statement, FakeComposable)
        for arg in statement.args
    )
    raw_sql = [(statement, parameters) for statement, parameters in executed if isinstance(statement, str)]
    assert all(row["database_name"] not in statement and row["role_name"] not in statement for statement, _ in raw_sql)
    assert any(parameters == (row["database_name"], row["role_name"]) for _, parameters in raw_sql)
    assert not project_database_secrets.secret_exists(settings, row["password_secret_ref"])
    with connect(settings) as connection:
        stored = connection.execute("SELECT status, last_error FROM project_databases").fetchone()
    assert stored["status"] == "purged"
    assert stored["last_error"] is None


def test_purge_ownership_mismatch_marks_purge_failed_and_keeps_secret(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    row = insert_project_database(settings, status="orphaned")
    password = "raw-generated-password"
    project_database_secrets.write_secret(settings, row["password_secret_ref"], password)
    patch_psycopg_helpers(monkeypatch)
    connector = FakeConnector(role_exists=True, database_owner="unexpected_owner")
    connector.role_name = row["role_name"]

    project_databases.purge_project_database(row, settings=settings, connector=connector)

    templates = [
        statement.template
        for statement, _ in all_executed(connector)
        if isinstance(statement, FakeComposable)
    ]
    assert "DROP DATABASE IF EXISTS {}" not in templates
    assert "DROP ROLE IF EXISTS {}" not in templates
    assert project_database_secrets.secret_exists(settings, row["password_secret_ref"])
    with connect(settings) as connection:
        stored = connection.execute("SELECT status, last_error FROM project_databases").fetchone()
    assert stored["status"] == "purge_failed"
    assert "owned by the managed project role" in stored["last_error"]


def test_purge_role_drop_failure_records_redacted_retryable_failure(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    row = insert_project_database(settings, status="active")
    password = "raw-generated-password"
    project_database_secrets.write_secret(settings, row["password_secret_ref"], password)
    patch_psycopg_helpers(monkeypatch)
    connector = FakeConnector(
        role_exists=True,
        database_owner=row["role_name"],
        fail_on_drop_role=True,
        failure_message=f"drop failed {settings.project_database_admin_url} password={password}",
    )
    connector.role_name = row["role_name"]

    project_databases.purge_project_database(row, settings=settings, connector=connector)

    assert project_database_secrets.secret_exists(settings, row["password_secret_ref"])
    with connect(settings) as connection:
        stored = connection.execute("SELECT status, last_error FROM project_databases").fetchone()
    assert stored["status"] == "purge_failed"
    assert "[redacted]" in stored["last_error"]
    assert settings.project_database_admin_url not in stored["last_error"]
    assert password not in stored["last_error"]


def test_purge_secret_delete_failure_records_redacted_retryable_failure(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    row = insert_project_database(settings, status="active")
    password = "raw-generated-password"
    project_database_secrets.write_secret(settings, row["password_secret_ref"], password)
    patch_psycopg_helpers(monkeypatch)
    connector = FakeConnector(role_exists=True, database_owner=row["role_name"])
    connector.role_name = row["role_name"]

    def fake_delete_secret(settings_arg, ref):
        raise project_database_secrets.SecretRefError(
            f"delete failed {settings_arg.project_database_admin_url} password={password}"
        )

    monkeypatch.setattr(project_database_secrets, "delete_secret", fake_delete_secret)

    project_databases.purge_project_database(row, settings=settings, connector=connector)

    with connect(settings) as connection:
        stored = connection.execute("SELECT status, last_error FROM project_databases").fetchone()
    assert stored["status"] == "purge_failed"
    assert "[redacted]" in stored["last_error"]
    assert settings.project_database_admin_url not in stored["last_error"]
    assert password not in stored["last_error"]
