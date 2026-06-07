import sqlite3
from collections.abc import Generator

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
        "HEIMDALL_CHILD_RUNNER_ENABLED",
        "HEIMDALL_CHILD_ROOT_HOST",
        "HEIMDALL_CHILD_ROOT_CONTAINER",
    ):
        monkeypatch.setenv(key, "")

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def child_client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    runtime_dir = tmp_path / "runtime"
    database_path = tmp_path / "heimdall.db"
    host_root = tmp_path / "child-host"
    container_root = tmp_path / "child-container"
    host_root.mkdir()
    container_root.mkdir()

    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("HEIMDALL_PREVIEW_HOST", "preview.local")
    monkeypatch.setenv("HEIMDALL_PREVIEW_PORT_START", "18000")
    monkeypatch.setenv("HEIMDALL_PREVIEW_PORT_END", "18010")
    monkeypatch.setenv("HEIMDALL_CHILD_RUNNER_ENABLED", "true")
    monkeypatch.setenv("HEIMDALL_CHILD_ROOT_HOST", str(host_root))
    monkeypatch.setenv("HEIMDALL_CHILD_ROOT_CONTAINER", str(container_root))
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
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def child_enabled_missing_roots_client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    runtime_dir = tmp_path / "runtime"
    database_path = tmp_path / "heimdall.db"
    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("HEIMDALL_PREVIEW_HOST", "preview.local")
    monkeypatch.setenv("HEIMDALL_PREVIEW_PORT_START", "18000")
    monkeypatch.setenv("HEIMDALL_PREVIEW_PORT_END", "18010")
    monkeypatch.setenv("HEIMDALL_CHILD_RUNNER_ENABLED", "true")
    monkeypatch.setenv("HEIMDALL_CHILD_ROOT_HOST", "")
    monkeypatch.setenv("HEIMDALL_CHILD_ROOT_CONTAINER", "")

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
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


def test_create_and_list_project(client):
    create_response = client.post("/api/projects", json=project_payload())
    assert create_response.status_code == 201, create_response.text

    created = create_response.json()
    assert created["slug"] == "preview-api"
    assert created["preview_port"] == 18000
    assert created["preview_url"] == "http://preview.local:18000"
    assert created["has_real_preview"] is False
    assert created["run_as_heimdall_child"] is False
    assert created["services"][0]["run_as_heimdall_child"] is False

    list_response = client.get("/api/projects")
    assert list_response.status_code == 200
    projects = list_response.json()
    assert len(projects) == 1
    assert projects[0]["id"] == created["id"]
    assert projects[0]["run_as_heimdall_child"] is False


def test_no_volume_project_create_works_without_volume_roots(client):
    response = client.post("/api/projects", json=project_payload(name="No Volume API"))

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["services"][0]["name"] == "app"
    assert created["services"][0]["volumes"] == []


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


def test_db_bootstrap_adds_child_flag_column_to_existing_projects_table(tmp_path):
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
        columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)").fetchall()}
    assert "run_as_heimdall_child" in columns


def test_db_bootstrap_adds_service_child_flag_column_and_unique_index_to_existing_project_services_table(tmp_path):
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
        columns = {row[1] for row in connection.execute("PRAGMA table_info(project_services)").fetchall()}
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(project_services)").fetchall()}
        index_sql = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'index' AND name = 'idx_project_services_one_child_per_project'
            """
        ).fetchone()[0]
    assert "run_as_heimdall_child" in columns
    assert "idx_project_services_one_child_per_project" in indexes
    assert "WHERE run_as_heimdall_child = 1" in index_sql


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


def test_child_project_roundtrips_and_preserves_on_update(child_client):
    create_response = child_client.post(
        "/api/projects",
        json=project_payload(run_as_heimdall_child=True),
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["run_as_heimdall_child"] is True
    assert created["services"][0]["run_as_heimdall_child"] is True

    read_response = child_client.get(f"/api/projects/{created['id']}")
    assert read_response.status_code == 200
    assert read_response.json()["run_as_heimdall_child"] is True
    assert read_response.json()["services"][0]["run_as_heimdall_child"] is True

    patch_response = child_client.patch(f"/api/projects/{created['id']}", json={"name": "Child API"})
    assert patch_response.status_code == 200, patch_response.text
    assert patch_response.json()["run_as_heimdall_child"] is True
    assert patch_response.json()["services"][0]["run_as_heimdall_child"] is True

    disable_response = child_client.patch(f"/api/projects/{created['id']}", json={"run_as_heimdall_child": False})
    assert disable_response.status_code == 200, disable_response.text
    assert disable_response.json()["run_as_heimdall_child"] is False
    assert disable_response.json()["services"][0]["run_as_heimdall_child"] is False


def test_child_project_create_rejects_disabled_gate(client):
    response = client.post("/api/projects", json=project_payload(run_as_heimdall_child=True))

    assert response.status_code == 422
    assert "HEIMDALL_CHILD_RUNNER_ENABLED" in response.json()["detail"]


def test_child_project_create_rejects_missing_roots(child_enabled_missing_roots_client):
    response = child_enabled_missing_roots_client.post(
        "/api/projects",
        json=project_payload(run_as_heimdall_child=True),
    )

    assert response.status_code == 422
    assert "HEIMDALL_CHILD_ROOT_HOST" in response.json()["detail"]


def test_child_multi_service_project_roundtrips_exactly_one_child_service(child_client):
    payload = multi_service_payload()
    for service in payload["services"]:
        service["run_as_heimdall_child"] = service["name"] == "backend"

    response = child_client.post("/api/projects", json=payload)

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["run_as_heimdall_child"] is True
    services = {service["name"]: service for service in created["services"]}
    assert services["backend"]["run_as_heimdall_child"] is True
    assert services["frontend"]["run_as_heimdall_child"] is False

    read_response = child_client.get(f"/api/projects/{created['id']}")
    assert read_response.status_code == 200
    read_services = {service["name"]: service for service in read_response.json()["services"]}
    assert read_response.json()["run_as_heimdall_child"] is True
    assert read_services["backend"]["run_as_heimdall_child"] is True
    assert read_services["frontend"]["run_as_heimdall_child"] is False


def test_child_multi_service_project_rejects_multiple_child_services(child_client):
    payload = multi_service_payload()
    for service in payload["services"]:
        service["run_as_heimdall_child"] = True

    response = child_client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "exactly one service" in response.json()["detail"]


def test_child_multi_service_project_rejects_top_level_child_without_marked_service(child_client):
    response = child_client.post(
        "/api/projects",
        json=multi_service_payload(run_as_heimdall_child=True),
    )

    assert response.status_code == 422
    assert "exactly one service" in response.json()["detail"]


def test_child_project_real_deploy_rechecks_gate_before_executor(child_client, monkeypatch):
    create_response = child_client.post(
        "/api/projects",
        json=project_payload(run_as_heimdall_child=True),
    )
    assert create_response.status_code == 201, create_response.text
    project = create_response.json()

    class UnexpectedExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def deploy_preview(self, request):  # pragma: no cover - should not be reached.
            raise AssertionError("executor should not run when child gate is disabled")

    monkeypatch.setattr("app.services.deployments.RealLocalDockerExecutor", UnexpectedExecutor)
    monkeypatch.setenv("HEIMDALL_CHILD_RUNNER_ENABLED", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    response = child_client.post(f"/api/projects/{project['id']}/deployments", json={"ref": "main"})
    get_settings.cache_clear()

    assert response.status_code == 422
    assert "HEIMDALL_CHILD_RUNNER_ENABLED" in response.json()["detail"]


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


def test_rejects_invalid_required_secret_name(client):
    payload = multi_service_payload()
    payload["services"][1]["required_secrets"] = ["jwt-secret"]

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "Required secret names" in response.json()["detail"]
