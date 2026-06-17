from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status

from ..config import get_settings
from ..db import DBConnection, DBRow, connect, resolve_log_path, row_to_dict
from ..models import (
    ACTIVE_DEPLOYMENT_STATUSES,
    DeploymentStatus,
    PortAllocationStatus,
    ProjectStatus,
    ReleaseStatus,
    TriggerType,
)
from ..schemas import (
    DeploymentLogsRead,
    DeploymentRead,
    DeploymentRequest,
    DeploymentResult,
    ReleaseRead,
    RollbackResponse,
)
from .executor_local_docker import (
    DryRunLocalDockerExecutor,
    ExecutorDeploymentRequest,
    ExecutorDeploymentResult,
    ExecutorServiceResult,
    RealLocalDockerExecutor,
    redact_text,
    redaction_values_for_settings,
)
from . import env_bundles
from .managed_database_runtime import apply_managed_database_runtime
from .projects import utc_now


def _as_bool(value: object) -> bool:
    return bool(int(value)) if value is not None else False


def _serialize_deployment(row: DBRow) -> DeploymentRead:
    data = row_to_dict(row)
    assert data is not None
    normalized = {**data, "is_dry_run": _as_bool(data["is_dry_run"])}
    return DeploymentRead(**normalized)


def _fetch_release_services(connection: DBConnection, release_id: str) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT *
        FROM release_services
        WHERE release_id = ?
        ORDER BY service_name ASC
        """,
        (release_id,),
    ).fetchall()
    services: list[dict[str, object]] = []
    for row in rows:
        data = row_to_dict(row)
        assert data is not None
        services.append(
            {
                "name": str(data["service_name"]),
                "image_tag": str(data["image_tag"]),
                "image_id": data["image_id"],
                "container_name": data["container_name"],
                "container_port": int(data["container_port"]),
                "public": _as_bool(data["is_public"]),
                "preview_url": data["preview_url"],
                "internal_url": data["internal_url"],
                "status": str(data["status"]),
            }
        )
    return services


def _serialize_release(row: DBRow, connection: DBConnection) -> ReleaseRead:
    data = row_to_dict(row)
    assert data is not None
    is_current = _as_bool(data["is_current"])
    is_dry_run = _as_bool(data["is_dry_run"])
    normalized = {
        **data,
        "is_current": is_current,
        "is_dry_run": is_dry_run,
    }
    return ReleaseRead(
        **normalized,
        rollback_supported=False,
        services=_fetch_release_services(connection, str(data["id"])),
    )

UTC = timezone.utc


def _get_project_row(connection: DBConnection, project_id: str) -> DBRow:
    row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' was not found.")
    return row


def _get_deployment_row(connection: DBConnection, deployment_id: str) -> DBRow:
    row = connection.execute("SELECT * FROM deployments WHERE id = ?", (deployment_id,)).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Deployment '{deployment_id}' was not found."
        )
    return row


def _get_release_row(connection: DBConnection, project_id: str, release_id: str) -> DBRow:
    row = connection.execute(
        "SELECT * FROM releases WHERE id = ? AND project_id = ?",
        (release_id, project_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Release '{release_id}' was not found.")
    return row


def _json_dict(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(item) for key, item in parsed.items()}


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str)]


def _env_keys(value: object) -> set[str]:
    if not isinstance(value, dict):
        return set()
    return {str(key) for key in value}


def _bundle_key_names(service: dict[str, object]) -> set[str]:
    bundle = service.get("env_bundle")
    if not isinstance(bundle, dict):
        return set()
    key_names = bundle.get("key_names") or []
    if not isinstance(key_names, list):
        return set()
    return {str(key) for key in key_names}


def _ensure_no_env_bundle_conflicts(services: list[dict[str, object]]) -> None:
    for service in services:
        bundle_keys = _bundle_key_names(service)
        if not bundle_keys:
            continue
        service_name = str(service.get("name") or service.get("id") or "service")
        runtime_conflicts = sorted(bundle_keys & _env_keys(service.get("runtime_env")))
        if runtime_conflicts:
            joined = ", ".join(runtime_conflicts)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Env bundle for service '{service_name}' conflicts with runtime_env key(s): {joined}.",
            )
        managed_conflicts = sorted(bundle_keys & _env_keys(service.get("managed_runtime_env")))
        if managed_conflicts:
            joined = ", ".join(managed_conflicts)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Env bundle for service '{service_name}' conflicts with managed runtime env key(s): {joined}.",
            )


def _single_project_service(project: dict[str, object]) -> dict[str, object]:
    return {
        "id": None,
        "name": "app",
        "build_context_path": str(project["build_context_path"]),
        "dockerfile_path": str(project["dockerfile_path"] or "Dockerfile"),
        "container_port": int(project["container_port"]),
        "public": True,
        "health_check_path": project["health_check_path"],
        "startup_order": 0,
        "build_env": {},
        "runtime_env": {},
        "required_secrets": [],
    }


def _load_project_for_executor(
    connection: DBConnection,
    project_row: DBRow,
    *,
    settings=None,
    include_managed_database: bool = False,
) -> tuple[dict[str, object], list[str]]:
    project = row_to_dict(project_row)
    assert project is not None
    rows = connection.execute(
        """
        SELECT *
        FROM project_services
        WHERE project_id = ?
        ORDER BY startup_order ASC, name ASC
        """,
        (project["id"],),
    ).fetchall()
    services: list[dict[str, object]] = []
    for row in rows:
        data = row_to_dict(row)
        assert data is not None
        service_id = str(data["id"])
        env_bundle = env_bundles.fetch_executor_env_bundle(
            connection,
            project_id=str(project["id"]),
            service_id=service_id,
        )
        service = {
            "id": service_id,
            "name": str(data["name"]),
            "build_context_path": str(data["build_context_path"]),
            "dockerfile_path": str(data["dockerfile_path"]),
            "container_port": int(data["container_port"]),
            "public": _as_bool(data["is_public"]),
            "health_check_path": data["health_check_path"],
            "startup_order": int(data["startup_order"]),
            "build_env": _json_dict(data["build_env_json"]),
            "runtime_env": _json_dict(data["runtime_env_json"]),
            "required_secrets": _json_list(data["required_secrets_json"]),
        }
        if env_bundle:
            service["env_bundle"] = env_bundle
        services.append(
            service
        )
    if not services:
        services = [_single_project_service(project)]
    redactions: list[str] = []
    if include_managed_database:
        if settings is None:
            settings = get_settings()
        redactions = apply_managed_database_runtime(
            connection,
            settings=settings,
            project=project,
            services=services,
        )
    _ensure_no_env_bundle_conflicts(services)
    project.pop("run_as_heimdall_child", None)
    return {**project, "services": services}, redactions


def _public_service(project: dict[str, object]) -> dict[str, object]:
    for service in project.get("services") or []:
        if isinstance(service, dict) and bool(service.get("public")):
            return service
    return _single_project_service(project)


def _compatibility_image_tag(project: dict[str, object], short_commit: str) -> str:
    if str(project.get("deploy_mode")) == "multi_service_dockerfile":
        public_service = _public_service(project)
        return f"heimdall/{project['slug']}-{public_service['name']}:{short_commit}"
    return f"heimdall/{project['slug']}:{short_commit}"


def _ensure_no_active_deployment(connection: DBConnection, project_id: str) -> None:
    row = connection.execute(
        """
        SELECT id, status
        FROM deployments
        WHERE project_id = ? AND status IN (?, ?, ?, ?, ?)
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (project_id, *ACTIVE_DEPLOYMENT_STATUSES),
    ).fetchone()
    if row is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project already has an active deployment: {row['id']} ({row['status']}).",
        )


def _synthetic_commit_sha(project_id: str, requested_ref: str | None, requested_commit_sha: str | None) -> str:
    seed = requested_commit_sha or requested_ref or "main"
    digest = hashlib.sha1(f"{project_id}:{seed}:{utc_now()}".encode("utf-8"), usedforsecurity=False).hexdigest()
    return requested_commit_sha or digest


def _write_log_file(log_path: Path, content: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(content, encoding="utf-8")


def _write_redacted_log_file(log_path: Path, content: str, settings) -> None:
    _write_log_file(log_path, redact_text(content, redaction_values_for_settings(settings)))


def _write_redacted_log_file_with_values(
    log_path: Path,
    content: str,
    settings,
    redactions: list[str],
) -> None:
    _write_log_file(log_path, redact_text(content, [*redaction_values_for_settings(settings), *redactions]))


def _create_deployment_row(
    connection: DBConnection,
    *,
    deployment_id: str,
    project_id: str,
    trigger_type: str,
    requested_ref: str | None,
    requested_commit_sha: str | None,
    status: str,
    status_message: str,
    is_dry_run: bool,
    created_at: str,
    previous_release_id: str | None = None,
    log_path: str | None = None,
    resolved_commit_sha: str | None = None,
    image_tag: str | None = None,
    target_release_id: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    duration_ms: int | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO deployments (
            id, project_id, trigger_type, requested_ref, requested_commit_sha, resolved_commit_sha,
            image_tag, previous_release_id, target_release_id, status, status_message, is_dry_run,
            started_at, finished_at, duration_ms, log_path, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            deployment_id,
            project_id,
            trigger_type,
            requested_ref,
            requested_commit_sha,
            resolved_commit_sha,
            image_tag,
            previous_release_id,
            target_release_id,
            status,
            status_message,
            int(is_dry_run),
            started_at,
            finished_at,
            duration_ms,
            log_path,
            created_at,
        ),
    )


def _fallback_service_results(
    project: dict[str, object],
    *,
    image_tag: str,
    image_id: str | None,
    status_value: str,
) -> tuple[ExecutorServiceResult, ...]:
    if str(project.get("deploy_mode")) == "multi_service_dockerfile":
        results: list[ExecutorServiceResult] = []
        short_tag = image_tag.rsplit(":", 1)[-1] if ":" in image_tag else "preview"
        for service in project.get("services") or []:
            if not isinstance(service, dict):
                continue
            service_name = str(service["name"])
            service_image_tag = f"heimdall/{project['slug']}-{service_name}:{short_tag}"
            results.append(
                ExecutorServiceResult(
                    name=service_name,
                    image_tag=service_image_tag,
                    image_id=image_id if service_image_tag == image_tag else None,
                    container_name=f"heimdall-preview-{project['slug']}-{service_name}",
                    container_id=None,
                    container_port=int(service["container_port"]),
                    public=bool(service["public"]),
                    preview_url=str(project["preview_url"]) if bool(service["public"]) else None,
                    internal_url=None if bool(service["public"]) else f"http://{service_name}:{service['container_port']}",
                    status=status_value,
                )
            )
        return tuple(results)

    return (
        ExecutorServiceResult(
            name="app",
            image_tag=image_tag,
            image_id=image_id,
            container_name=f"heimdall-preview-{project['slug']}",
            container_id=None,
            container_port=int(project["container_port"]),
            public=True,
            preview_url=str(project["preview_url"]),
            internal_url=None,
            status=status_value,
        ),
    )


def _insert_release_services(
    connection: DBConnection,
    *,
    release_id: str,
    service_results: tuple[ExecutorServiceResult, ...],
    created_at: str,
) -> None:
    for service in service_results:
        connection.execute(
            """
            INSERT INTO release_services (
                id, release_id, service_name, image_tag, image_id, container_name, container_port,
                is_public, preview_url, internal_url, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"release_service_{uuid.uuid4().hex[:12]}",
                release_id,
                service.name,
                service.image_tag,
                service.image_id,
                service.container_name,
                service.container_port,
                int(service.public),
                service.preview_url,
                service.internal_url,
                service.status,
                created_at,
            ),
        )


def create_manual_deployment(project_id: str, payload: DeploymentRequest) -> DeploymentResult:
    if payload.dry_run:
        return _create_dry_run_deployment(project_id, payload)
    return _create_real_deployment(project_id, payload)


def _create_dry_run_deployment(project_id: str, payload: DeploymentRequest) -> DeploymentResult:
    settings = get_settings()
    with connect(settings) as connection:
        project_row = _get_project_row(connection, project_id)
        project, _ = _load_project_for_executor(connection, project_row)
        _ensure_no_active_deployment(connection, project_id)

        deployment_id = f"deploy_{uuid.uuid4().hex[:12]}"
        release_id = f"release_{uuid.uuid4().hex[:12]}"
        created_at = utc_now()
        started_at_dt = datetime.now(UTC)
        started_at = started_at_dt.isoformat()
        resolved_commit_sha = _synthetic_commit_sha(project_id, payload.ref, payload.commit_sha)
        short_commit = resolved_commit_sha[:7]
        image_tag = _compatibility_image_tag(project, short_commit)
        log_relative_path = f"deployments/{deployment_id}.log"
        previous_release_id = project["current_release_id"]

        _create_deployment_row(
            connection,
            deployment_id=deployment_id,
            project_id=project_id,
            trigger_type=payload.trigger_type.value,
            requested_ref=payload.ref or project["tracked_branch"],
            requested_commit_sha=payload.commit_sha,
            status=DeploymentStatus.HEALTH_CHECKING.value,
            status_message="Dry-run deployment is executing simulated workspace/build/container/health steps.",
            is_dry_run=True,
            created_at=created_at,
            previous_release_id=previous_release_id,
            log_path=log_relative_path,
            started_at=started_at,
            resolved_commit_sha=resolved_commit_sha,
            image_tag=image_tag,
        )

        executor = DryRunLocalDockerExecutor()
        executor_result = executor.deploy_preview(
            ExecutorDeploymentRequest(
                project=project,
                deployment_id=deployment_id,
                timestamp=utc_now(),
                resolved_commit_sha=resolved_commit_sha,
                image_tag=image_tag,
            )
        )
        _write_redacted_log_file(resolve_log_path(log_relative_path, settings), executor_result.log_content, settings)
        service_results = executor_result.service_results or _fallback_service_results(
            project,
            image_tag=image_tag,
            image_id=None,
            status_value=ReleaseStatus.SIMULATED.value,
        )

        connection.execute(
            """
            INSERT INTO releases (
                id, project_id, deployment_id, commit_sha, short_commit_sha, image_tag, image_id,
                status, is_current, is_dry_run, created_at, activated_at, last_used_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                release_id,
                project_id,
                deployment_id,
                resolved_commit_sha,
                short_commit,
                image_tag,
                None,
                ReleaseStatus.SIMULATED.value,
                0,
                1,
                created_at,
                None,
                None,
            ),
        )
        _insert_release_services(
            connection,
            release_id=release_id,
            service_results=service_results,
            created_at=created_at,
        )

        finished_at_dt = datetime.now(UTC)
        finished_at = finished_at_dt.isoformat()
        duration_ms = int((finished_at_dt - started_at_dt).total_seconds() * 1000)
        connection.execute(
            """
            UPDATE deployments
            SET target_release_id = ?, status = ?, status_message = ?, finished_at = ?, duration_ms = ?
            WHERE id = ?
            """,
            (
                release_id,
                DeploymentStatus.DRY_RUN_SUCCESS.value,
                executor_result.status_message,
                finished_at,
                duration_ms,
                deployment_id,
            ),
        )
        connection.execute(
            """
            UPDATE projects
            SET updated_at = ?
            WHERE id = ?
            """,
            (finished_at, project_id),
        )

        deployment_row = _get_deployment_row(connection, deployment_id)
        release_row = _get_release_row(connection, project_id, release_id)
        return DeploymentResult(
            deployment=_serialize_deployment(deployment_row),
            release=_serialize_release(release_row, connection),
        )


def _executor_exception_result(deployment_id: str, exc: Exception) -> ExecutorDeploymentResult:
    message = f"Deployment failed: executor raised {exc.__class__.__name__}."
    timestamp = utc_now()
    return ExecutorDeploymentResult(
        log_content="\n".join(
            [
                "[summary]",
                f"{timestamp} deployment {deployment_id} failed",
                f"{timestamp} {message}",
            ]
        ),
        is_dry_run=False,
        status_message=message,
        success=False,
    )


def _create_real_deployment(project_id: str, payload: DeploymentRequest) -> DeploymentResult:
    settings = get_settings()
    deployment_id = f"deploy_{uuid.uuid4().hex[:12]}"
    release_id = f"release_{uuid.uuid4().hex[:12]}"
    created_at = utc_now()
    started_at_dt = datetime.now(UTC)
    started_at = started_at_dt.isoformat()
    log_relative_path = f"deployments/{deployment_id}.log"

    with connect(settings) as connection:
        project_row = _get_project_row(connection, project_id)
        project, managed_database_redactions = _load_project_for_executor(
            connection,
            project_row,
            settings=settings,
            include_managed_database=True,
        )
        _ensure_no_active_deployment(connection, project_id)

        previous_release_id = project["current_release_id"]
        previous_project_status = str(project["status"])
        requested_ref = payload.ref or str(project["tracked_branch"])

        _create_deployment_row(
            connection,
            deployment_id=deployment_id,
            project_id=project_id,
            trigger_type=payload.trigger_type.value,
            requested_ref=requested_ref,
            requested_commit_sha=payload.commit_sha,
            status=DeploymentStatus.FETCHING.value,
            status_message="Preview deployment is preparing workspace and fetching repository.",
            is_dry_run=False,
            created_at=created_at,
            previous_release_id=previous_release_id,
            log_path=log_relative_path,
            started_at=started_at,
        )
        connection.execute(
            """
            UPDATE projects
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (ProjectStatus.DEPLOYING.value, started_at, project_id),
        )

    try:
        executor = RealLocalDockerExecutor(settings=settings)
        executor_result = executor.deploy_preview(
            ExecutorDeploymentRequest(
                project=project,
                deployment_id=deployment_id,
                timestamp=utc_now(),
                release_id=release_id,
                requested_ref=requested_ref,
                requested_commit_sha=payload.commit_sha,
                extra_redactions=tuple(managed_database_redactions),
            )
        )
    except Exception as exc:  # pragma: no cover - defensive executor boundary.
        executor_result = _executor_exception_result(deployment_id, exc)

    success = executor_result.success and bool(executor_result.resolved_commit_sha and executor_result.image_tag)
    log_content = executor_result.log_content
    all_redactions = [*redaction_values_for_settings(settings), *managed_database_redactions]
    status_message = redact_text(executor_result.status_message, all_redactions)
    if executor_result.success and not success:
        status_message = "Deployment failed: executor did not return release metadata."
        log_content = "\n".join([log_content, "", "[summary]", f"{utc_now()} {status_message}"])

    _write_redacted_log_file_with_values(
        resolve_log_path(log_relative_path, settings),
        log_content,
        settings,
        managed_database_redactions,
    )

    finished_at_dt = datetime.now(UTC)
    finished_at = finished_at_dt.isoformat()
    duration_ms = int((finished_at_dt - started_at_dt).total_seconds() * 1000)

    with connect(settings) as connection:
        if success:
            assert executor_result.resolved_commit_sha is not None
            assert executor_result.image_tag is not None
            short_commit = executor_result.resolved_commit_sha[:7]
            if previous_release_id:
                connection.execute(
                    """
                    UPDATE releases
                    SET status = ?, is_current = 0, last_used_at = ?
                    WHERE id = ? AND project_id = ?
                    """,
                    (ReleaseStatus.SUPERSEDED.value, finished_at, previous_release_id, project_id),
                )
            connection.execute(
                """
                INSERT INTO releases (
                    id, project_id, deployment_id, commit_sha, short_commit_sha, image_tag, image_id,
                    status, is_current, is_dry_run, created_at, activated_at, last_used_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    release_id,
                    project_id,
                    deployment_id,
                    executor_result.resolved_commit_sha,
                    short_commit,
                    executor_result.image_tag,
                    executor_result.image_id,
                    ReleaseStatus.CURRENT.value,
                    1,
                    0,
                    created_at,
                    finished_at,
                    finished_at,
                ),
            )
            service_results = executor_result.service_results or _fallback_service_results(
                project,
                image_tag=executor_result.image_tag,
                image_id=executor_result.image_id,
                status_value=ReleaseStatus.AVAILABLE.value,
            )
            _insert_release_services(
                connection,
                release_id=release_id,
                service_results=service_results,
                created_at=created_at,
            )
            connection.execute(
                """
                UPDATE deployments
                SET target_release_id = ?, status = ?, status_message = ?, resolved_commit_sha = ?,
                    image_tag = ?, finished_at = ?, duration_ms = ?
                WHERE id = ?
                """,
                (
                    release_id,
                    DeploymentStatus.SUCCESS.value,
                    status_message,
                    executor_result.resolved_commit_sha,
                    executor_result.image_tag,
                    finished_at,
                    duration_ms,
                    deployment_id,
                ),
            )
            connection.execute(
                """
                UPDATE projects
                SET status = ?, current_release_id = ?, current_commit_sha = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    ProjectStatus.HEALTHY.value,
                    release_id,
                    executor_result.resolved_commit_sha,
                    finished_at,
                    project_id,
                ),
            )
            connection.execute(
                """
                UPDATE port_allocations
                SET status = ?, updated_at = ?
                WHERE project_id = ?
                """,
                (PortAllocationStatus.ACTIVE.value, finished_at, project_id),
            )
            deployment_row = _get_deployment_row(connection, deployment_id)
            release_row = _get_release_row(connection, project_id, release_id)
            return DeploymentResult(
                deployment=_serialize_deployment(deployment_row),
                release=_serialize_release(release_row, connection),
            )

        next_project_status = (
            ProjectStatus.FAILED.value
            if executor_result.preview_unavailable or not previous_release_id
            else previous_project_status
        )
        connection.execute(
            """
            UPDATE deployments
            SET status = ?, status_message = ?, resolved_commit_sha = ?, image_tag = ?,
                finished_at = ?, duration_ms = ?
            WHERE id = ?
            """,
            (
                DeploymentStatus.FAILED.value,
                status_message,
                executor_result.resolved_commit_sha,
                executor_result.image_tag,
                finished_at,
                duration_ms,
                deployment_id,
            ),
        )
        connection.execute(
            """
            UPDATE projects
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (next_project_status, finished_at, project_id),
        )
        deployment_row = _get_deployment_row(connection, deployment_id)
        return DeploymentResult(deployment=_serialize_deployment(deployment_row), release=None)


def get_deployment(deployment_id: str) -> DeploymentRead:
    with connect() as connection:
        return _serialize_deployment(_get_deployment_row(connection, deployment_id))


def list_project_deployments(project_id: str) -> list[DeploymentRead]:
    with connect() as connection:
        _get_project_row(connection, project_id)
        rows = connection.execute(
            "SELECT * FROM deployments WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
        return [_serialize_deployment(row) for row in rows]


def get_deployment_logs(deployment_id: str) -> DeploymentLogsRead:
    settings = get_settings()
    with connect(settings) as connection:
        row = _get_deployment_row(connection, deployment_id)
        data = row_to_dict(row)
        assert data is not None
        content = ""
        if data["log_path"]:
            log_file = resolve_log_path(data["log_path"], settings)
            if log_file.exists():
                content = log_file.read_text(encoding="utf-8")
        return DeploymentLogsRead(deployment_id=deployment_id, log_path=data["log_path"], content=content)


def list_releases(project_id: str) -> list[ReleaseRead]:
    with connect() as connection:
        _get_project_row(connection, project_id)
        rows = connection.execute(
            "SELECT * FROM releases WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
        return [_serialize_release(row, connection) for row in rows]


def rollback_release(project_id: str, release_id: str) -> RollbackResponse:
    settings = get_settings()
    with connect(settings) as connection:
        project_row = _get_project_row(connection, project_id)
        project = row_to_dict(project_row)
        assert project is not None
        release_row = _get_release_row(connection, project_id, release_id)
        release = row_to_dict(release_row)
        assert release is not None
        _ensure_no_active_deployment(connection, project_id)

        deployment_id = f"deploy_{uuid.uuid4().hex[:12]}"
        created_at = utc_now()
        log_relative_path = f"deployments/{deployment_id}.log"
        if _as_bool(release["is_dry_run"]):
            message = "Rollback is unsupported for simulated dry-run releases because no real Docker image exists."
        else:
            message = "Rollback is not implemented for preview releases yet."
        log_content = "\n".join(
            [
                "[container]",
                f"{created_at} rollback refused for release {release_id}",
                "",
                "[summary]",
                f"{created_at} {message}",
            ]
        )
        _write_log_file(resolve_log_path(log_relative_path, settings), log_content)
        _create_deployment_row(
            connection,
            deployment_id=deployment_id,
            project_id=project_id,
            trigger_type=TriggerType.ROLLBACK.value,
            requested_ref=release["commit_sha"],
            requested_commit_sha=release["commit_sha"],
            status=DeploymentStatus.ROLLBACK_FAILED.value,
            status_message=message,
            is_dry_run=True,
            created_at=created_at,
            previous_release_id=project["current_release_id"],
            log_path=log_relative_path,
            resolved_commit_sha=release["commit_sha"],
            image_tag=release["image_tag"],
            target_release_id=release_id,
            started_at=created_at,
            finished_at=created_at,
            duration_ms=0,
        )
        deployment_row = _get_deployment_row(connection, deployment_id)
        return RollbackResponse(
            supported=False,
            message=message,
            deployment=_serialize_deployment(deployment_row),
        )
