import base64
import json
from urllib.parse import quote

from app.config import get_settings
from app.db import connect
from app.services import project_database_secrets
from app.services.executor_local_docker import ExecutorDeploymentResult, ExecutorServiceResult

from .test_projects import multi_service_payload, project_payload


def create_project(client):
    response = client.post("/api/projects", json=project_payload())
    assert response.status_code == 201, response.text
    return response.json()


def create_multi_service_project(client):
    response = client.post("/api/projects", json=multi_service_payload())
    assert response.status_code == 201, response.text
    return response.json()


def install_active_project_database(
    project_id,
    *,
    service_name="app",
    env_var_name="DATABASE_URL",
    password="generated-db-password",
    network_name="heimdall-project-db",
    write_secret=True,
):
    settings = get_settings()
    ref = f"project-databases/{project_id}/password"
    database_name = f"hm_{project_id}_db"
    role_name = f"hm_{project_id}_role"
    with connect(settings) as connection:
        service_row = connection.execute(
            "SELECT id FROM project_services WHERE project_id = ? AND name = ?",
            (project_id, service_name),
        ).fetchone()
        service_id = service_row["id"] if service_row else None
        database_id = f"pdb_{project_id[-8:]}"
        connection.execute(
            """
            INSERT INTO project_databases (
                id, project_id, database_name, role_name, password_secret_ref, app_host,
                app_port, network_name, status, retention_policy, created_at, updated_at, provisioned_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                database_id,
                project_id,
                database_name,
                role_name,
                ref,
                "project-postgres",
                5432,
                network_name,
                "active",
                "retain",
                "2026-06-08T00:00:00+00:00",
                "2026-06-08T00:00:00+00:00",
                "2026-06-08T00:00:00+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO project_database_bindings (
                id, project_database_id, project_id, service_id, env_var_name, required_secret_name, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"pdbind_{project_id[-8:]}",
                database_id,
                project_id,
                service_id,
                env_var_name,
                env_var_name,
                "2026-06-08T00:00:00+00:00",
                "2026-06-08T00:00:00+00:00",
            ),
        )
    if write_secret:
        project_database_secrets.write_secret(settings, ref, password)
    database_url = (
        f"postgresql://{quote(role_name, safe='')}:{quote(password, safe='')}"
        f"@project-postgres:5432/{quote(database_name, safe='')}"
    )
    return {
        "database_id": database_id,
        "database_name": database_name,
        "role_name": role_name,
        "password": password,
        "password_secret_ref": ref,
        "database_url": database_url,
    }


def test_manual_deploy_creates_dry_run_release_and_logs(client):
    project = create_project(client)

    deploy_response = client.post(
        f"/api/projects/{project['id']}/deployments",
        json={"ref": "main", "trigger_type": "manual", "dry_run": True},
    )
    assert deploy_response.status_code == 201, deploy_response.text

    body = deploy_response.json()
    deployment = body["deployment"]
    release = body["release"]
    assert deployment["status"] == "dry_run_success"
    assert deployment["is_dry_run"] is True
    assert release["status"] == "simulated"
    assert release["is_dry_run"] is True
    assert release["is_current"] is False
    assert release["rollback_supported"] is False

    project_after = client.get(f"/api/projects/{project['id']}").json()
    assert project_after["current_release_id"] is None
    assert project_after["current_commit_sha"] is None
    assert project_after["has_real_preview"] is False
    assert project_after["last_deployment_status"] == "dry_run_success"

    deployment_detail = client.get(f"/api/deployments/{deployment['id']}")
    assert deployment_detail.status_code == 200
    assert deployment_detail.json()["target_release_id"] == release["id"]

    logs_response = client.get(f"/api/deployments/{deployment['id']}/logs")
    assert logs_response.status_code == 200
    content = logs_response.json()["content"]
    assert "[workspace]" in content
    assert "[build]" in content
    assert "[container]" in content
    assert "[health]" in content
    assert "[summary]" in content
    assert "no preview container was started" in content

    releases_response = client.get(f"/api/projects/{project['id']}/releases")
    assert releases_response.status_code == 200
    releases = releases_response.json()
    assert len(releases) == 1
    assert releases[0]["status"] == "simulated"


def test_rollback_placeholder_records_safe_failure(client):
    project = create_project(client)
    deploy_response = client.post(
        f"/api/projects/{project['id']}/deployments",
        json={"ref": "main", "trigger_type": "manual", "dry_run": True},
    )
    release_id = deploy_response.json()["release"]["id"]

    rollback_response = client.post(
        f"/api/projects/{project['id']}/rollback",
        json={"release_id": release_id},
    )
    assert rollback_response.status_code == 409
    body = rollback_response.json()
    assert body["supported"] is False
    assert "simulated dry-run releases" in body["message"]
    assert body["deployment"]["status"] == "rollback_failed"


def test_manual_deploy_real_success_marks_current_release(client, monkeypatch):
    project = create_project(client)
    commit_sha = "a" * 40

    class FakeExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def deploy_preview(self, request):
            assert request.requested_ref == "main"
            assert request.release_id
            return ExecutorDeploymentResult(
                log_content="[workspace]\nok\n\n[build]\nok\n\n[container]\nok\n\n[health]\nok\n\n[summary]\nok",
                is_dry_run=False,
                status_message="Preview deployment completed successfully.",
                success=True,
                resolved_commit_sha=commit_sha,
                image_tag="heimdall/preview-api:aaaaaaa",
                image_id="sha256:image",
            )

    monkeypatch.setattr("app.services.deployments.RealLocalDockerExecutor", FakeExecutor)

    deploy_response = client.post(
        f"/api/projects/{project['id']}/deployments",
        json={"ref": "main", "trigger_type": "manual"},
    )
    assert deploy_response.status_code == 201, deploy_response.text

    body = deploy_response.json()
    deployment = body["deployment"]
    release = body["release"]
    assert deployment["status"] == "success"
    assert deployment["is_dry_run"] is False
    assert deployment["resolved_commit_sha"] == commit_sha
    assert release["status"] == "current"
    assert release["is_current"] is True
    assert release["is_dry_run"] is False

    project_after = client.get(f"/api/projects/{project['id']}").json()
    assert project_after["current_release_id"] == release["id"]
    assert project_after["current_commit_sha"] == commit_sha
    assert project_after["status"] == "healthy"
    assert project_after["has_real_preview"] is True

    with connect(get_settings()) as connection:
        allocation = connection.execute(
            "SELECT status FROM port_allocations WHERE project_id = ?",
            (project["id"],),
        ).fetchone()
    assert allocation["status"] == "active"


def test_manual_deploy_real_build_failure_creates_no_release(client, monkeypatch):
    project = create_project(client)

    class FailingExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def deploy_preview(self, request):
            return ExecutorDeploymentResult(
                log_content="[workspace]\nok\n\n[build]\nfailed\n\n[summary]\nfailed",
                is_dry_run=False,
                status_message="Build failed: docker build exited with code 1.",
                success=False,
            )

    monkeypatch.setattr("app.services.deployments.RealLocalDockerExecutor", FailingExecutor)

    deploy_response = client.post(
        f"/api/projects/{project['id']}/deployments",
        json={"ref": "main", "trigger_type": "manual"},
    )
    assert deploy_response.status_code == 201, deploy_response.text

    body = deploy_response.json()
    assert body["release"] is None
    assert body["deployment"]["status"] == "failed"
    assert body["deployment"]["is_dry_run"] is False
    assert "Build failed" in body["deployment"]["status_message"]

    project_after = client.get(f"/api/projects/{project['id']}").json()
    assert project_after["current_release_id"] is None
    assert project_after["current_commit_sha"] is None
    assert project_after["status"] == "failed"
    assert client.get(f"/api/projects/{project['id']}/releases").json() == []


def test_second_real_deploy_supersedes_previous_current_release(client, monkeypatch):
    project = create_project(client)
    commits = iter(["b" * 40, "c" * 40])

    class SequencedExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def deploy_preview(self, request):
            commit_sha = next(commits)
            return ExecutorDeploymentResult(
                log_content="[workspace]\nok\n\n[build]\nok\n\n[container]\nok\n\n[health]\nok\n\n[summary]\nok",
                is_dry_run=False,
                status_message="Preview deployment completed successfully.",
                success=True,
                resolved_commit_sha=commit_sha,
                image_tag=f"heimdall/preview-api:{commit_sha[:7]}",
                image_id=f"sha256:{commit_sha[:12]}",
            )

    monkeypatch.setattr("app.services.deployments.RealLocalDockerExecutor", SequencedExecutor)

    first_response = client.post(f"/api/projects/{project['id']}/deployments", json={"ref": "main"})
    second_response = client.post(f"/api/projects/{project['id']}/deployments", json={"ref": "main"})
    assert first_response.status_code == 201, first_response.text
    assert second_response.status_code == 201, second_response.text

    first_release = first_response.json()["release"]
    second_release = second_response.json()["release"]
    releases = client.get(f"/api/projects/{project['id']}/releases").json()
    by_id = {release["id"]: release for release in releases}
    assert by_id[first_release["id"]]["status"] == "superseded"
    assert by_id[first_release["id"]]["is_current"] is False
    assert by_id[second_release["id"]]["status"] == "current"
    assert by_id[second_release["id"]]["is_current"] is True

    project_after = client.get(f"/api/projects/{project['id']}").json()
    assert project_after["current_release_id"] == second_release["id"]
    assert project_after["current_commit_sha"] == "c" * 40


def test_real_deploy_redacts_provider_tokens_and_webhook_secrets_from_logs_and_response(client, monkeypatch):
    github_token = "github-super-secret-token"
    github_webhook_secret = "github-super-secret-webhook"
    gitlab_token = "gitlab-super-secret-token"
    gitlab_webhook_secret = "gitlab-super-secret-webhook"
    github_encoded = base64.b64encode(f"x-access-token:{github_token}".encode("utf-8")).decode("ascii")
    gitlab_encoded = base64.b64encode(f"oauth2:{gitlab_token}".encode("utf-8")).decode("ascii")
    monkeypatch.setenv("HEIMDALL_GITHUB_API_TOKEN", github_token)
    monkeypatch.setenv("HEIMDALL_GITHUB_WEBHOOK_SECRET", github_webhook_secret)
    monkeypatch.setenv("HEIMDALL_GITLAB_API_TOKEN", gitlab_token)
    monkeypatch.setenv("HEIMDALL_GITLAB_WEBHOOK_SECRET", gitlab_webhook_secret)
    get_settings.cache_clear()
    project = create_project(client)

    class LeakyExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def deploy_preview(self, request):
            return ExecutorDeploymentResult(
                log_content=(
                    f"[workspace]\nraw {github_token}\nheader {github_encoded}\nwebhook {github_webhook_secret}\n"
                    f"gitlab {gitlab_token}\ngitlab header {gitlab_encoded}\ngitlab webhook {gitlab_webhook_secret}\n"
                    "\n[summary]\nok"
                ),
                is_dry_run=False,
                status_message=(
                    f"done without leaking {github_token} {github_webhook_secret} "
                    f"{gitlab_token} {gitlab_webhook_secret}"
                ),
                success=True,
                resolved_commit_sha="d" * 40,
                image_tag="heimdall/preview-api:ddddddd",
            )

    monkeypatch.setattr("app.services.deployments.RealLocalDockerExecutor", LeakyExecutor)

    deploy_response = client.post(f"/api/projects/{project['id']}/deployments", json={"ref": "main"})
    assert deploy_response.status_code == 201, deploy_response.text
    response_text = json.dumps(deploy_response.json())
    for secret in (github_token, github_webhook_secret, gitlab_token, gitlab_webhook_secret):
        assert secret not in response_text
    assert github_encoded not in response_text
    assert gitlab_encoded not in response_text
    assert "[redacted]" in response_text

    deployment_id = deploy_response.json()["deployment"]["id"]
    logs_response = client.get(f"/api/deployments/{deployment_id}/logs")
    assert logs_response.status_code == 200
    log_content = logs_response.json()["content"]
    for secret in (github_token, github_webhook_secret, gitlab_token, gitlab_webhook_secret):
        assert secret not in log_content
    assert github_encoded not in log_content
    assert gitlab_encoded not in log_content
    assert "[redacted]" in log_content


def test_real_deploy_redacts_managed_database_runtime_values_and_does_not_persist_them(client, monkeypatch):
    project = create_project(client)
    managed = install_active_project_database(project["id"], password="generated-db-password/with:special")

    class LeakyManagedDatabaseExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def deploy_preview(self, request):
            service = request.project["services"][0]
            assert service["managed_runtime_env"]["DATABASE_URL"] == managed["database_url"]
            assert service["managed_database_network"] == "heimdall-project-db"
            return ExecutorDeploymentResult(
                log_content=f"[container]\nurl {managed['database_url']}\npassword {managed['password']}\n\n[summary]\nok",
                is_dry_run=False,
                status_message=f"done {managed['database_url']} {managed['password']}",
                success=True,
                resolved_commit_sha="f" * 40,
                image_tag="heimdall/preview-api:fffffff",
                image_id="sha256:image",
            )

    monkeypatch.setattr("app.services.deployments.RealLocalDockerExecutor", LeakyManagedDatabaseExecutor)

    deploy_response = client.post(f"/api/projects/{project['id']}/deployments", json={"ref": "main"})

    assert deploy_response.status_code == 201, deploy_response.text
    response_text = json.dumps(deploy_response.json())
    for forbidden in (
        managed["database_url"],
        managed["password"],
        managed["password_secret_ref"],
        managed["database_name"],
        managed["role_name"],
        "postgres://",
    ):
        assert forbidden not in response_text
    assert "[redacted]" in response_text

    deployment_id = deploy_response.json()["deployment"]["id"]
    logs_response = client.get(f"/api/deployments/{deployment_id}/logs")
    assert logs_response.status_code == 200
    log_content = logs_response.json()["content"]
    assert managed["database_url"] not in log_content
    assert managed["password"] not in log_content
    assert "[redacted]" in log_content

    with connect(get_settings()) as connection:
        service_row = connection.execute("SELECT runtime_env_json FROM project_services WHERE project_id = ?", (project["id"],)).fetchone()
        release_text = json.dumps(
            [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT releases.*, release_services.*
                    FROM releases
                    LEFT JOIN release_services ON release_services.release_id = releases.id
                    WHERE releases.project_id = ?
                    """,
                    (project["id"],),
                ).fetchall()
            ],
            sort_keys=True,
        )
    assert managed["database_url"] not in service_row["runtime_env_json"]
    assert managed["password"] not in service_row["runtime_env_json"]
    assert managed["database_url"] not in release_text
    assert managed["password"] not in release_text


def test_real_deploy_rejects_reserved_managed_database_network_before_executor(client, monkeypatch):
    project = create_project(client)
    install_active_project_database(project["id"], network_name="heimdall-control")

    class UnexpectedExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def deploy_preview(self, request):  # pragma: no cover - should not be reached.
            raise AssertionError("executor should not run when DB network is reserved")

    monkeypatch.setattr("app.services.deployments.RealLocalDockerExecutor", UnexpectedExecutor)

    response = client.post(f"/api/projects/{project['id']}/deployments", json={"ref": "main"})

    assert response.status_code == 422
    assert "heimdall-control" in response.json()["detail"]
    with connect(get_settings()) as connection:
        deployment_count = connection.execute(
            "SELECT COUNT(*) AS count FROM deployments WHERE project_id = ?",
            (project["id"],),
        ).fetchone()["count"]
    assert deployment_count == 0


def test_multi_service_real_deploy_creates_current_release_service_manifest(client, monkeypatch):
    project = create_multi_service_project(client)
    commit_sha = "e" * 40

    class MultiServiceExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def deploy_preview(self, request):
            assert request.project["deploy_mode"] == "multi_service_dockerfile"
            assert "run_as_heimdall_child" not in request.project
            assert [service["name"] for service in request.project["services"]] == ["backend", "frontend"]
            assert all("run_as_heimdall_child" not in service for service in request.project["services"])
            assert request.release_id
            return ExecutorDeploymentResult(
                log_content=(
                    "[workspace]\nok\n\n[build:backend]\nok\n\n[build:frontend]\nok\n\n"
                    "[container:backend]\nok\n\n[container:frontend]\nok\n\n"
                    "[health:backend]\nok\n\n[health:frontend]\nok\n\n[summary]\nok"
                ),
                is_dry_run=False,
                status_message="Multi-service preview deployment completed successfully.",
                success=True,
                resolved_commit_sha=commit_sha,
                image_tag="heimdall/portfolio-frontend:eeeeeee",
                image_id="sha256:frontend",
                service_results=(
                    ExecutorServiceResult(
                        name="backend",
                        image_tag="heimdall/portfolio-backend:eeeeeee",
                        image_id="sha256:backend",
                        container_name="heimdall-preview-portfolio-backend",
                        container_id="container-backend",
                        container_port=8000,
                        public=False,
                        preview_url=None,
                        internal_url="http://backend:8000",
                    ),
                    ExecutorServiceResult(
                        name="frontend",
                        image_tag="heimdall/portfolio-frontend:eeeeeee",
                        image_id="sha256:frontend",
                        container_name="heimdall-preview-portfolio-frontend",
                        container_id="container-frontend",
                        container_port=3000,
                        public=True,
                        preview_url=project["preview_url"],
                        internal_url=None,
                    ),
                ),
            )

    monkeypatch.setattr("app.services.deployments.RealLocalDockerExecutor", MultiServiceExecutor)

    deploy_response = client.post(f"/api/projects/{project['id']}/deployments", json={"ref": "main"})

    assert deploy_response.status_code == 201, deploy_response.text
    body = deploy_response.json()
    release = body["release"]
    assert body["deployment"]["status"] == "success"
    assert body["deployment"]["image_tag"] == "heimdall/portfolio-frontend:eeeeeee"
    assert release["image_tag"] == "heimdall/portfolio-frontend:eeeeeee"
    assert release["rollback_supported"] is False
    services = {service["name"]: service for service in release["services"]}
    assert services["frontend"]["public"] is True
    assert services["frontend"]["preview_url"] == project["preview_url"]
    assert services["backend"]["public"] is False
    assert services["backend"]["internal_url"] == "http://backend:8000"

    releases = client.get(f"/api/projects/{project['id']}/releases").json()
    assert releases[0]["services"] == release["services"]
    with connect(get_settings()) as connection:
        rows = connection.execute(
            "SELECT service_name, image_tag FROM release_services WHERE release_id = ? ORDER BY service_name",
            (release["id"],),
        ).fetchall()
    assert [(row["service_name"], row["image_tag"]) for row in rows] == [
        ("backend", "heimdall/portfolio-backend:eeeeeee"),
        ("frontend", "heimdall/portfolio-frontend:eeeeeee"),
    ]


def test_multi_service_real_deploy_failure_creates_no_release_or_manifest(client, monkeypatch):
    project = create_multi_service_project(client)

    class FailingMultiServiceExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def deploy_preview(self, request):
            return ExecutorDeploymentResult(
                log_content="[workspace]\nok\n\n[build:backend]\nfailed\n\n[summary]\nfailed",
                is_dry_run=False,
                status_message="Build failed for backend: docker build exited with code 1.",
                success=False,
            )

    monkeypatch.setattr("app.services.deployments.RealLocalDockerExecutor", FailingMultiServiceExecutor)

    deploy_response = client.post(f"/api/projects/{project['id']}/deployments", json={"ref": "main"})

    assert deploy_response.status_code == 201, deploy_response.text
    assert deploy_response.json()["release"] is None
    assert deploy_response.json()["deployment"]["status"] == "failed"
    with connect(get_settings()) as connection:
        release_count = connection.execute("SELECT COUNT(*) AS count FROM releases").fetchone()["count"]
        service_count = connection.execute("SELECT COUNT(*) AS count FROM release_services").fetchone()["count"]
    assert release_count == 0
    assert service_count == 0


def test_multi_service_dry_run_manifest_has_no_secret_values(client):
    project = create_multi_service_project(client)
    forbidden_value = "postgres://user:password@db/app"

    deploy_response = client.post(
        f"/api/projects/{project['id']}/deployments",
        json={"ref": "main", "trigger_type": "manual", "dry_run": True},
    )

    assert deploy_response.status_code == 201, deploy_response.text
    response_text = json.dumps(deploy_response.json())
    assert forbidden_value not in response_text
    release = deploy_response.json()["release"]
    assert {service["name"] for service in release["services"]} == {"backend", "frontend"}
    assert all(service["status"] == "simulated" for service in release["services"])

    logs_response = client.get(f"/api/deployments/{deploy_response.json()['deployment']['id']}/logs")
    assert forbidden_value not in logs_response.json()["content"]


def test_dry_run_does_not_read_or_assemble_managed_database_secret(client, monkeypatch):
    project = create_multi_service_project(client)
    managed = install_active_project_database(
        project["id"],
        service_name="backend",
        password="dry-run-db-password",
        write_secret=False,
    )

    def fail_read_secret(settings, ref):  # pragma: no cover - should not be called.
        raise AssertionError("dry-run should not read managed DB secrets")

    monkeypatch.setattr(project_database_secrets, "read_secret", fail_read_secret)

    deploy_response = client.post(
        f"/api/projects/{project['id']}/deployments",
        json={"ref": "main", "trigger_type": "manual", "dry_run": True},
    )

    assert deploy_response.status_code == 201, deploy_response.text
    response_text = json.dumps(deploy_response.json())
    assert managed["database_url"] not in response_text
    assert managed["password"] not in response_text
    logs_response = client.get(f"/api/deployments/{deploy_response.json()['deployment']['id']}/logs")
    assert managed["database_url"] not in logs_response.json()["content"]
    assert managed["password"] not in logs_response.json()["content"]
