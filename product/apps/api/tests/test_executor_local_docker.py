from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from app.config import Settings
from app.services.executor_local_docker import (
    CommandResult,
    ExecutorDeploymentRequest,
    RealLocalDockerExecutor,
)


COMMIT_SHA = "a" * 40
IMAGE_ID = "sha256:1234567890abcdef"


class RecordingRunner:
    def __init__(
        self,
        *,
        commit_sha: str = COMMIT_SHA,
        image_id: str = IMAGE_ID,
        existing_containers: str | dict[str, str] = "",
        network_exists: bool = False,
        network_labels: dict[str, str] | None = None,
    ):
        self.calls: list[list[str]] = []
        self.commit_sha = commit_sha
        self.image_id = image_id
        self.existing_containers = existing_containers
        self.network_exists = network_exists
        self.network_labels = network_labels
        self.leaky_output = ""

    def run(self, argv, *, cwd: Path | None = None) -> CommandResult:
        assert isinstance(argv, list)
        assert cwd is None
        self.calls.append(list(argv))

        if argv[0] == "git" and "clone" in argv:
            repo_dir = Path(argv[-1])
            repo_dir.mkdir(parents=True, exist_ok=True)
            (repo_dir / ".git").mkdir(exist_ok=True)
            (repo_dir / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
            return CommandResult(exit_code=0, stderr=self.leaky_output)
        if argv[0] == "git" and "fetch" in argv:
            return CommandResult(exit_code=0)
        if argv[0] == "git" and "checkout" in argv:
            return CommandResult(exit_code=0)
        if argv[0] == "git" and "rev-parse" in argv:
            return CommandResult(exit_code=0, stdout=f"{self.commit_sha}\n")
        if argv[:2] == ["docker", "build"]:
            return CommandResult(exit_code=0)
        if argv[:3] == ["docker", "image", "inspect"]:
            image_tag = argv[-1]
            if "-backend:" in image_tag:
                return CommandResult(exit_code=0, stdout="sha256:backend\n")
            if "-frontend:" in image_tag:
                return CommandResult(exit_code=0, stdout="sha256:frontend\n")
            return CommandResult(exit_code=0, stdout=f"{self.image_id}\n")
        if argv[:3] == ["docker", "ps", "-aq"]:
            if isinstance(self.existing_containers, dict):
                service_filter = next((part for part in argv if part.startswith("label=heimdall.service=")), "")
                service_name = service_filter.removeprefix("label=heimdall.service=")
                return CommandResult(exit_code=0, stdout=self.existing_containers.get(service_name, ""))
            return CommandResult(exit_code=0, stdout=self.existing_containers)
        if argv[:2] == ["docker", "stop"]:
            return CommandResult(exit_code=0)
        if argv[:2] == ["docker", "rm"]:
            return CommandResult(exit_code=0)
        if argv[:3] == ["docker", "network", "inspect"]:
            if not self.network_exists:
                return CommandResult(exit_code=1)
            return CommandResult(
                exit_code=0,
                stdout=json.dumps([{"Labels": self.network_labels if self.network_labels is not None else {}}]),
            )
        if argv[:3] == ["docker", "network", "create"]:
            return CommandResult(exit_code=0)
        if argv[:2] == ["docker", "run"]:
            if "--rm" in argv:
                return CommandResult(exit_code=0)
            return CommandResult(exit_code=0, stdout="container-id\n")

        raise AssertionError(f"unexpected command: {argv}")


class StaticHealthClient:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.calls: list[tuple[str, float]] = []

    def get_status_code(self, url: str, *, timeout: float) -> int:
        self.calls.append((url, timeout))
        return self.status_code


def make_settings(
    tmp_path: Path,
    *,
    github_token: str | None = None,
    github_webhook_secret: str | None = None,
    gitlab_base_url: str | None = None,
    gitlab_token: str | None = None,
    gitlab_webhook_secret: str | None = None,
    child_runner_enabled: bool = False,
    child_root_host: Path | None = None,
    child_root_container: Path | None = None,
) -> Settings:
    settings = Settings(
        runtime_dir=tmp_path / "runtime",
        database_url=f"sqlite:///{tmp_path / 'heimdall.db'}",
        public_base_url="http://127.0.0.1:8000",
        preview_host="127.0.0.1",
        preview_port_start=18000,
        preview_port_end=18010,
        github_api_token=github_token,
        github_webhook_secret=github_webhook_secret,
        gitlab_base_url=gitlab_base_url,
        gitlab_api_token=gitlab_token,
        gitlab_webhook_secret=gitlab_webhook_secret,
        child_runner_enabled=child_runner_enabled,
        child_root_host=child_root_host,
        child_root_container=child_root_container,
    )
    settings.ensure_runtime_dirs()
    return settings


def make_project(**overrides) -> dict[str, object]:
    project: dict[str, object] = {
        "id": "project-1",
        "name": "Preview API",
        "slug": "preview-api",
        "provider": "github",
        "repo_url": "https://github.com/example/preview-api.git",
        "tracked_branch": "main",
        "build_context_path": ".",
        "dockerfile_path": "Dockerfile",
        "preview_host": "127.0.0.1",
        "preview_port": 18000,
        "container_port": 8080,
        "health_check_path": "/health",
        "health_check_url": None,
        "preview_url": "http://127.0.0.1:18000",
    }
    project.update(overrides)
    return project


def make_multi_service_project(**overrides) -> dict[str, object]:
    project = make_project(
        name="Portfolio",
        slug="portfolio",
        repo_url="https://github.com/example/portfolio.git",
        deploy_mode="multi_service_dockerfile",
        build_context_path="frontend",
        dockerfile_path="frontend/Dockerfile",
        container_port=3000,
        health_check_path="/",
        preview_url="http://127.0.0.1:18000",
        services=[
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
                "required_secrets": ["DATABASE_URL"],
            },
            {
                "name": "frontend",
                "build_context_path": "frontend",
                "dockerfile_path": "frontend/Dockerfile",
                "container_port": 3000,
                "public": True,
                "health_check_path": "/",
                "startup_order": 20,
                "build_env": {"VITE_API_BASE_URL": "/api"},
                "runtime_env": {"BACKEND_INTERNAL_URL": "http://backend:8000"},
                "required_secrets": [],
            },
        ],
    )
    project.update(overrides)
    return project


def make_request(project: dict[str, object]) -> ExecutorDeploymentRequest:
    return ExecutorDeploymentRequest(
        project=project,
        deployment_id="deployment-1",
        release_id="release-1",
        timestamp="2026-06-04T00:00:00+00:00",
        requested_ref="main",
    )


def prepare_existing_repo(settings: Settings, project: dict[str, object]) -> Path:
    repo_dir = settings.workspaces_dir / str(project["id"]) / "repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()
    (repo_dir / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    return repo_dir


def prepare_existing_multi_service_repo(settings: Settings, project: dict[str, object]) -> Path:
    repo_dir = settings.workspaces_dir / str(project["id"]) / "repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()
    for service in project["services"]:
        service_dir = repo_dir / str(service["name"])
        service_dir.mkdir()
        (service_dir / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    return repo_dir


def find_call(calls: list[list[str]], *parts: str) -> list[str]:
    for call in calls:
        if all(part in call for part in parts):
            return call
    raise AssertionError(f"command containing {parts} was not run")


def env_values(argv: list[str]) -> list[str]:
    return [value for index, value in enumerate(argv) if index > 0 and argv[index - 1] == "--env"]


def test_real_local_docker_executor_success_fetches_builds_replaces_and_reports_metadata(tmp_path):
    settings = make_settings(tmp_path)
    project = make_project()
    prepare_existing_repo(settings, project)
    runner = RecordingRunner()
    health = StaticHealthClient(200)
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=health,
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is True
    assert result.resolved_commit_sha == COMMIT_SHA
    assert result.image_tag == "heimdall/preview-api:aaaaaaa"
    assert result.image_id == IMAGE_ID
    assert result.is_dry_run is False
    assert [line for line in result.log_content.splitlines() if line.startswith("[")] == [
        "[workspace]",
        "[build]",
        "[container]",
        "[health]",
        "[summary]",
    ]

    find_call(runner.calls, "fetch")
    find_call(runner.calls, "checkout")
    find_call(runner.calls, "rev-parse")
    find_call(runner.calls, "build")
    find_call(runner.calls, "inspect")

    docker_ps = find_call(runner.calls, "ps", "-aq")
    assert docker_ps == [
        "docker",
        "ps",
        "-aq",
        "--filter",
        "label=heimdall.managed=true",
        "--filter",
        "label=heimdall.project_id=project-1",
    ]

    docker_run = find_call(runner.calls, "run")
    assert docker_run[docker_run.index("--name") + 1] == "heimdall-preview-preview-api"
    assert "heimdall.project_id=project-1" in docker_run
    assert "heimdall.release_id=release-1" in docker_run
    assert "heimdall.managed=true" in docker_run
    assert docker_run[docker_run.index("-p") + 1] == "127.0.0.1:18000:8080"
    assert docker_run == [
        "docker",
        "run",
        "-d",
        "--name",
        "heimdall-preview-preview-api",
        "--label",
        "heimdall.project_id=project-1",
        "--label",
        "heimdall.release_id=release-1",
        "--label",
        "heimdall.managed=true",
        "-p",
        "127.0.0.1:18000:8080",
        "heimdall/preview-api:aaaaaaa",
    ]
    assert "--env-file" not in docker_run
    assert "/var/run/docker.sock" not in docker_run
    assert health.calls == [("http://127.0.0.1:18000/health", 5.0)]


def test_child_single_service_executor_adds_only_required_mounts_and_env(tmp_path):
    host_root = tmp_path / "child-host"
    container_root = tmp_path / "child-container"
    host_root.mkdir()
    container_root.mkdir()
    settings = make_settings(
        tmp_path,
        github_token="github-child-token",
        github_webhook_secret="github-child-webhook",
        gitlab_base_url="https://gitlab.example.com",
        gitlab_token="gitlab-child-token",
        gitlab_webhook_secret="gitlab-child-webhook",
        child_runner_enabled=True,
        child_root_host=host_root,
        child_root_container=container_root,
    )
    project = make_project(run_as_heimdall_child=True)
    prepare_existing_repo(settings, project)
    runner = RecordingRunner()
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=StaticHealthClient(200),
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is True
    runtime_dir = container_root / "project-1" / "runtime"
    project_volumes_dir = container_root / "project-1" / "project-volumes"
    assert runtime_dir.is_dir()
    assert project_volumes_dir.is_dir()
    assert not runtime_dir.is_symlink()
    assert not project_volumes_dir.is_symlink()

    docker_run = find_call(runner.calls, "run")
    assert "--env-file" not in docker_run
    assert [docker_run[index + 1] for index, value in enumerate(docker_run) if value == "-v"] == [
        "/var/run/docker.sock:/var/run/docker.sock",
        f"{host_root / 'project-1' / 'runtime'}:/var/lib/heimdall",
        f"{host_root / 'project-1' / 'project-volumes'}:/host/project-volumes",
    ]
    assert env_values(docker_run) == [
        "HEIMDALL_RUNTIME_DIR=/var/lib/heimdall",
        "HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db",
        f"HEIMDALL_VOLUME_ROOT_HOST={host_root / 'project-1' / 'project-volumes'}",
        "HEIMDALL_VOLUME_ROOT_CONTAINER=/host/project-volumes",
        "HEIMDALL_GITHUB_API_TOKEN=github-child-token",
        "HEIMDALL_GITHUB_WEBHOOK_SECRET=github-child-webhook",
        "HEIMDALL_GITLAB_BASE_URL=https://gitlab.example.com",
        "HEIMDALL_GITLAB_API_TOKEN=gitlab-child-token",
        "HEIMDALL_GITLAB_WEBHOOK_SECRET=gitlab-child-webhook",
    ]
    assert docker_run[-1] == "heimdall/preview-api:aaaaaaa"


def test_child_executor_omits_unset_provider_env(tmp_path):
    host_root = tmp_path / "child-host"
    container_root = tmp_path / "child-container"
    host_root.mkdir()
    container_root.mkdir()
    settings = make_settings(
        tmp_path,
        github_token="github-child-token",
        child_runner_enabled=True,
        child_root_host=host_root,
        child_root_container=container_root,
    )
    project = make_project(run_as_heimdall_child=True)
    prepare_existing_repo(settings, project)
    runner = RecordingRunner()
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=StaticHealthClient(200),
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is True
    docker_run = find_call(runner.calls, "run")
    child_env = env_values(docker_run)
    assert "HEIMDALL_GITHUB_API_TOKEN=github-child-token" in child_env
    assert not any(value.startswith("HEIMDALL_GITHUB_WEBHOOK_SECRET=") for value in child_env)
    assert not any(value.startswith("HEIMDALL_GITLAB_BASE_URL=") for value in child_env)
    assert not any(value.startswith("HEIMDALL_GITLAB_API_TOKEN=") for value in child_env)
    assert not any(value.startswith("HEIMDALL_GITLAB_WEBHOOK_SECRET=") for value in child_env)


def test_child_multi_service_executor_adds_child_args_only_to_marked_service(tmp_path):
    host_root = tmp_path / "child-host"
    container_root = tmp_path / "child-container"
    host_root.mkdir()
    container_root.mkdir()
    settings = make_settings(
        tmp_path,
        github_token="github-child-token",
        github_webhook_secret="github-child-webhook",
        gitlab_base_url="https://gitlab.example.com",
        gitlab_token="gitlab-child-token",
        gitlab_webhook_secret="gitlab-child-webhook",
        child_runner_enabled=True,
        child_root_host=host_root,
        child_root_container=container_root,
    )
    project = make_multi_service_project(run_as_heimdall_child=True)
    for service in project["services"]:
        service["run_as_heimdall_child"] = service["name"] == "backend"
    prepare_existing_multi_service_repo(settings, project)
    runner = RecordingRunner()
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=StaticHealthClient(200),
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is True
    runtime_dir = container_root / "project-1" / "runtime"
    project_volumes_dir = container_root / "project-1" / "project-volumes"
    assert runtime_dir.is_dir()
    assert project_volumes_dir.is_dir()

    container_runs = [call for call in runner.calls if call[:3] == ["docker", "run", "-d"]]
    assert len(container_runs) == 2
    backend_run, frontend_run = container_runs
    assert backend_run[backend_run.index("--name") + 1] == "heimdall-preview-portfolio-backend"
    assert [backend_run[index + 1] for index, value in enumerate(backend_run) if value == "-v"] == [
        "/var/run/docker.sock:/var/run/docker.sock",
        f"{host_root / 'project-1' / 'runtime'}:/var/lib/heimdall",
        f"{host_root / 'project-1' / 'project-volumes'}:/host/project-volumes",
    ]
    provider_env = [
        "HEIMDALL_GITHUB_API_TOKEN=github-child-token",
        "HEIMDALL_GITHUB_WEBHOOK_SECRET=github-child-webhook",
        "HEIMDALL_GITLAB_BASE_URL=https://gitlab.example.com",
        "HEIMDALL_GITLAB_API_TOKEN=gitlab-child-token",
        "HEIMDALL_GITLAB_WEBHOOK_SECRET=gitlab-child-webhook",
    ]
    assert env_values(backend_run) == [
        "PORT=8000",
        "HEIMDALL_RUNTIME_DIR=/var/lib/heimdall",
        "HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db",
        f"HEIMDALL_VOLUME_ROOT_HOST={host_root / 'project-1' / 'project-volumes'}",
        "HEIMDALL_VOLUME_ROOT_CONTAINER=/host/project-volumes",
        *provider_env,
    ]
    assert frontend_run[frontend_run.index("--name") + 1] == "heimdall-preview-portfolio-frontend"
    assert "/var/run/docker.sock:/var/run/docker.sock" not in frontend_run
    assert "HEIMDALL_RUNTIME_DIR=/var/lib/heimdall" not in frontend_run
    for value in provider_env:
        assert value not in frontend_run

    helper = find_call(runner.calls, "curlimages/curl:8.10.1", "http://backend:8000/health")
    assert "/var/run/docker.sock:/var/run/docker.sock" not in helper
    assert "HEIMDALL_RUNTIME_DIR=/var/lib/heimdall" not in helper
    for value in provider_env:
        assert value not in helper
    for docker_run in [*container_runs, helper]:
        assert "--env-file" not in docker_run
        assert "--privileged" not in docker_run
        assert "--volumes-from" not in docker_run


def test_child_executor_rejects_symlinked_generated_child_directory(tmp_path):
    host_root = tmp_path / "child-host"
    container_root = tmp_path / "child-container"
    outside = tmp_path / "outside-child"
    host_root.mkdir()
    container_root.mkdir()
    outside.mkdir()
    try:
        (container_root / "project-1").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    settings = make_settings(
        tmp_path,
        child_runner_enabled=True,
        child_root_host=host_root,
        child_root_container=container_root,
    )
    project = make_project(run_as_heimdall_child=True)
    prepare_existing_repo(settings, project)
    runner = RecordingRunner()
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=StaticHealthClient(200),
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is False
    assert "symlink" in result.status_message or "remain under" in result.status_message
    assert not any(call[:3] == ["docker", "run", "-d"] for call in runner.calls)


def test_multi_service_executor_fetches_once_builds_networks_labels_and_checks_internal_health(tmp_path):
    settings = make_settings(tmp_path)
    project = make_multi_service_project()
    prepare_existing_multi_service_repo(settings, project)
    runner = RecordingRunner(existing_containers={"backend": "old-backend\n", "frontend": ""})
    health = StaticHealthClient(200)
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=health,
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is True
    assert result.resolved_commit_sha == COMMIT_SHA
    assert result.image_tag == "heimdall/portfolio-frontend:aaaaaaa"
    assert result.image_id == "sha256:frontend"
    assert result.preview_unavailable is True
    assert [line for line in result.log_content.splitlines() if line.startswith("[")] == [
        "[workspace]",
        "[build:backend]",
        "[build:frontend]",
        "[container:backend]",
        "[container:frontend]",
        "[health:backend]",
        "[health:frontend]",
        "[summary]",
    ]

    assert sum(1 for call in runner.calls if call[0] == "git" and "fetch" in call) == 1
    build_calls = [call for call in runner.calls if call[:2] == ["docker", "build"]]
    assert len(build_calls) == 2
    assert build_calls[0][build_calls[0].index("--file") + 1].endswith("backend/Dockerfile")
    assert build_calls[0][-1].endswith("backend")
    assert build_calls[1][build_calls[1].index("--file") + 1].endswith("frontend/Dockerfile")
    assert "VITE_API_BASE_URL=/api" in build_calls[1]

    assert find_call(runner.calls, "network", "inspect", "heimdall-preview-portfolio")
    network_create = find_call(runner.calls, "network", "create", "heimdall-preview-portfolio")
    assert "heimdall.managed=true" in network_create
    assert "heimdall.project_id=project-1" in network_create

    backend_ps = find_call(runner.calls, "ps", "-aq", "label=heimdall.service=backend")
    assert backend_ps[-2:] == ["--filter", "label=heimdall.service=backend"]
    assert find_call(runner.calls, "stop") == ["docker", "stop", "old-backend"]
    assert find_call(runner.calls, "rm") == ["docker", "rm", "old-backend"]

    container_runs = [call for call in runner.calls if call[:3] == ["docker", "run", "-d"]]
    assert len(container_runs) == 2
    backend_run, frontend_run = container_runs
    assert backend_run[backend_run.index("--name") + 1] == "heimdall-preview-portfolio-backend"
    assert backend_run[backend_run.index("--network-alias") + 1] == "backend"
    assert "heimdall.service=backend" in backend_run
    assert "PORT=8000" in backend_run
    assert "-p" not in backend_run
    assert frontend_run[frontend_run.index("--name") + 1] == "heimdall-preview-portfolio-frontend"
    assert frontend_run[frontend_run.index("--network-alias") + 1] == "frontend"
    assert "heimdall.service=frontend" in frontend_run
    assert "BACKEND_INTERNAL_URL=http://backend:8000" in frontend_run
    assert frontend_run[frontend_run.index("-p") + 1] == "127.0.0.1:18000:3000"

    helper = find_call(runner.calls, "curlimages/curl:8.10.1", "http://backend:8000/health")
    assert helper[:5] == ["docker", "run", "--rm", "--network", "heimdall-preview-portfolio"]
    assert health.calls == [("http://127.0.0.1:18000/", 5.0)]
    services = {service.name: service for service in result.service_results}
    assert services["backend"].internal_url == "http://backend:8000"
    assert services["backend"].preview_url is None
    assert services["frontend"].preview_url == "http://127.0.0.1:18000"


def test_multi_service_executor_reuses_existing_matching_project_network(tmp_path):
    settings = make_settings(tmp_path)
    project = make_multi_service_project()
    prepare_existing_multi_service_repo(settings, project)
    runner = RecordingRunner(
        network_exists=True,
        network_labels={"heimdall.managed": "true", "heimdall.project_id": "project-1"},
    )
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=StaticHealthClient(200),
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is True
    assert find_call(runner.calls, "network", "inspect", "heimdall-preview-portfolio")
    assert not any(call[:3] == ["docker", "network", "create"] for call in runner.calls)
    assert "already exists and is Heimdall-managed" in result.log_content


@pytest.mark.parametrize(
    "network_labels",
    [
        {},
        {"heimdall.managed": "false", "heimdall.project_id": "project-1"},
        {"heimdall.managed": "true", "heimdall.project_id": "other-project"},
    ],
)
def test_multi_service_executor_rejects_existing_foreign_or_unmanaged_network(tmp_path, network_labels):
    settings = make_settings(tmp_path)
    project = make_multi_service_project()
    prepare_existing_multi_service_repo(settings, project)
    runner = RecordingRunner(network_exists=True, network_labels=network_labels)
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=StaticHealthClient(200),
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is False
    assert "not Heimdall-owned" in result.status_message
    assert find_call(runner.calls, "network", "inspect", "heimdall-preview-portfolio")
    assert not any(call[:3] == ["docker", "network", "create"] for call in runner.calls)
    assert not any(call[:3] == ["docker", "run", "-d"] for call in runner.calls)


@pytest.mark.parametrize(
    ("provider", "repo_url", "token_attr", "username", "base_url"),
    [
        ("github", "https://github.com/example/private.git", "github_token", "x-access-token", "https://github.com/"),
        ("gitlab", "https://gitlab.com/example/private.git", "gitlab_token", "oauth2", "https://gitlab.com/"),
    ],
)
def test_git_token_uses_extra_header_without_leaking_to_logs_or_repo_url(
    tmp_path,
    provider,
    repo_url,
    token_attr,
    username,
    base_url,
):
    token = f"{provider}-secret-token"
    encoded = base64.b64encode(f"{username}:{token}".encode("utf-8")).decode("ascii")
    settings = make_settings(tmp_path, **{token_attr: token})
    project = make_project(provider=provider, repo_url=repo_url)
    runner = RecordingRunner()
    runner.leaky_output = f"raw {token}\nheader Authorization: Basic {encoded}\nencoded {encoded}\n"
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=StaticHealthClient(200),
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is True
    clone = find_call(runner.calls, "clone")
    config_arg = clone[clone.index("-c") + 1]
    assert config_arg == f"http.{base_url}.extraHeader=Authorization: Basic {encoded}"
    assert repo_url in clone
    assert f"{username}:{token}" not in repo_url
    assert token not in result.log_content
    assert encoded not in result.log_content
    assert f"Authorization: Basic {encoded}" not in result.log_content
    assert "[redacted]" in result.log_content


def test_existing_container_replacement_only_stops_label_scoped_container_ids(tmp_path):
    settings = make_settings(tmp_path)
    project = make_project()
    prepare_existing_repo(settings, project)
    runner = RecordingRunner(existing_containers="old-container-1\nold-container-2\n")
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=StaticHealthClient(200),
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is True
    assert result.preview_unavailable is True
    docker_ps = find_call(runner.calls, "ps", "-aq")
    assert docker_ps == [
        "docker",
        "ps",
        "-aq",
        "--filter",
        "label=heimdall.managed=true",
        "--filter",
        "label=heimdall.project_id=project-1",
    ]
    assert find_call(runner.calls, "stop") == ["docker", "stop", "old-container-1", "old-container-2"]
    assert find_call(runner.calls, "rm") == ["docker", "rm", "old-container-1", "old-container-2"]


@pytest.mark.parametrize(
    ("field", "value", "setup_escape"),
    [
        ("dockerfile_path", "../outside/Dockerfile", "relative_file"),
        ("build_context_path", "../outside-context", "relative_dir"),
        ("dockerfile_path", "Dockerfile", "symlink_file"),
        ("build_context_path", "context", "symlink_dir"),
    ],
)
def test_executor_rejects_repo_path_escapes_without_leaking_secrets(tmp_path, field, value, setup_escape):
    token = "path-escape-secret"
    settings = make_settings(tmp_path, github_token=token)
    project = make_project(**{field: value})
    repo_dir = prepare_existing_repo(settings, project)
    project_workspace = repo_dir.parent

    if setup_escape == "relative_file":
        outside = project_workspace / "outside"
        outside.mkdir()
        (outside / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    elif setup_escape == "relative_dir":
        (project_workspace / "outside-context").mkdir()
    elif setup_escape == "symlink_file":
        target = project_workspace / "outside.Dockerfile"
        target.write_text("FROM scratch\n", encoding="utf-8")
        (repo_dir / "Dockerfile").unlink()
        (repo_dir / "Dockerfile").symlink_to(target)
    elif setup_escape == "symlink_dir":
        target = project_workspace / "outside-context"
        target.mkdir()
        (repo_dir / "context").symlink_to(target, target_is_directory=True)

    runner = RecordingRunner()
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=StaticHealthClient(200),
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is False
    assert "escapes repository root" in result.status_message
    assert token not in result.status_message
    assert token not in result.log_content
    assert not any(call[0] == "docker" for call in runner.calls)


def test_executor_rejects_absolute_path_escape_without_raw_filesystem_exception(tmp_path):
    settings = make_settings(tmp_path)
    project = make_project(dockerfile_path=str(tmp_path / "outside" / "missing.Dockerfile"))
    prepare_existing_repo(settings, project)
    runner = RecordingRunner()
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=StaticHealthClient(200),
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is False
    assert result.status_message == "Build failed: dockerfile_path escapes repository root."
    assert not any(call[0] == "docker" for call in runner.calls)


def test_health_failure_returns_failed_result_without_success_summary(tmp_path):
    settings = make_settings(tmp_path)
    project = make_project()
    prepare_existing_repo(settings, project)
    runner = RecordingRunner()
    executor = RealLocalDockerExecutor(
        settings=settings,
        runner=runner,
        health_client=StaticHealthClient(500),
        sleep=lambda _: None,
        health_timeout_seconds=0,
        health_interval_seconds=0,
    )

    result = executor.deploy_preview(make_request(project))

    assert result.success is False
    assert result.status_message.startswith("Health failed:")
    assert "completed successfully" not in result.status_message
    assert "completed successfully" not in result.log_content
    assert find_call(runner.calls, "run")
