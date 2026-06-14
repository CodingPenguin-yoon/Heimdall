from __future__ import annotations

import sqlite3

import pytest

from app.config import Settings
from app.db import POSTGRES_SCHEMA_STATEMENTS, SCHEMA_STATEMENTS, adapt_qmark_placeholders, connect, init_db, row_to_dict


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
    )


def test_adapt_qmark_placeholders_ignores_literals_and_comments():
    statement = """
    SELECT '?', "?", value
    FROM sample
    WHERE id = ? AND name = ?
    -- ignored ?
    /* ignored ? */
    """

    assert adapt_qmark_placeholders(statement) == """
    SELECT '?', "?", value
    FROM sample
    WHERE id = %s AND name = %s
    -- ignored ?
    /* ignored ? */
    """


def test_row_to_dict_accepts_dict_rows():
    row = {"id": "project_1", "name": "Preview API"}

    assert row_to_dict(row) == {"id": "project_1", "name": "Preview API"}


def test_sqlite_connection_still_supports_qmark_placeholders_and_rows(tmp_path):
    settings = make_settings(tmp_path)
    settings.ensure_runtime_dirs()

    with connect(settings) as connection:
        connection.execute("CREATE TABLE sample (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample (id, value) VALUES (?, ?)", ("one", "two"))
        row = connection.execute("SELECT * FROM sample WHERE id = ?", ("one",)).fetchone()

    assert row_to_dict(row) == {"id": "one", "value": "two"}


def test_sqlite_bootstrap_creates_project_database_metadata_tables(tmp_path):
    settings = make_settings(tmp_path)

    init_db(settings)

    with connect(settings) as connection:
        database_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(project_databases)").fetchall()
        }
        binding_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(project_database_bindings)").fetchall()
        }
        database_foreign_keys = connection.execute("PRAGMA foreign_key_list(project_databases)").fetchall()
        binding_foreign_key_tables = {
            row["table"] for row in connection.execute("PRAGMA foreign_key_list(project_database_bindings)").fetchall()
        }
        database_unique_columns = {
            tuple(
                row["name"]
                for row in connection.execute(f"PRAGMA index_info({index_row['name']})").fetchall()
            )
            for index_row in connection.execute("PRAGMA index_list(project_databases)").fetchall()
            if index_row["unique"]
        }

    assert database_columns == {
        "id",
        "project_id",
        "database_name",
        "role_name",
        "password_secret_ref",
        "app_host",
        "app_port",
        "network_name",
        "status",
        "retention_policy",
        "orphaned_at",
        "created_at",
        "updated_at",
        "provisioned_at",
        "last_error",
    }
    assert binding_columns == {
        "id",
        "project_database_id",
        "project_id",
        "service_id",
        "env_var_name",
        "required_secret_name",
        "created_at",
        "updated_at",
    }
    assert database_foreign_keys == []
    assert ("project_id",) in database_unique_columns
    assert ("database_name",) in database_unique_columns
    assert ("role_name",) in database_unique_columns
    assert ("project_id", "database_name", "role_name") not in database_unique_columns
    assert binding_foreign_key_tables == {"project_databases", "project_services"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"project_id": "project_one", "database_name": "db_two", "role_name": "role_two"},
        {"project_id": "project_two", "database_name": "db_one", "role_name": "role_two"},
        {"project_id": "project_two", "database_name": "db_two", "role_name": "role_one"},
    ],
)
def test_sqlite_project_databases_unique_constraints_fail_independently(tmp_path, overrides):
    settings = make_settings(tmp_path)

    init_db(settings)

    def insert_project_database(connection, **values):
        data = {
            "id": "pdb_one",
            "project_id": "project_one",
            "database_name": "db_one",
            "role_name": "role_one",
            "password_secret_ref": "project-databases/project_one/password",
            "app_host": "project-postgres",
            "app_port": 5432,
            "network_name": "heimdall-project-db",
            "status": "pending",
            "retention_policy": "retain",
            "orphaned_at": None,
            "created_at": "2026-06-08T00:00:00+00:00",
            "updated_at": "2026-06-08T00:00:00+00:00",
            "provisioned_at": None,
            "last_error": None,
        }
        data.update(values)
        connection.execute(
            """
            INSERT INTO project_databases (
                id, project_id, database_name, role_name, password_secret_ref, app_host,
                app_port, network_name, status, retention_policy, orphaned_at, created_at,
                updated_at, provisioned_at, last_error
            )
            VALUES (
                :id, :project_id, :database_name, :role_name, :password_secret_ref, :app_host,
                :app_port, :network_name, :status, :retention_policy, :orphaned_at, :created_at,
                :updated_at, :provisioned_at, :last_error
            )
            """,
            data,
        )

    with connect(settings) as connection:
        insert_project_database(connection)
        with pytest.raises(sqlite3.IntegrityError):
            insert_project_database(connection, id="pdb_two", **overrides)


def test_postgres_schema_includes_project_database_metadata_tables():
    sqlite_schema = "\n".join(SCHEMA_STATEMENTS)
    postgres_schema = "\n".join(POSTGRES_SCHEMA_STATEMENTS)

    for schema in (sqlite_schema, postgres_schema):
        assert "CREATE TABLE IF NOT EXISTS project_databases" in schema
        assert "CREATE TABLE IF NOT EXISTS project_database_bindings" in schema
        assert "password_secret_ref TEXT NOT NULL" in schema
        assert "retention_policy TEXT NOT NULL" in schema
        assert "UNIQUE(project_id)" in schema
        assert "UNIQUE(database_name)" in schema
        assert "UNIQUE(role_name)" in schema
        assert "UNIQUE(project_id, database_name, role_name)" not in schema
        assert "UNIQUE(project_id, service_id, env_var_name)" in schema
