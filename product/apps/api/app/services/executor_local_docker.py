from __future__ import annotations

import base64
import json
import re
import shlex
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse, urlunparse

import httpx

from ..config import Settings, get_settings
from ..models import DeployMode, Provider


COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")


@dataclass(frozen=True)
class ExecutorDeploymentRequest:
    project: dict[str, object]
    deployment_id: str
    timestamp: str
    release_id: str | None = None
    requested_ref: str | None = None
    requested_commit_sha: str | None = None
    resolved_commit_sha: str | None = None
    image_tag: str | None = None


@dataclass(frozen=True)
class ExecutorDeploymentResult:
    log_content: str
    is_dry_run: bool
    status_message: str
    success: bool = True
    resolved_commit_sha: str | None = None
    image_tag: str | None = None
    image_id: str | None = None
    service_results: tuple["ExecutorServiceResult", ...] = field(default_factory=tuple)
    preview_unavailable: bool = False


@dataclass(frozen=True)
class ExecutorServiceResult:
    name: str
    image_tag: str
    image_id: str | None
    container_name: str
    container_id: str | None
    container_port: int
    public: bool
    preview_url: str | None
    internal_url: str | None
    status: str = "available"


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    def run(self, argv: Sequence[str], *, cwd: Path | None = None) -> CommandResult:
        """Run a command without invoking a shell."""


class HealthClient(Protocol):
    def get_status_code(self, url: str, *, timeout: float) -> int:
        """Return the HTTP status code for a health check request."""


class LocalDockerExecutor(Protocol):
    def deploy_preview(self, request: ExecutorDeploymentRequest) -> ExecutorDeploymentResult:
        """Build and run a project preview with the local Docker executor."""


class SubprocessCommandRunner:
    def run(self, argv: Sequence[str], *, cwd: Path | None = None) -> CommandResult:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        return CommandResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class HttpxHealthClient:
    def get_status_code(self, url: str, *, timeout: float) -> int:
        response = httpx.get(url, timeout=timeout, follow_redirects=False)
        return response.status_code


class ExecutorStepError(Exception):
    pass


class SectionedLog:
    def __init__(self, redactions: Sequence[str] = ()):
        self._redactions = tuple(redactions)
        self._lines: list[str] = []

    def section(self, name: str) -> None:
        if self._lines:
            self._lines.append("")
        self._lines.append(f"[{name}]")

    def add(self, message: str) -> None:
        self._lines.append(redact_text(message, self._redactions))

    def content(self) -> str:
        return "\n".join(self._lines)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value and value not in seen:
            unique_values.append(value)
            seen.add(value)
    return unique_values


def _basic_auth_header(username: str, token: str) -> tuple[str, str]:
    encoded = base64.b64encode(f"{username}:{token}".encode("utf-8")).decode("ascii")
    return f"Authorization: Basic {encoded}", encoded


def _provider_username(provider: str) -> str:
    return "x-access-token" if provider == Provider.GITHUB.value else "oauth2"


def redaction_values_for_settings(settings: Settings) -> list[str]:
    values: list[str] = []
    if settings.github_api_token:
        header, encoded = _basic_auth_header(_provider_username(Provider.GITHUB.value), settings.github_api_token)
        values.extend([settings.github_api_token, header, encoded])
    if settings.github_webhook_secret:
        values.append(settings.github_webhook_secret)
    if settings.gitlab_api_token:
        header, encoded = _basic_auth_header(_provider_username(Provider.GITLAB.value), settings.gitlab_api_token)
        values.extend([settings.gitlab_api_token, header, encoded])
    if settings.gitlab_webhook_secret:
        values.append(settings.gitlab_webhook_secret)
    return _unique(values)


def _child_provider_env(settings: Settings) -> list[str]:
    env: list[str] = []
    if settings.github_api_token:
        env.append(f"HEIMDALL_GITHUB_API_TOKEN={settings.github_api_token}")
    if settings.github_webhook_secret:
        env.append(f"HEIMDALL_GITHUB_WEBHOOK_SECRET={settings.github_webhook_secret}")
    if settings.gitlab_base_url:
        env.append(f"HEIMDALL_GITLAB_BASE_URL={settings.gitlab_base_url}")
    if settings.gitlab_api_token:
        env.append(f"HEIMDALL_GITLAB_API_TOKEN={settings.gitlab_api_token}")
    if settings.gitlab_webhook_secret:
        env.append(f"HEIMDALL_GITLAB_WEBHOOK_SECRET={settings.gitlab_webhook_secret}")
    return env


def redact_text(value: str, redactions: Sequence[str]) -> str:
    redacted = value
    for secret in sorted(_unique(list(redactions)), key=len, reverse=True):
        redacted = redacted.replace(secret, "[redacted]")
    return redacted


def _format_argv(argv: Sequence[str], redactions: Sequence[str]) -> str:
    return " ".join(shlex.quote(redact_text(str(part), redactions)) for part in argv)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _http_config_base(repo_url: str) -> str | None:
    parsed = urlparse(repo_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    return urlunparse((parsed.scheme, netloc, "/", "", "", ""))


def _branch_from_ref(ref: str) -> str:
    if ref.startswith("refs/heads/"):
        return ref.removeprefix("refs/heads/")
    if ref.startswith("origin/"):
        return ref.removeprefix("origin/")
    return ref


def _validate_branch_ref(ref: str) -> str:
    branch = _branch_from_ref(ref.strip())
    parts = branch.split("/")
    if (
        not branch
        or branch.startswith("-")
        or branch.startswith("/")
        or branch.endswith("/")
        or branch.endswith(".lock")
        or "\\" in branch
        or ".." in branch
        or "@{" in branch
        or any(part in {"", ".", ".."} for part in parts)
        or any(ord(character) < 32 for character in branch)
    ):
        raise ExecutorStepError("Workspace failed: requested Git ref is not a safe branch ref.")
    return branch


def _is_multi_service_project(project: dict[str, object]) -> bool:
    return str(project.get("deploy_mode") or "") == DeployMode.MULTI_SERVICE_DOCKERFILE.value


def _is_child_service(service: dict[str, object]) -> bool:
    return _as_bool(service.get("run_as_heimdall_child"))


def _child_services(project: dict[str, object]) -> list[dict[str, object]]:
    return [service for service in _project_services(project) if _is_child_service(service)]


def _is_child_project(project: dict[str, object]) -> bool:
    return _as_bool(project.get("run_as_heimdall_child")) or bool(_child_services(project))


def _multi_service_child_state_error(project: dict[str, object]) -> str | None:
    if not _is_multi_service_project(project):
        return None
    child_count = len(_child_services(project))
    if _as_bool(project.get("run_as_heimdall_child")) or child_count > 0:
        if child_count != 1:
            return "Deployment failed: multi-service child mode requires exactly one service marked run_as_heimdall_child."
    return None


def _service_sort_key(service: dict[str, object]) -> tuple[int, str]:
    return (int(service.get("startup_order") or 0), str(service["name"]))


def _project_services(project: dict[str, object]) -> list[dict[str, object]]:
    services = project.get("services") or []
    if isinstance(services, list):
        return sorted([service for service in services if isinstance(service, dict)], key=_service_sort_key)
    return []


def _public_service(services: Sequence[dict[str, object]]) -> dict[str, object]:
    for service in services:
        if bool(service.get("public")):
            return service
    raise ExecutorStepError("Deployment failed: multi-service project does not define a public service.")


class RealLocalDockerExecutor:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        runner: CommandRunner | None = None,
        health_client: HealthClient | None = None,
        sleep: Callable[[float], None] = time.sleep,
        health_timeout_seconds: float = 60.0,
        health_interval_seconds: float = 2.0,
    ) -> None:
        self.settings = settings or get_settings()
        self.runner = runner or SubprocessCommandRunner()
        self.health_client = health_client or HttpxHealthClient()
        self.sleep = sleep
        self.health_timeout_seconds = health_timeout_seconds
        self.health_interval_seconds = health_interval_seconds

    def _failed_before_docker(self, deployment_id: str, message: str) -> ExecutorDeploymentResult:
        log = SectionedLog(redaction_values_for_settings(self.settings))
        log.section("summary")
        log.add(f"{_now()} deployment {deployment_id} failed")
        log.add(f"{_now()} {message}")
        return ExecutorDeploymentResult(
            log_content=log.content(),
            is_dry_run=False,
            status_message=message,
            success=False,
        )

    def deploy_preview(self, request: ExecutorDeploymentRequest) -> ExecutorDeploymentResult:
        child_state_error = _multi_service_child_state_error(request.project)
        if child_state_error:
            return self._failed_before_docker(request.deployment_id, child_state_error)
        if _is_child_project(request.project):
            try:
                self.settings.require_child_runner()
            except ValueError as exc:
                return self._failed_before_docker(request.deployment_id, f"Deployment failed: {exc}")
        if _is_multi_service_project(request.project):
            return self._deploy_multi_service_preview(request)

        redactions = redaction_values_for_settings(self.settings)
        log = SectionedLog(redactions)
        resolved_commit_sha: str | None = None
        image_tag: str | None = None
        image_id: str | None = None
        preview_unavailable = False

        try:
            if not request.release_id:
                raise ExecutorStepError("Deployment failed: release id is required for a real preview deploy.")

            log.section("workspace")
            repo_dir = self._prepare_workspace(request, log, redactions)
            resolved_commit_sha = self._checkout_and_resolve(repo_dir, request, log, redactions)
            short_commit = resolved_commit_sha[:7]
            image_tag = f"heimdall/{request.project['slug']}:{short_commit}"

            log.section("build")
            image_id = self._build_image(repo_dir, request.project, image_tag, log, redactions)

            log.section("container")
            preview_unavailable = self._replace_container(request, image_tag, log, redactions)

            log.section("health")
            self._check_health(request.project, log)

            log.section("summary")
            log.add(f"{_now()} deployment {request.deployment_id} completed successfully")
            log.add(f"{_now()} release {request.release_id} is current for commit {resolved_commit_sha}")
            return ExecutorDeploymentResult(
                log_content=log.content(),
                is_dry_run=False,
                status_message="Preview deployment completed successfully.",
                success=True,
                resolved_commit_sha=resolved_commit_sha,
                image_tag=image_tag,
                image_id=image_id,
                preview_unavailable=preview_unavailable,
            )
        except ExecutorStepError as exc:
            log.section("summary")
            log.add(f"{_now()} deployment {request.deployment_id} failed")
            log.add(f"{_now()} {exc}")
            return ExecutorDeploymentResult(
                log_content=log.content(),
                is_dry_run=False,
                status_message=str(exc),
                success=False,
                resolved_commit_sha=resolved_commit_sha,
                image_tag=image_tag,
                image_id=image_id,
                preview_unavailable=preview_unavailable,
            )

    def _deploy_multi_service_preview(self, request: ExecutorDeploymentRequest) -> ExecutorDeploymentResult:
        redactions = redaction_values_for_settings(self.settings)
        log = SectionedLog(redactions)
        resolved_commit_sha: str | None = None
        compatibility_image_tag: str | None = None
        compatibility_image_id: str | None = None
        preview_unavailable = False
        service_results: list[ExecutorServiceResult] = []

        try:
            if not request.release_id:
                raise ExecutorStepError("Deployment failed: release id is required for a real preview deploy.")
            services = _project_services(request.project)
            if not services:
                raise ExecutorStepError("Deployment failed: multi-service project has no services.")
            public_service = _public_service(services)

            log.section("workspace")
            repo_dir = self._prepare_workspace(request, log, redactions)
            resolved_commit_sha = self._checkout_and_resolve(repo_dir, request, log, redactions)
            short_commit = resolved_commit_sha[:7]

            built_services: dict[str, tuple[dict[str, object], str, str | None]] = {}
            for service in services:
                service_name = str(service["name"])
                image_tag = f"heimdall/{request.project['slug']}-{service_name}:{short_commit}"
                log.section(f"build:{service_name}")
                image_id = self._build_service_image(repo_dir, service, image_tag, log, redactions)
                built_services[service_name] = (service, image_tag, image_id)
                if service_name == str(public_service["name"]):
                    compatibility_image_tag = image_tag
                    compatibility_image_id = image_id

            network_name = self._project_network_name(request.project)
            network_ready = False
            started_services: list[tuple[dict[str, object], str, str | None, str, str | None]] = []
            for service in services:
                service_name = str(service["name"])
                service, image_tag, image_id = built_services[service_name]
                log.section(f"container:{service_name}")
                if not network_ready:
                    self._ensure_project_network(request.project, network_name, log, redactions)
                    network_ready = True
                service_preview_unavailable, container_name, container_id = self._replace_service_container(
                    request,
                    service,
                    image_tag,
                    network_name,
                    log,
                    redactions,
                )
                preview_unavailable = preview_unavailable or service_preview_unavailable
                started_services.append((service, image_tag, image_id, container_name, container_id))

            for service, image_tag, image_id, container_name, container_id in started_services:
                service_name = str(service["name"])
                log.section(f"health:{service_name}")
                self._check_service_health(request.project, service, network_name, log, redactions)
                service_results.append(
                    ExecutorServiceResult(
                        name=service_name,
                        image_tag=image_tag,
                        image_id=image_id,
                        container_name=container_name,
                        container_id=container_id,
                        container_port=int(service["container_port"]),
                        public=bool(service["public"]),
                        preview_url=str(request.project["preview_url"]) if bool(service["public"]) else None,
                        internal_url=None if bool(service["public"]) else self._service_internal_url(service),
                    )
                )

            log.section("summary")
            log.add(f"{_now()} deployment {request.deployment_id} completed successfully")
            log.add(f"{_now()} release {request.release_id} is current for commit {resolved_commit_sha}")
            return ExecutorDeploymentResult(
                log_content=log.content(),
                is_dry_run=False,
                status_message="Multi-service preview deployment completed successfully.",
                success=True,
                resolved_commit_sha=resolved_commit_sha,
                image_tag=compatibility_image_tag,
                image_id=compatibility_image_id,
                service_results=tuple(service_results),
                preview_unavailable=preview_unavailable,
            )
        except ExecutorStepError as exc:
            log.section("summary")
            log.add(f"{_now()} deployment {request.deployment_id} failed")
            log.add(f"{_now()} {exc}")
            return ExecutorDeploymentResult(
                log_content=log.content(),
                is_dry_run=False,
                status_message=str(exc),
                success=False,
                resolved_commit_sha=resolved_commit_sha,
                image_tag=compatibility_image_tag,
                image_id=compatibility_image_id,
                service_results=tuple(service_results),
                preview_unavailable=preview_unavailable,
            )

    def _prepare_workspace(
        self,
        request: ExecutorDeploymentRequest,
        log: SectionedLog,
        redactions: Sequence[str],
    ) -> Path:
        project_id = str(request.project["id"])
        workspaces_root = self.settings.workspaces_dir.resolve()
        project_workspace = (workspaces_root / project_id).resolve()
        if not _is_relative_to(project_workspace, workspaces_root):
            raise ExecutorStepError("Workspace failed: project workspace escapes the runtime workspaces directory.")

        repo_dir = project_workspace / "repo"
        project_workspace.mkdir(parents=True, exist_ok=True)
        if repo_dir.exists() and not _is_relative_to(repo_dir.resolve(), project_workspace):
            raise ExecutorStepError("Workspace failed: repository workspace escapes the project workspace.")

        git_config_args, git_redactions = self._git_config_args(request.project)
        command_redactions = _unique([*redactions, *git_redactions])
        repo_url = str(request.project["repo_url"])

        if (repo_dir / ".git").exists():
            log.add(f"{_now()} fetching repository in {repo_dir}")
            self._run_checked(
                [
                    "git",
                    *git_config_args,
                    "-C",
                    str(repo_dir),
                    "fetch",
                    "origin",
                    "--prune",
                    "--tags",
                    "+refs/heads/*:refs/remotes/origin/*",
                ],
                log=log,
                redactions=command_redactions,
                phase="Workspace",
                command_label="git fetch",
            )
            return repo_dir

        if repo_dir.exists():
            raise ExecutorStepError("Workspace failed: repository workspace exists but is not a Git repository.")

        log.add(f"{_now()} cloning repository into {repo_dir}")
        self._run_checked(
            [
                "git",
                *git_config_args,
                "clone",
                "--origin",
                "origin",
                "--no-checkout",
                repo_url,
                str(repo_dir),
            ],
            log=log,
            redactions=command_redactions,
            phase="Workspace",
            command_label="git clone",
        )
        self._run_checked(
            [
                "git",
                *git_config_args,
                "-C",
                str(repo_dir),
                "fetch",
                "origin",
                "--prune",
                "--tags",
                "+refs/heads/*:refs/remotes/origin/*",
            ],
            log=log,
            redactions=command_redactions,
            phase="Workspace",
            command_label="git fetch",
        )
        return repo_dir

    def _git_config_args(self, project: dict[str, object]) -> tuple[list[str], list[str]]:
        provider = str(project["provider"])
        token = self.settings.github_api_token if provider == Provider.GITHUB.value else self.settings.gitlab_api_token
        if not token:
            return [], []

        config_base = _http_config_base(str(project["repo_url"]))
        if not config_base:
            return [], [token]

        auth_header, encoded = _basic_auth_header(_provider_username(provider), token)
        config_key = f"http.{config_base}.extraHeader"
        return ["-c", f"{config_key}={auth_header}"], [token, auth_header, encoded]

    def _checkout_and_resolve(
        self,
        repo_dir: Path,
        request: ExecutorDeploymentRequest,
        log: SectionedLog,
        redactions: Sequence[str],
    ) -> str:
        if request.requested_commit_sha:
            if not COMMIT_SHA_RE.fullmatch(request.requested_commit_sha):
                raise ExecutorStepError("Workspace failed: requested commit SHA is invalid.")
            checkout_target = request.requested_commit_sha
        else:
            branch = _validate_branch_ref(request.requested_ref or str(request.project["tracked_branch"]))
            checkout_target = f"refs/remotes/origin/{branch}"

        log.add(f"{_now()} checking out {checkout_target}")
        self._run_checked(
            ["git", "-C", str(repo_dir), "checkout", "--force", "--detach", checkout_target],
            log=log,
            redactions=redactions,
            phase="Workspace",
            command_label="git checkout",
        )
        result = self._run_checked(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            log=log,
            redactions=redactions,
            phase="Workspace",
            command_label="git rev-parse",
        )
        commit_sha = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        if not re.fullmatch(r"^[0-9a-fA-F]{40}$", commit_sha):
            raise ExecutorStepError("Workspace failed: Git did not resolve a full commit SHA.")
        log.add(f"{_now()} resolved commit {commit_sha}")
        return commit_sha.lower()

    def _build_image(
        self,
        repo_dir: Path,
        project: dict[str, object],
        image_tag: str,
        log: SectionedLog,
        redactions: Sequence[str],
    ) -> str | None:
        repo_root = repo_dir.resolve(strict=True)
        dockerfile_path = self._resolve_repo_path(repo_root, str(project["dockerfile_path"]), "dockerfile_path")
        context_path = self._resolve_repo_path(repo_root, str(project["build_context_path"]), "build_context_path")
        if not dockerfile_path.is_file():
            raise ExecutorStepError("Build failed: dockerfile_path does not resolve to a file.")
        if not context_path.is_dir():
            raise ExecutorStepError("Build failed: build_context_path does not resolve to a directory.")

        log.add(f"{_now()} building image {image_tag}")
        self._run_checked(
            ["docker", "build", "--file", str(dockerfile_path), "--tag", image_tag, str(context_path)],
            log=log,
            redactions=redactions,
            phase="Build",
            command_label="docker build",
        )
        inspect = self._run_checked(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image_tag],
            log=log,
            redactions=redactions,
            phase="Build",
            command_label="docker image inspect",
        )
        return inspect.stdout.strip().splitlines()[-1] if inspect.stdout.strip() else None

    def _build_service_image(
        self,
        repo_dir: Path,
        service: dict[str, object],
        image_tag: str,
        log: SectionedLog,
        redactions: Sequence[str],
    ) -> str | None:
        repo_root = repo_dir.resolve(strict=True)
        service_name = str(service["name"])
        dockerfile_path = self._resolve_repo_path(repo_root, str(service["dockerfile_path"]), "dockerfile_path")
        context_path = self._resolve_repo_path(repo_root, str(service["build_context_path"]), "build_context_path")
        if not dockerfile_path.is_file():
            raise ExecutorStepError(f"Build failed for {service_name}: dockerfile_path does not resolve to a file.")
        if not context_path.is_dir():
            raise ExecutorStepError(f"Build failed for {service_name}: build_context_path does not resolve to a directory.")

        build_args: list[str] = []
        build_env = service.get("build_env") or {}
        if isinstance(build_env, dict):
            for key in sorted(build_env):
                build_args.extend(["--build-arg", f"{key}={build_env[key]}"])

        log.add(f"{_now()} building image {image_tag}")
        self._run_checked(
            ["docker", "build", "--file", str(dockerfile_path), "--tag", image_tag, *build_args, str(context_path)],
            log=log,
            redactions=redactions,
            phase="Build",
            command_label=f"docker build {service_name}",
        )
        inspect = self._run_checked(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image_tag],
            log=log,
            redactions=redactions,
            phase="Build",
            command_label=f"docker image inspect {service_name}",
        )
        return inspect.stdout.strip().splitlines()[-1] if inspect.stdout.strip() else None

    def _resolve_repo_path(self, repo_root: Path, relative_path: str, field_name: str) -> Path:
        try:
            candidate = (repo_root / relative_path).resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise ExecutorStepError(f"Build failed: {field_name} does not resolve inside repository root.") from exc
        if not _is_relative_to(candidate, repo_root):
            raise ExecutorStepError(f"Build failed: {field_name} escapes repository root.")
        return candidate

    def _project_network_name(self, project: dict[str, object]) -> str:
        return f"heimdall-preview-{project['slug']}"

    def _ensure_project_network(
        self,
        project: dict[str, object],
        network_name: str,
        log: SectionedLog,
        redactions: Sequence[str],
    ) -> None:
        inspect_argv = ["docker", "network", "inspect", network_name]
        log.add(f"{_now()} command: {_format_argv(inspect_argv, redactions)}")
        try:
            inspect = self.runner.run(inspect_argv)
        except OSError as exc:
            raise ExecutorStepError("Container failed: unable to execute docker.") from exc
        log.add(f"{_now()} exit_code: {inspect.exit_code}")
        if inspect.exit_code == 0:
            labels = self._network_labels_from_inspect(inspect.stdout, network_name)
            expected_project_id = str(project["id"])
            if labels.get("heimdall.managed") != "true" or labels.get("heimdall.project_id") != expected_project_id:
                raise ExecutorStepError(
                    f"Container failed: Docker network {network_name} already exists but is not Heimdall-owned "
                    f"for project {expected_project_id}."
                )
            log.add(f"{_now()} Docker network {network_name} already exists and is Heimdall-managed for this project")
            return
        self._run_checked(
            [
                "docker",
                "network",
                "create",
                "--label",
                "heimdall.managed=true",
                "--label",
                f"heimdall.project_id={project['id']}",
                network_name,
            ],
            log=log,
            redactions=redactions,
            phase="Container",
            command_label="docker network create",
        )

    def _network_labels_from_inspect(self, inspect_output: str, network_name: str) -> dict[str, str]:
        try:
            parsed = json.loads(inspect_output)
        except json.JSONDecodeError as exc:
            raise ExecutorStepError(
                f"Container failed: Docker network {network_name} exists but its labels could not be inspected."
            ) from exc
        network = parsed[0] if isinstance(parsed, list) and parsed else parsed
        labels = network.get("Labels") if isinstance(network, dict) else None
        if not isinstance(labels, dict):
            raise ExecutorStepError(
                f"Container failed: Docker network {network_name} exists but does not expose Docker labels."
            )
        return {str(key): str(value) for key, value in labels.items() if value is not None}

    def _replace_service_container(
        self,
        request: ExecutorDeploymentRequest,
        service: dict[str, object],
        image_tag: str,
        network_name: str,
        log: SectionedLog,
        redactions: Sequence[str],
    ) -> tuple[bool, str, str | None]:
        project = request.project
        project_id = str(project["id"])
        service_name = str(service["name"])
        existing_containers = self._managed_container_ids(project_id, log, redactions, service_name=service_name)
        preview_unavailable = False
        if existing_containers:
            preview_unavailable = True
            log.add(f"{_now()} stopping {len(existing_containers)} managed preview container(s) for {service_name}")
            self._run_checked(
                ["docker", "stop", *existing_containers],
                log=log,
                redactions=redactions,
                phase="Container",
                command_label=f"docker stop {service_name}",
            )
            self._run_checked(
                ["docker", "rm", *existing_containers],
                log=log,
                redactions=redactions,
                phase="Container",
                command_label=f"docker rm {service_name}",
            )
        else:
            log.add(f"{_now()} no existing Heimdall-managed preview container found for {service_name}")

        container_name = f"heimdall-preview-{project['slug']}-{service_name}"
        docker_run = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--network",
            network_name,
            "--network-alias",
            service_name,
            "--label",
            "heimdall.managed=true",
            "--label",
            f"heimdall.project_id={project_id}",
            "--label",
            f"heimdall.release_id={request.release_id}",
            "--label",
            f"heimdall.service={service_name}",
        ]
        runtime_env = service.get("runtime_env") or {}
        if isinstance(runtime_env, dict):
            for key in sorted(runtime_env):
                docker_run.extend(["--env", f"{key}={runtime_env[key]}"])
        if bool(service["public"]):
            docker_run.extend(["-p", f"{project['preview_host']}:{project['preview_port']}:{service['container_port']}"])
        if _is_child_service(service):
            docker_run.extend(self._child_run_args(project_id))
        docker_run.append(image_tag)

        log.add(f"{_now()} starting container {container_name}")
        result = self._run_checked(
            docker_run,
            log=log,
            redactions=redactions,
            phase="Container",
            command_label=f"docker run {service_name}",
        )
        container_id = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else None
        return preview_unavailable, container_name, container_id

    def _replace_container(
        self,
        request: ExecutorDeploymentRequest,
        image_tag: str,
        log: SectionedLog,
        redactions: Sequence[str],
    ) -> bool:
        project = request.project
        project_id = str(project["id"])
        existing_containers = self._managed_container_ids(project_id, log, redactions)
        preview_unavailable = False
        if existing_containers:
            preview_unavailable = True
            log.add(f"{_now()} stopping {len(existing_containers)} managed preview container(s)")
            self._run_checked(
                ["docker", "stop", *existing_containers],
                log=log,
                redactions=redactions,
                phase="Container",
                command_label="docker stop",
            )
            self._run_checked(
                ["docker", "rm", *existing_containers],
                log=log,
                redactions=redactions,
                phase="Container",
                command_label="docker rm",
            )
        else:
            log.add(f"{_now()} no existing Heimdall-managed preview containers found for project")

        container_name = f"heimdall-preview-{project['slug']}"
        port_mapping = f"{project['preview_host']}:{project['preview_port']}:{project['container_port']}"
        docker_run = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--label",
            f"heimdall.project_id={project_id}",
            "--label",
            f"heimdall.release_id={request.release_id}",
            "--label",
            "heimdall.managed=true",
            "-p",
            port_mapping,
        ]
        if _is_child_project(project):
            docker_run.extend(self._child_run_args(project_id))
        docker_run.append(image_tag)

        log.add(f"{_now()} starting container {container_name}")
        self._run_checked(
            docker_run,
            log=log,
            redactions=redactions,
            phase="Container",
            command_label="docker run",
        )
        return preview_unavailable

    def _child_run_args(self, project_id: str) -> list[str]:
        try:
            _, container_root = self.settings.require_child_runner()
            paths = self.settings.child_runner_paths(project_id)
        except ValueError as exc:
            raise ExecutorStepError(f"Container failed: {exc}") from exc

        self._ensure_child_directory(paths.container_runtime, container_root, "child runtime")
        self._ensure_child_directory(paths.container_project_volumes, container_root, "child project volumes")

        docker_args = [
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
            "-v",
            f"{paths.host_runtime}:/var/lib/heimdall",
            "-v",
            f"{paths.host_project_volumes}:/host/project-volumes",
            "--env",
            "HEIMDALL_RUNTIME_DIR=/var/lib/heimdall",
            "--env",
            "HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db",
            "--env",
            f"HEIMDALL_VOLUME_ROOT_HOST={paths.host_project_volumes}",
            "--env",
            "HEIMDALL_VOLUME_ROOT_CONTAINER=/host/project-volumes",
        ]
        for value in _child_provider_env(self.settings):
            docker_args.extend(["--env", value])
        return docker_args

    def _ensure_child_directory(self, path: Path, root: Path, label: str) -> None:
        try:
            root_resolved = root.resolve(strict=True)
            candidate = path.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise ExecutorStepError(f"Container failed: {label} path could not be resolved.") from exc
        if not _is_relative_to(candidate, root_resolved):
            raise ExecutorStepError(f"Container failed: {label} path escapes the configured child root.")

        self._reject_symlink_components(path, root, root_resolved, label)
        path.mkdir(parents=True, exist_ok=True)
        self._reject_symlink_components(path, root, root_resolved, label)

        try:
            created = path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ExecutorStepError(f"Container failed: {label} path could not be checked after creation.") from exc
        if not _is_relative_to(created, root_resolved):
            raise ExecutorStepError(f"Container failed: {label} path escapes the configured child root.")
        if path.is_symlink() or not path.is_dir():
            raise ExecutorStepError(f"Container failed: {label} path must be a directory and not a symlink.")

    def _reject_symlink_components(self, path: Path, root: Path, root_resolved: Path, label: str) -> None:
        current = root
        try:
            relative_parts = path.relative_to(root).parts
        except ValueError:
            try:
                relative_parts = path.resolve(strict=False).relative_to(root_resolved).parts
            except ValueError as exc:
                raise ExecutorStepError(f"Container failed: {label} path escapes the configured child root.") from exc
            current = root_resolved
        for part in relative_parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise ExecutorStepError(f"Container failed: {label} path must not contain symlinks.")

    def _managed_container_ids(
        self,
        project_id: str,
        log: SectionedLog,
        redactions: Sequence[str],
        *,
        service_name: str | None = None,
    ) -> list[str]:
        argv = [
            "docker",
            "ps",
            "-aq",
            "--filter",
            "label=heimdall.managed=true",
            "--filter",
            f"label=heimdall.project_id={project_id}",
        ]
        if service_name is not None:
            argv.extend(["--filter", f"label=heimdall.service={service_name}"])
        result = self._run_checked(
            argv,
            log=log,
            redactions=redactions,
            phase="Container",
            command_label="docker ps",
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _check_health(self, project: dict[str, object], log: SectionedLog) -> None:
        url = self._health_url(project)
        deadline = time.monotonic() + self.health_timeout_seconds
        attempt = 0
        while True:
            attempt += 1
            try:
                status_code = self.health_client.get_status_code(url, timeout=5.0)
            except httpx.HTTPError as exc:
                log.add(f"{_now()} health attempt {attempt}: HTTP error {exc.__class__.__name__}")
            except Exception as exc:  # pragma: no cover - defensive boundary for injected clients.
                log.add(f"{_now()} health attempt {attempt}: error {exc.__class__.__name__}")
            else:
                log.add(f"{_now()} health attempt {attempt}: HTTP {status_code}")
                if 200 <= status_code < 400:
                    log.add(f"{_now()} health check succeeded")
                    return

            if time.monotonic() >= deadline:
                break
            self.sleep(min(self.health_interval_seconds, max(0.0, deadline - time.monotonic())))

        raise ExecutorStepError(
            f"Health failed: {url} did not return HTTP 2xx/3xx within {int(self.health_timeout_seconds)} seconds."
        )

    def _check_service_health(
        self,
        project: dict[str, object],
        service: dict[str, object],
        network_name: str,
        log: SectionedLog,
        redactions: Sequence[str],
    ) -> None:
        if bool(service["public"]):
            self._check_public_service_health(project, service, log)
            return
        self._check_internal_service_health(service, network_name, log, redactions)

    def _check_public_service_health(
        self,
        project: dict[str, object],
        service: dict[str, object],
        log: SectionedLog,
    ) -> None:
        path = str(service.get("health_check_path") or "/")
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"http://{project['preview_host']}:{project['preview_port']}{path}"
        deadline = time.monotonic() + self.health_timeout_seconds
        attempt = 0
        while True:
            attempt += 1
            try:
                status_code = self.health_client.get_status_code(url, timeout=5.0)
            except httpx.HTTPError as exc:
                log.add(f"{_now()} health attempt {attempt}: HTTP error {exc.__class__.__name__}")
            except Exception as exc:  # pragma: no cover - defensive boundary for injected clients.
                log.add(f"{_now()} health attempt {attempt}: error {exc.__class__.__name__}")
            else:
                log.add(f"{_now()} health attempt {attempt}: HTTP {status_code}")
                if 200 <= status_code < 400:
                    log.add(f"{_now()} health check succeeded")
                    return

            if time.monotonic() >= deadline:
                break
            self.sleep(min(self.health_interval_seconds, max(0.0, deadline - time.monotonic())))

        raise ExecutorStepError(
            f"Health failed for {service['name']}: {url} did not return HTTP 2xx/3xx within "
            f"{int(self.health_timeout_seconds)} seconds."
        )

    def _check_internal_service_health(
        self,
        service: dict[str, object],
        network_name: str,
        log: SectionedLog,
        redactions: Sequence[str],
    ) -> None:
        url = f"{self._service_internal_url(service)}{self._service_health_path(service)}"
        deadline = time.monotonic() + self.health_timeout_seconds
        attempt = 0
        argv = [
            "docker",
            "run",
            "--rm",
            "--network",
            network_name,
            "curlimages/curl:8.10.1",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "5",
            url,
        ]
        while True:
            attempt += 1
            log.add(f"{_now()} health attempt {attempt}")
            try:
                self._run_checked(
                    argv,
                    log=log,
                    redactions=redactions,
                    phase="Health",
                    command_label=f"docker health helper {service['name']}",
                )
            except ExecutorStepError:
                if time.monotonic() >= deadline:
                    break
                self.sleep(min(self.health_interval_seconds, max(0.0, deadline - time.monotonic())))
            else:
                log.add(f"{_now()} health check succeeded")
                return

        raise ExecutorStepError(
            f"Health failed for {service['name']}: {url} did not return HTTP 2xx/3xx within "
            f"{int(self.health_timeout_seconds)} seconds."
        )

    def _service_internal_url(self, service: dict[str, object]) -> str:
        return f"http://{service['name']}:{service['container_port']}"

    def _service_health_path(self, service: dict[str, object]) -> str:
        path = str(service.get("health_check_path") or "/")
        if not path.startswith("/"):
            path = f"/{path}"
        return path

    def _health_url(self, project: dict[str, object]) -> str:
        if project.get("health_check_url"):
            return str(project["health_check_url"])
        path = str(project.get("health_check_path") or "/")
        if not path.startswith("/"):
            path = f"/{path}"
        return f"http://{project['preview_host']}:{project['preview_port']}{path}"

    def _run_checked(
        self,
        argv: Sequence[str],
        *,
        log: SectionedLog,
        redactions: Sequence[str],
        phase: str,
        command_label: str,
    ) -> CommandResult:
        log.add(f"{_now()} command: {_format_argv(argv, redactions)}")
        try:
            result = self.runner.run(list(argv))
        except OSError as exc:
            raise ExecutorStepError(f"{phase} failed: unable to execute {argv[0]}.") from exc

        if result.stdout:
            log.add(f"{_now()} stdout:")
            for line in redact_text(result.stdout.rstrip(), redactions).splitlines():
                log.add(line)
        if result.stderr:
            log.add(f"{_now()} stderr:")
            for line in redact_text(result.stderr.rstrip(), redactions).splitlines():
                log.add(line)
        log.add(f"{_now()} exit_code: {result.exit_code}")

        if result.exit_code != 0:
            raise ExecutorStepError(f"{phase} failed: {command_label} exited with code {result.exit_code}.")
        return result


class DryRunLocalDockerExecutor:
    def deploy_preview(self, request: ExecutorDeploymentRequest) -> ExecutorDeploymentResult:
        project = request.project
        timestamp = request.timestamp
        resolved_commit_sha = request.resolved_commit_sha or "dry-run"
        if _is_multi_service_project(project):
            return self._deploy_multi_service_preview(request, resolved_commit_sha)
        image_tag = request.image_tag or f"heimdall/{project['slug']}:{resolved_commit_sha[:7]}"
        log_content = "\n".join(
            [
                "[workspace]",
                f"{timestamp} dry-run: workspace preparation skipped for {project['repo_url']}",
                (
                    f"{timestamp} dry-run: tracked branch {project['tracked_branch']}, "
                    f"resolved commit {resolved_commit_sha}"
                ),
                "",
                "[build]",
                f"{timestamp} dry-run: would build {image_tag}",
                f"{timestamp} dry-run: Dockerfile path {project['dockerfile_path']}, context {project['build_context_path']}",
                "",
                "[container]",
                f"{timestamp} dry-run: container start skipped for preview target {project['preview_url']}",
                f"{timestamp} dry-run: no preview container was started or replaced",
                "",
                "[health]",
                (
                    f"{timestamp} dry-run: health check not executed against "
                    f"{project['health_check_url'] or project['health_check_path'] or '(none)'}"
                ),
                "",
                "[summary]",
                f"{timestamp} deployment {request.deployment_id} completed as dry_run_success",
                f"{timestamp} release is simulated only and was not marked current",
            ]
        )
        return ExecutorDeploymentResult(
            log_content=log_content,
            is_dry_run=True,
            status_message=(
                "Dry-run deployment completed successfully. "
                "No repository fetch, Docker build, or container start occurred."
            ),
            success=True,
            resolved_commit_sha=resolved_commit_sha,
            image_tag=image_tag,
        )

    def _deploy_multi_service_preview(
        self,
        request: ExecutorDeploymentRequest,
        resolved_commit_sha: str,
    ) -> ExecutorDeploymentResult:
        project = request.project
        timestamp = request.timestamp
        short_commit = resolved_commit_sha[:7]
        services = _project_services(project)
        public_service = _public_service(services)
        compatibility_image_tag = request.image_tag or f"heimdall/{project['slug']}-{public_service['name']}:{short_commit}"
        service_results: list[ExecutorServiceResult] = []
        lines = [
            "[workspace]",
            f"{timestamp} dry-run: workspace preparation skipped for {project['repo_url']}",
            f"{timestamp} dry-run: tracked branch {project['tracked_branch']}, resolved commit {resolved_commit_sha}",
        ]
        for service in services:
            service_name = str(service["name"])
            image_tag = f"heimdall/{project['slug']}-{service_name}:{short_commit}"
            lines.extend(
                [
                    "",
                    f"[build:{service_name}]",
                    f"{timestamp} dry-run: would build {image_tag}",
                    (
                        f"{timestamp} dry-run: Dockerfile path {service['dockerfile_path']}, "
                        f"context {service['build_context_path']}"
                    ),
                ]
            )
            service_results.append(
                ExecutorServiceResult(
                    name=service_name,
                    image_tag=image_tag,
                    image_id=None,
                    container_name=f"heimdall-preview-{project['slug']}-{service_name}",
                    container_id=None,
                    container_port=int(service["container_port"]),
                    public=bool(service["public"]),
                    preview_url=str(project["preview_url"]) if bool(service["public"]) else None,
                    internal_url=None if bool(service["public"]) else f"http://{service_name}:{service['container_port']}",
                    status="simulated",
                )
            )
        for service in services:
            service_name = str(service["name"])
            target = (
                str(project["preview_url"])
                if bool(service["public"])
                else f"http://{service_name}:{service['container_port']}"
            )
            lines.extend(
                [
                    "",
                    f"[container:{service_name}]",
                    f"{timestamp} dry-run: container start skipped for {target}",
                    f"{timestamp} dry-run: no preview container was started or replaced",
                    "",
                    f"[health:{service_name}]",
                    f"{timestamp} dry-run: health check not executed against {service.get('health_check_path') or '/'}",
                ]
            )
        lines.extend(
            [
                "",
                "[summary]",
                f"{timestamp} deployment {request.deployment_id} completed as dry_run_success",
                f"{timestamp} release is simulated only and was not marked current",
            ]
        )
        return ExecutorDeploymentResult(
            log_content="\n".join(lines),
            is_dry_run=True,
            status_message=(
                "Dry-run deployment completed successfully. "
                "No repository fetch, Docker build, or container start occurred."
            ),
            success=True,
            resolved_commit_sha=resolved_commit_sha,
            image_tag=compatibility_image_tag,
            service_results=tuple(service_results),
        )
