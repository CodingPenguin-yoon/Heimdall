import base64
import json

from app.config import get_settings
from app.db import connect
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


def test_real_deploy_redacts_provider_token_from_logs_and_response(client, monkeypatch):
    token = "super-secret-token"
    encoded = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
    monkeypatch.setenv("HEIMDALL_GITHUB_API_TOKEN", token)
    get_settings.cache_clear()
    project = create_project(client)

    class LeakyExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def deploy_preview(self, request):
            return ExecutorDeploymentResult(
                log_content=f"[workspace]\nraw {token}\nheader {encoded}\n\n[summary]\nok",
                is_dry_run=False,
                status_message=f"done without leaking {token}",
                success=True,
                resolved_commit_sha="d" * 40,
                image_tag="heimdall/preview-api:ddddddd",
            )

    monkeypatch.setattr("app.services.deployments.RealLocalDockerExecutor", LeakyExecutor)

    deploy_response = client.post(f"/api/projects/{project['id']}/deployments", json={"ref": "main"})
    assert deploy_response.status_code == 201, deploy_response.text
    response_text = json.dumps(deploy_response.json())
    assert token not in response_text
    assert encoded not in response_text
    assert "[redacted]" in response_text

    deployment_id = deploy_response.json()["deployment"]["id"]
    logs_response = client.get(f"/api/deployments/{deployment_id}/logs")
    assert logs_response.status_code == 200
    log_content = logs_response.json()["content"]
    assert token not in log_content
    assert encoded not in log_content
    assert "[redacted]" in log_content


def test_multi_service_real_deploy_creates_current_release_service_manifest(client, monkeypatch):
    project = create_multi_service_project(client)
    commit_sha = "e" * 40

    class MultiServiceExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def deploy_preview(self, request):
            assert request.project["deploy_mode"] == "multi_service_dockerfile"
            assert [service["name"] for service in request.project["services"]] == ["backend", "frontend"]
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
