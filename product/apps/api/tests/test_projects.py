import sqlite3
from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


def volume_project_payload(**overrides):
    payload = project_payload(
        volumes=[
            {
                "name": "data",
                "target_path": "/app/data",
                "read_only": False,
            }
        ]
    )
    payload.update(overrides)
    return payload


@pytest.fixture
def volume_client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    runtime_dir = tmp_path / "runtime"
    database_path = tmp_path / "heimdall.db"
    host_root = tmp_path / "volume-host"
    container_root = tmp_path / "volume-container"
    host_root.mkdir()
    container_root.mkdir()

    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("HEIMDALL_PREVIEW_HOST", "preview.local")
    monkeypatch.setenv("HEIMDALL_PREVIEW_PORT_START", "18000")
    monkeypatch.setenv("HEIMDALL_PREVIEW_PORT_END", "18010")
    monkeypatch.setenv("HEIMDALL_VOLUME_ROOT_HOST", str(host_root))
    monkeypatch.setenv("HEIMDALL_VOLUME_ROOT_CONTAINER", str(container_root))
    for key in (
        "HEIMDALL_GITHUB_API_TOKEN",
        "GITHUB_API_TOKEN",
        "GITHUB_TOKEN",
        "HEIMDALL_GITHUB_WEBHOOK_SECRET",
        "GITHUB_WEBHOOK_SECRET",
        "GITHUB_SECRET",
        "HEIMDALL_GITLAB_BASE_URL",
        "GITLAB_BASE_URL",
        "HEIMDALL_GITLAB_API_TOKEN",
        "GITLAB_API_TOKEN",
        "GITLAB_TOKEN",
        "HEIMDALL_GITLAB_WEBHOOK_SECRET",
        "GITLAB_WEBHOOK_SECRET",
        "GITLAB_SYSTEM_HOOK_SECRET",
        "HEIMDALL_PROJECT_DATABASE_ADMIN_URL",
        "HEIMDALL_PROJECT_DATABASE_APP_HOST",
        "HEIMDALL_PROJECT_DATABASE_APP_PORT",
        "HEIMDALL_PROJECT_DATABASE_NETWORK",
    ):
        monkeypatch.setenv(key, "")

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def project_db_client(tmp_path, monkeypatch) -> Generator[tuple[TestClient, str], None, None]:
    runtime_dir = tmp_path / "runtime"
    database_path = tmp_path / "heimdall.db"
    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("HEIMDALL_PREVIEW_HOST", "preview.local")
    monkeypatch.setenv("HEIMDALL_PREVIEW_PORT_START", "18000")
    monkeypatch.setenv("HEIMDALL_PREVIEW_PORT_END", "18010")
    monkeypatch.setenv(
        "HEIMDALL_PROJECT_DATABASE_ADMIN_URL",
        "postgres://admin:secret@project-postgres:5432/postgres",
    )
    monkeypatch.setenv("HEIMDALL_PROJECT_DATABASE_APP_HOST", "project-postgres")
    monkeypatch.setenv("HEIMDALL_PROJECT_DATABASE_APP_PORT", "5432")
    monkeypatch.setenv("HEIMDALL_PROJECT_DATABASE_NETWORK", "heimdall-project-db")
    for key in (
        "HEIMDALL_GITHUB_API_TOKEN",
        "GITHUB_API_TOKEN",
        "GITHUB_TOKEN",
        "HEIMDALL_GITHUB_WEBHOOK_SECRET",
        "GITHUB_WEBHOOK_SECRET",
        "GITHUB_SECRET",
        "HEIMDALL_GITLAB_BASE_URL",
        "GITLAB_BASE_URL",
        "HEIMDALL_GITLAB_API_TOKEN",
        "GITLAB_API_TOKEN",
        "GITLAB_TOKEN",
        "HEIMDALL_GITLAB_WEBHOOK_SECRET",
        "GITLAB_WEBHOOK_SECRET",
        "GITLAB_SYSTEM_HOOK_SECRET",
        "HEIMDALL_VOLUME_ROOT_HOST",
        "HEIMDALL_VOLUME_ROOT_CONTAINER",
    ):
        monkeypatch.setenv(key, "")

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client, str(database_path)
    get_settings.cache_clear()


def project_payload(**overrides):
    payload = {
        "name": "Preview API",
        "provider": "github",
        "repo_url": "https://github.com/example/preview-api.git",
        "tracked_branch": "main",
        "deploy_mode": "dockerfile",
        "build_context_path": ".",
        "dockerfile_path": "Dockerfile",
        "container_port": 8080,
        "health_check_path": "/health",
        "auto_deploy_enabled": True,
    }
    payload.update(overrides)
    return payload


def multi_service_payload(**overrides):
    payload = project_payload(
        name="Portfolio",
        repo_url="https://github.com/example/portfolio.git",
        deploy_mode="multi_service_dockerfile",
        build_context_path=".",
        dockerfile_path="Dockerfile",
        container_port=None,
        health_check_path=None,
        services=[
            {
                "name": "frontend",
                "build_context_path": "frontend",
                "dockerfile_path": "frontend/Dockerfile",
                "container_port": 3000,
                "public": True,
                "health_check_path": "/",
                "startup_order": 20,
                "build_env": {"VITE_API_BASE_URL": "/api"},
                "runtime_env": {},
                "required_secrets": [],
            },
            {
                "name": "backend",
                "build_context_path": "backend",
                "dockerfile_path": "backend/Dockerfile",
                "container_port": 8000,
                "public": False,
                "health_check_path": "/health",
                "startup_order": 10,
                "build_env": {},
                "runtime_env": {"PORT": "8000"},
                "required_secrets": ["DATABASE_URL", "JWT_SECRET"],
            },
        ],
    )
    payload.update(overrides)
    return payload


def install_fake_project_database_provisioner(monkeypatch, *, status: str, last_error=None):
    captured: dict[str, str] = {}

    def fake_provision_project_database(project_id, *, settings=None, connector=None):
        from app.config import get_settings
        from app.db import connect
        from app.services import project_database_secrets, project_databases

        active_settings = settings or get_settings()
        row = project_databases.fetch_project_database(project_id, active_settings)
        assert row is not None
        password = project_database_secrets.read_or_create_secret(
            active_settings,
            str(row["password_secret_ref"]),
        )
        captured["password"] = password
        timestamp = datetime.now(timezone.utc).isoformat()
        with connect(active_settings) as connection:
            if status == "active":
                connection.execute(
                    """
                    UPDATE project_databases
                    SET status = ?, provisioned_at = COALESCE(provisioned_at, ?), last_error = NULL, updated_at = ?
                    WHERE project_id = ?
                    """,
                    ("active", timestamp, timestamp, project_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE project_databases
                    SET status = ?, last_error = ?, updated_at = ?
                    WHERE project_id = ?
                    """,
                    (status, last_error, timestamp, project_id),
                )

    from app.services import project_databases

    monkeypatch.setattr(project_databases, "provision_project_database", fake_provision_project_database)
    return captured


def install_fake_project_database_purger(monkeypatch):
    captured = {"calls": 0, "statuses_at_call": []}

    def fake_purge_project_database(row, *, settings=None, connector=None):
        from app.config import get_settings
        from app.db import connect

        active_settings = settings or get_settings()
        captured["calls"] += 1
        timestamp = datetime.now(timezone.utc).isoformat()
        with connect(active_settings) as connection:
            status_at_call = connection.execute(
                "SELECT status FROM project_databases WHERE id = ?",
                (row["id"],),
            ).fetchone()[0]
            captured["statuses_at_call"].append(status_at_call)
            connection.execute(
                """
                UPDATE project_databases
                SET status = ?, last_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                ("purged", timestamp, row["id"]),
            )

    from app.services import project_databases

    monkeypatch.setattr(project_databases, "purge_project_database", fake_purge_project_database)
    return captured


def purge_payload(database_id: str, **overrides):
    payload = {
        "database_id": database_id,
        "confirmation": "purge managed project database",
    }
    payload.update(overrides)
    return payload


def test_create_and_list_project(client):
    create_response = client.post("/api/projects", json=project_payload())
    assert create_response.status_code == 201, create_response.text

    created = create_response.json()
    assert created["slug"] == "preview-api"
    assert created["preview_port"] == 18000
    assert created["preview_url"] == "http://preview.local:18000"
    assert created["has_real_preview"] is False
    assert "run_as_heimdall_child" not in created
    assert "run_as_heimdall_child" not in created["services"][0]

    list_response = client.get("/api/projects")
    assert list_response.status_code == 200
    projects = list_response.json()
    assert len(projects) == 1
    assert projects[0]["id"] == created["id"]
    assert "run_as_heimdall_child" not in projects[0]


def test_no_volume_project_create_works_without_volume_roots(client):
    response = client.post("/api/projects", json=project_payload(name="No Volume API"))

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["services"][0]["name"] == "app"
    assert created["services"][0]["volumes"] == []


def test_project_database_requires_admin_url_only_when_enabled(client):
    no_database_response = client.post("/api/projects", json=project_payload(name="No DB API"))
    assert no_database_response.status_code == 201, no_database_response.text
    assert no_database_response.json()["database"] is None

    database_response = client.post(
        "/api/projects",
        json=project_payload(
            name="Managed DB API",
            repo_url="https://github.com/example/managed-db-api.git",
            database={"required": True},
        ),
    )

    assert database_response.status_code == 422
    assert "HEIMDALL_PROJECT_DATABASE_ADMIN_URL" in database_response.json()["detail"]


def test_create_project_database_metadata_is_redacted_and_slug_stable(project_db_client, monkeypatch):
    test_client, database_path = project_db_client
    admin_url = "postgres://admin:secret@project-postgres:5432/postgres"
    captured = install_fake_project_database_provisioner(monkeypatch, status="active")

    create_response = test_client.post("/api/projects", json=project_payload(database={"required": True}))

    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    database = created["database"]
    assert database["required"] is True
    assert database["type"] == "postgres"
    assert database["env_var"] == "DATABASE_URL"
    assert database["status"] == "active"
    assert database["id"].startswith("pdb_")
    assert database["app_host"] == "project-postgres"
    assert database["app_port"] == 5432
    assert database["network_name"] == "heimdall-project-db"
    assert database["retention_policy"] == "retain"
    assert database["provisioned_at"] is not None
    assert admin_url not in create_response.text
    assert captured["password"] not in create_response.text
    assert "database_name" not in create_response.text
    assert "role_name" not in create_response.text
    assert "password_secret_ref" not in create_response.text
    assert "postgres://" not in create_response.text

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT id, database_name, role_name, password_secret_ref
            FROM project_databases
            WHERE project_id = ?
            """,
            (created["id"],),
        ).fetchone()
    assert row is not None
    assert row[0] == database["id"]
    assert row[1].startswith(f"hm_{created['id']}_")
    assert row[2].startswith(f"hm_{created['id']}_")
    assert len(row[1]) <= 63
    assert len(row[2]) <= 63
    assert created["slug"] not in row[1]
    assert row[3] == f"project-databases/{created['id']}/password"
    assert captured["password"] not in "".join(str(value) for value in row)

    rename_response = test_client.patch(f"/api/projects/{created['id']}", json={"slug": "preview-api-renamed"})

    assert rename_response.status_code == 200, rename_response.text
    assert rename_response.json()["database"]["id"] == database["id"]
    with sqlite3.connect(database_path) as connection:
        renamed_row = connection.execute(
            "SELECT database_name, role_name FROM project_databases WHERE project_id = ?",
            (created["id"],),
        ).fetchone()
    assert renamed_row == (row[1], row[2])


def test_create_project_database_failure_is_redacted(project_db_client, monkeypatch):
    test_client, _ = project_db_client
    admin_url = "postgres://admin:secret@project-postgres:5432/postgres"
    captured = install_fake_project_database_provisioner(
        monkeypatch,
        status="failed",
        last_error="failed to provision [redacted]",
    )

    response = test_client.post("/api/projects", json=project_payload(database={"required": True}))

    assert response.status_code == 201, response.text
    database = response.json()["database"]
    assert database["status"] == "failed"
    assert database["last_error"] == "failed to provision [redacted]"
    assert admin_url not in response.text
    assert captured["password"] not in response.text
    assert "password_secret_ref" not in response.text
    assert "database_name" not in response.text
    assert "role_name" not in response.text
    assert "postgres://" not in response.text


def test_multi_service_project_database_binds_database_url_required_secret(project_db_client, monkeypatch):
    test_client, database_path = project_db_client
    install_fake_project_database_provisioner(monkeypatch, status="active")

    response = test_client.post("/api/projects", json=multi_service_payload(database={"required": True}))

    assert response.status_code == 201, response.text
    created = response.json()
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT project_services.name, project_database_bindings.env_var_name,
                   project_database_bindings.required_secret_name
            FROM project_database_bindings
            JOIN project_services ON project_services.id = project_database_bindings.service_id
            WHERE project_database_bindings.project_id = ?
            ORDER BY project_services.name
            """,
            (created["id"],),
        ).fetchall()

    assert rows == [("backend", "DATABASE_URL", "DATABASE_URL")]


def test_service_update_resyncs_project_database_bindings(project_db_client, monkeypatch):
    test_client, database_path = project_db_client
    install_fake_project_database_provisioner(monkeypatch, status="active")
    create_response = test_client.post("/api/projects", json=multi_service_payload(database={"required": True}))
    assert create_response.status_code == 201, create_response.text
    project_id = create_response.json()["id"]

    payload = multi_service_payload()["services"]
    for service in payload:
        service["required_secrets"] = []

    patch_response = test_client.patch(f"/api/projects/{project_id}", json={"services": payload})

    assert patch_response.status_code == 200, patch_response.text
    with sqlite3.connect(database_path) as connection:
        binding_count = connection.execute(
            "SELECT COUNT(*) FROM project_database_bindings WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    assert binding_count == 0


def test_project_database_required_false_retains_attempted_metadata(project_db_client, monkeypatch):
    test_client, database_path = project_db_client
    captured = install_fake_project_database_provisioner(
        monkeypatch,
        status="failed",
        last_error="failed to provision [redacted]",
    )

    create_response = test_client.post("/api/projects", json=project_payload(database={"required": True}))
    assert create_response.status_code == 201, create_response.text
    project_id = create_response.json()["id"]

    patch_response = test_client.patch(f"/api/projects/{project_id}", json={"database": {"required": False}})

    assert patch_response.status_code == 200, patch_response.text
    assert patch_response.json()["database"]["required"] is False
    assert patch_response.json()["database"]["status"] == "disabled"
    with sqlite3.connect(database_path) as connection:
        database_count = connection.execute(
            "SELECT COUNT(*) FROM project_databases WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        binding_count = connection.execute(
            "SELECT COUNT(*) FROM project_database_bindings WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    assert database_count == 1
    assert binding_count == 0
    assert captured["password"] not in patch_response.text


def test_project_database_retry_marks_failed_database_active(project_db_client, monkeypatch):
    test_client, _ = project_db_client
    failed_capture = install_fake_project_database_provisioner(
        monkeypatch,
        status="failed",
        last_error="failed to provision [redacted]",
    )
    create_response = test_client.post("/api/projects", json=project_payload(database={"required": True}))
    assert create_response.status_code == 201, create_response.text
    project_id = create_response.json()["id"]
    assert create_response.json()["database"]["status"] == "failed"

    active_capture = install_fake_project_database_provisioner(monkeypatch, status="active")
    retry_response = test_client.post(f"/api/projects/{project_id}/database/retry")

    assert retry_response.status_code == 200, retry_response.text
    assert retry_response.json()["database"]["status"] == "active"
    assert retry_response.json()["database"]["provisioned_at"] is not None
    assert active_capture["password"] == failed_capture["password"]
    assert active_capture["password"] not in retry_response.text


def test_project_database_retry_rejects_active_database(project_db_client, monkeypatch):
    test_client, _ = project_db_client
    install_fake_project_database_provisioner(monkeypatch, status="active")
    create_response = test_client.post("/api/projects", json=project_payload(database={"required": True}))
    assert create_response.status_code == 201, create_response.text
    project_id = create_response.json()["id"]

    retry_response = test_client.post(f"/api/projects/{project_id}/database/retry")

    assert retry_response.status_code == 409
    assert "cannot be retried" in retry_response.json()["detail"]


def test_project_delete_marks_database_orphaned(project_db_client, monkeypatch):
    test_client, database_path = project_db_client
    install_fake_project_database_provisioner(monkeypatch, status="active")
    create_response = test_client.post("/api/projects", json=project_payload(database={"required": True}))
    assert create_response.status_code == 201, create_response.text
    project_id = create_response.json()["id"]

    delete_response = test_client.delete(f"/api/projects/{project_id}")

    assert delete_response.status_code == 204
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT status, orphaned_at, provisioned_at FROM project_databases WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == "orphaned"
    assert row[1] is not None
    assert row[2] is not None


def test_project_database_purge_requires_confirmation_without_state_change(project_db_client, monkeypatch):
    test_client, database_path = project_db_client
    install_fake_project_database_provisioner(monkeypatch, status="active")
    purger = install_fake_project_database_purger(monkeypatch)
    create_response = test_client.post("/api/projects", json=project_payload(database={"required": True}))
    assert create_response.status_code == 201, create_response.text
    project_id = create_response.json()["id"]
    database_id = create_response.json()["database"]["id"]

    response = test_client.post(
        f"/api/projects/{project_id}/database/purge",
        json=purge_payload(database_id, confirmation="wrong confirmation"),
    )

    assert response.status_code == 422
    assert purger["calls"] == 0
    with sqlite3.connect(database_path) as connection:
        status_value = connection.execute(
            "SELECT status FROM project_databases WHERE id = ?",
            (database_id,),
        ).fetchone()[0]
    assert status_value == "active"


def test_project_database_purge_rejects_mismatched_database_id(project_db_client, monkeypatch):
    test_client, _ = project_db_client
    install_fake_project_database_provisioner(monkeypatch, status="active")
    purger = install_fake_project_database_purger(monkeypatch)
    create_response = test_client.post("/api/projects", json=project_payload(database={"required": True}))
    assert create_response.status_code == 201, create_response.text
    project_id = create_response.json()["id"]

    response = test_client.post(
        f"/api/projects/{project_id}/database/purge",
        json=purge_payload("pdb_wrong"),
    )

    assert response.status_code == 422
    assert purger["calls"] == 0


def test_project_database_purge_rejects_active_deployment(project_db_client, monkeypatch):
    test_client, database_path = project_db_client
    install_fake_project_database_provisioner(monkeypatch, status="active")
    purger = install_fake_project_database_purger(monkeypatch)
    create_response = test_client.post("/api/projects", json=project_payload(database={"required": True}))
    assert create_response.status_code == 201, create_response.text
    project_id = create_response.json()["id"]
    database_id = create_response.json()["database"]["id"]
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO deployments (
                id, project_id, trigger_type, status, status_message, is_dry_run, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "deploy_active",
                project_id,
                "manual",
                "starting",
                "deployment starting",
                0,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    response = test_client.post(
        f"/api/projects/{project_id}/database/purge",
        json=purge_payload(database_id),
    )

    assert response.status_code == 409
    assert "active deployment" in response.json()["detail"]
    assert purger["calls"] == 0


def test_orphaned_project_database_can_be_purged_after_project_delete(project_db_client, monkeypatch):
    test_client, database_path = project_db_client
    install_fake_project_database_provisioner(monkeypatch, status="active")
    purger = install_fake_project_database_purger(monkeypatch)
    create_response = test_client.post("/api/projects", json=project_payload(database={"required": True}))
    assert create_response.status_code == 201, create_response.text
    project_id = create_response.json()["id"]
    database_id = create_response.json()["database"]["id"]
    delete_response = test_client.delete(f"/api/projects/{project_id}")
    assert delete_response.status_code == 204

    response = test_client.post(
        f"/api/projects/{project_id}/database/purge",
        json=purge_payload(database_id),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == database_id
    assert response.json()["status"] == "purged"
    assert purger["calls"] == 1
    assert purger["statuses_at_call"] == ["purging"]
    with sqlite3.connect(database_path) as connection:
        stored = connection.execute(
            "SELECT status FROM project_databases WHERE id = ?",
            (database_id,),
        ).fetchone()
    assert stored[0] == "purged"


def test_project_database_purge_is_idempotent_when_already_purged(project_db_client, monkeypatch):
    test_client, database_path = project_db_client
    install_fake_project_database_provisioner(monkeypatch, status="active")
    purger = install_fake_project_database_purger(monkeypatch)
    create_response = test_client.post("/api/projects", json=project_payload(database={"required": True}))
    assert create_response.status_code == 201, create_response.text
    project_id = create_response.json()["id"]
    database_id = create_response.json()["database"]["id"]
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE project_databases SET status = ?, last_error = ? WHERE id = ?",
            ("purged", None, database_id),
        )

    response = test_client.post(
        f"/api/projects/{project_id}/database/purge",
        json=purge_payload(database_id),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "purged"
    assert purger["calls"] == 0


def test_purged_project_database_cannot_be_silently_reenabled(project_db_client, monkeypatch):
    test_client, database_path = project_db_client
    install_fake_project_database_provisioner(monkeypatch, status="active")
    create_response = test_client.post("/api/projects", json=project_payload(database={"required": True}))
    assert create_response.status_code == 201, create_response.text
    project_id = create_response.json()["id"]
    database_id = create_response.json()["database"]["id"]
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE project_databases SET status = ?, last_error = NULL WHERE id = ?",
            ("purged", database_id),
        )

    response = test_client.patch(f"/api/projects/{project_id}", json={"database": {"required": True}})

    assert response.status_code == 409
    assert "Purged managed project database metadata" in response.json()["detail"]
    with sqlite3.connect(database_path) as connection:
        status_value = connection.execute(
            "SELECT status FROM project_databases WHERE id = ?",
            (database_id,),
        ).fetchone()[0]
    assert status_value == "purged"


def test_single_service_top_level_volumes_roundtrip(volume_client):
    create_response = volume_client.post("/api/projects", json=volume_project_payload())

    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    volume = created["services"][0]["volumes"][0]
    assert volume["id"].startswith("volume_")
    assert volume["name"] == "data"
    assert volume["target_path"] == "/app/data"
    assert volume["read_only"] is False
    assert volume["status"] == "active"
    assert volume["source_relative_path"].startswith(f"{created['id']}/service_")
    assert volume["source_relative_path"].endswith(f"/{volume['id']}")
    assert "host_path" not in volume
    assert "host_source_path" not in volume
    assert "container_source_path" not in volume

    read_response = volume_client.get(f"/api/projects/{created['id']}")
    assert read_response.status_code == 200
    assert read_response.json()["services"][0]["volumes"] == [volume]


def test_volume_create_fails_when_roots_missing(client):
    response = client.post("/api/projects", json=volume_project_payload())

    assert response.status_code == 422
    assert "HEIMDALL_VOLUME_ROOT_HOST" in response.json()["detail"]


def test_rejects_top_level_host_source_extra_field(client):
    response = client.post("/api/projects", json=project_payload(host_path="/tmp/heimdall-data"))

    assert response.status_code == 422


@pytest.mark.parametrize(
    "field",
    ["child_root", "docker_sock", "docker_args", "mounts", "volumes_from", "privileged", "source", "src", "bind_source"],
)
def test_rejects_forbidden_project_extra_fields(client, field):
    response = client.post("/api/projects", json=project_payload(**{field: "/tmp/heimdall-data"}))

    assert response.status_code == 422


def test_rejects_service_level_host_source_extra_field(client):
    payload = multi_service_payload()
    payload["services"][0]["source"] = "/tmp/heimdall-frontend"

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422


def test_rejects_duplicate_volume_names(volume_client):
    response = volume_client.post(
        "/api/projects",
        json=volume_project_payload(
            volumes=[
                {"name": "data", "target_path": "/app/data"},
                {"name": "data", "target_path": "/app/cache"},
            ]
        ),
    )

    assert response.status_code == 422
    assert "Duplicate volume name" in response.json()["detail"]


def test_rejects_duplicate_normalized_volume_targets(volume_client):
    response = volume_client.post(
        "/api/projects",
        json=volume_project_payload(
            volumes=[
                {"name": "data", "target_path": "/app/data/cache"},
                {"name": "cache", "target_path": "/app//data/cache/."},
            ]
        ),
    )

    assert response.status_code == 422
    assert "Duplicate volume target_path" in response.json()["detail"]


@pytest.mark.parametrize("target_path", ["/var/run/docker.sock", "/var/lib/docker/containers", "/app/../data"])
def test_rejects_invalid_volume_target_paths(volume_client, target_path):
    response = volume_client.post(
        "/api/projects",
        json=volume_project_payload(volumes=[{"name": "data", "target_path": target_path}]),
    )

    assert response.status_code == 422
    assert "target_path" in response.json()["detail"]


def test_rejects_volume_host_path_extra_field(volume_client):
    response = volume_client.post(
        "/api/projects",
        json=volume_project_payload(
            volumes=[
                {
                    "name": "data",
                    "target_path": "/app/data",
                    "host_path": "/tmp/host-data",
                }
            ]
        ),
    )

    assert response.status_code == 422


def test_multi_service_volumes_roundtrip(volume_client):
    payload = multi_service_payload()
    payload["services"][0]["volumes"] = [{"name": "web-cache", "target_path": "/app/.cache", "read_only": True}]
    payload["services"][1]["volumes"] = [{"name": "api-data", "target_path": "/srv/app/data"}]

    response = volume_client.post("/api/projects", json=payload)

    assert response.status_code == 201, response.text
    created = response.json()
    frontend = next(service for service in created["services"] if service["name"] == "frontend")
    backend = next(service for service in created["services"] if service["name"] == "backend")
    assert frontend["volumes"][0]["name"] == "web-cache"
    assert frontend["volumes"][0]["read_only"] is True
    assert frontend["volumes"][0]["source_relative_path"].startswith(f"{created['id']}/service_")
    assert backend["volumes"][0]["name"] == "api-data"
    assert "host_source_path" not in frontend["volumes"][0]


def test_patch_preserves_volume_identity(volume_client):
    create_response = volume_client.post("/api/projects", json=volume_project_payload())
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    original_volume = created["services"][0]["volumes"][0]

    patch_response = volume_client.patch(f"/api/projects/{created['id']}", json={"slug": "preview-api-renamed"})

    assert patch_response.status_code == 200, patch_response.text
    patched_volume = patch_response.json()["services"][0]["volumes"][0]
    assert patched_volume["id"] == original_volume["id"]
    assert patched_volume["source_relative_path"] == original_volume["source_relative_path"]


def test_empty_volumes_update_removes_metadata(volume_client):
    create_response = volume_client.post("/api/projects", json=volume_project_payload())
    assert create_response.status_code == 201, create_response.text
    project_id = create_response.json()["id"]

    patch_response = volume_client.patch(f"/api/projects/{project_id}", json={"volumes": []})

    assert patch_response.status_code == 200, patch_response.text
    assert patch_response.json()["services"][0]["volumes"] == []


def test_db_bootstrap_creates_volume_tables_on_existing_db(tmp_path):
    from app.config import Settings
    from app.db import init_db

    database_path = tmp_path / "existing.db"
    database_path.touch()
    settings = Settings(
        runtime_dir=tmp_path / "runtime",
        database_url=f"sqlite:///{database_path}",
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

    init_db(settings)

    with sqlite3.connect(database_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE '%volume%'"
            )
        }
    assert "project_service_volumes" in table_names
    assert "release_service_volume_mounts" in table_names


def test_db_bootstrap_does_not_add_child_flag_columns_to_existing_tables(tmp_path):
    from app.config import Settings
    from app.db import init_db

    database_path = tmp_path / "existing.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE projects (
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
            """
        )
        connection.execute(
            """
            CREATE TABLE project_services (
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
                UNIQUE(project_id, name)
            )
            """
        )
    settings = Settings(
        runtime_dir=tmp_path / "runtime",
        database_url=f"sqlite:///{database_path}",
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

    init_db(settings)

    with sqlite3.connect(database_path) as connection:
        project_columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)").fetchall()}
        service_columns = {row[1] for row in connection.execute("PRAGMA table_info(project_services)").fetchall()}
        service_indexes = {row[1] for row in connection.execute("PRAGMA index_list(project_services)").fetchall()}
    assert "run_as_heimdall_child" not in project_columns
    assert "run_as_heimdall_child" not in service_columns
    assert "idx_project_services_one_child_per_project" not in service_indexes


def test_db_bootstrap_drops_legacy_service_child_unique_index(tmp_path):
    from app.config import Settings
    from app.db import init_db

    database_path = tmp_path / "existing.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE project_services (
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
                run_as_heimdall_child INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, name)
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX idx_project_services_one_child_per_project
            ON project_services(project_id)
            WHERE run_as_heimdall_child = 1
            """
        )
    settings = Settings(
        runtime_dir=tmp_path / "runtime",
        database_url=f"sqlite:///{database_path}",
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

    init_db(settings)

    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(project_services)").fetchall()}
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(project_services)").fetchall()}
    assert "run_as_heimdall_child" in columns
    assert "idx_project_services_one_child_per_project" not in indexes


def test_create_second_project_auto_allocates_next_preview_port(client):
    first_response = client.post("/api/projects", json=project_payload(name="Preview API"))
    assert first_response.status_code == 201, first_response.text

    second_response = client.post(
        "/api/projects",
        json=project_payload(name="Portfolio", repo_url="https://github.com/example/portfolio.git"),
    )

    assert second_response.status_code == 201, second_response.text
    assert first_response.json()["preview_port"] == 18000
    assert second_response.json()["preview_port"] == 18001


def test_create_gitlab_project(client):
    response = client.post(
        "/api/projects",
        json=project_payload(
            name="GitLab Preview",
            provider="gitlab",
            repo_url="https://gitlab.com/example/preview-api.git",
        ),
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["provider"] == "gitlab"
    assert created["repo_url"] == "https://gitlab.com/example/preview-api.git"


def test_rejects_embedded_repo_credentials(client):
    response = client.post(
        "/api/projects",
        json=project_payload(repo_url="https://token:secret@github.com/example/private-repo.git"),
    )
    assert response.status_code == 422
    assert "Embedded repository credentials" in response.json()["detail"]


def test_rejects_path_traversal(client):
    response = client.post(
        "/api/projects",
        json=project_payload(build_context_path="../outside"),
    )
    assert response.status_code == 422
    assert "path traversal" in response.json()["detail"]


def test_compose_mode_is_explicitly_unsupported(client):
    response = client.post(
        "/api/projects",
        json=project_payload(deploy_mode="compose", compose_file_path="docker-compose.yml"),
    )
    assert response.status_code == 422
    assert "unsupported" in response.json()["detail"].lower()


def test_create_multi_service_project(client):
    response = client.post("/api/projects", json=multi_service_payload())

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["deploy_mode"] == "multi_service_dockerfile"
    assert created["build_context_path"] == "frontend"
    assert created["dockerfile_path"] == "frontend/Dockerfile"
    assert created["container_port"] == 3000
    assert created["health_check_path"] == "/"
    assert [service["name"] for service in created["services"]] == ["backend", "frontend"]
    backend = next(service for service in created["services"] if service["name"] == "backend")
    assert backend["public"] is False
    assert backend["required_secrets"] == ["DATABASE_URL", "JWT_SECRET"]
    assert "DATABASE_URL" in response.text
    assert "postgres://" not in response.text


@pytest.mark.parametrize("value", [True, False])
def test_create_rejects_removed_top_level_child_field(client, value):
    response = client.post("/api/projects", json=project_payload(run_as_heimdall_child=value))

    assert response.status_code == 422
    assert "run_as_heimdall_child" in response.text


@pytest.mark.parametrize("value", [True, False])
def test_patch_rejects_removed_top_level_child_field(client, value):
    create_response = client.post("/api/projects", json=project_payload())
    assert create_response.status_code == 201, create_response.text

    response = client.patch(
        f"/api/projects/{create_response.json()['id']}",
        json={"run_as_heimdall_child": value},
    )

    assert response.status_code == 422
    assert "run_as_heimdall_child" in response.text


@pytest.mark.parametrize("value", [True, False])
def test_create_rejects_removed_service_child_field(client, value):
    payload = multi_service_payload()
    payload["services"][0]["run_as_heimdall_child"] = value

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "run_as_heimdall_child" in response.text


@pytest.mark.parametrize("value", [True, False])
def test_patch_rejects_removed_service_child_field(client, value):
    create_response = client.post("/api/projects", json=multi_service_payload())
    assert create_response.status_code == 201, create_response.text
    payload = multi_service_payload()
    payload["services"][0]["run_as_heimdall_child"] = value

    response = client.patch(
        f"/api/projects/{create_response.json()['id']}",
        json={"services": payload["services"]},
    )

    assert response.status_code == 422
    assert "run_as_heimdall_child" in response.text


def test_rejects_duplicate_multi_service_names(client):
    payload = multi_service_payload()
    payload["services"][0]["name"] = "backend"

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "Duplicate service name" in response.json()["detail"]


def test_rejects_invalid_multi_service_name(client):
    payload = multi_service_payload()
    payload["services"][0]["name"] = "Front End"

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "Service name" in response.json()["detail"]


def test_rejects_zero_public_multi_services(client):
    payload = multi_service_payload()
    for service in payload["services"]:
        service["public"] = False

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "exactly one public service" in response.json()["detail"]


def test_rejects_multiple_public_multi_services(client):
    payload = multi_service_payload()
    for service in payload["services"]:
        service["public"] = True

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "exactly one public service" in response.json()["detail"]


def test_rejects_invalid_multi_service_path(client):
    payload = multi_service_payload()
    payload["services"][0]["dockerfile_path"] = "../Dockerfile"

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "path traversal" in response.json()["detail"]


def test_rejects_invalid_env_name_and_secret_looking_env_value(client):
    invalid_name = multi_service_payload()
    invalid_name["services"][0]["build_env"] = {"1BAD": "value"}
    invalid_name_response = client.post("/api/projects", json=invalid_name)
    assert invalid_name_response.status_code == 422
    assert "invalid environment variable name" in invalid_name_response.json()["detail"]

    secret_value = multi_service_payload()
    secret_value["services"][0]["runtime_env"] = {"PUBLIC_VALUE": "super-secret-token"}
    secret_value_response = client.post("/api/projects", json=secret_value)
    assert secret_value_response.status_code == 422
    assert "secret value" in secret_value_response.json()["detail"]

    raw_database_url = multi_service_payload()
    raw_database_url["services"][1]["runtime_env"] = {"DATABASE_URL": "postgres://user:password@db/app"}
    raw_database_url_response = client.post("/api/projects", json=raw_database_url)
    assert raw_database_url_response.status_code == 422
    assert "looks secret" in raw_database_url_response.json()["detail"]


@pytest.mark.parametrize(
    ("env_name", "env_value"),
    [
        ("HEIMDALL_CHILD_ROOT_HOST", "/srv/heimdall/children"),
        ("DOCKER_HOST", "unix:///var/run/docker.sock"),
        ("PUBLIC_DOCKER_SOCKET", "/var/run/docker.sock"),
    ],
)
def test_rejects_server_only_or_docker_socket_env(client, env_name, env_value):
    payload = multi_service_payload()
    payload["services"][0]["build_env"] = {env_name: env_value}

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "reserved" in response.json()["detail"]


@pytest.mark.parametrize("field_name", ["build_env", "runtime_env", "required_secrets"])
def test_rejects_project_database_server_only_env_names(client, field_name):
    payload = multi_service_payload()
    if field_name == "required_secrets":
        payload["services"][1][field_name] = ["HEIMDALL_PROJECT_DATABASE_ADMIN_URL"]
    else:
        payload["services"][1][field_name] = {"HEIMDALL_PROJECT_DATABASE_ADMIN_URL": "postgres://admin:secret@db/postgres"}

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "reserved" in response.json()["detail"]


def test_rejects_invalid_required_secret_name(client):
    payload = multi_service_payload()
    payload["services"][1]["required_secrets"] = ["jwt-secret"]

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "Required secret names" in response.json()["detail"]
