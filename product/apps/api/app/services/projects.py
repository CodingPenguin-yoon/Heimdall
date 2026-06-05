from __future__ import annotations

import sqlite3
import uuid
import json
from datetime import UTC, datetime
from enum import Enum

from fastapi import HTTPException, status

from ..config import Settings, get_settings
from ..db import connect, row_to_dict
from ..models import DeployMode, PortAllocationStatus, ProjectStatus
from ..schemas import ProjectCreate, ProjectRead, ProjectServiceRead, ProjectUpdate, WebhookRegistrationRead
from ..validation import (
    bad_request,
    slugify,
    validate_container_port,
    validate_env_map,
    validate_health_check,
    validate_preview_port,
    validate_relative_path,
    validate_required_secrets,
    validate_repo_url,
    validate_service_name,
    validate_slug,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _as_bool(value: object) -> bool:
    return bool(int(value)) if value is not None else False


def _project_not_found(project_id: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' was not found.")


def _enum_value(value: object) -> object:
    return value.value if isinstance(value, Enum) else value


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


def _single_service_from_project(project: dict[str, object]) -> dict[str, object]:
    return {
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


def _normalize_service_payloads(raw_services: object) -> list[dict[str, object]]:
    if not isinstance(raw_services, list) or not raw_services:
        raise bad_request("Multi-service Dockerfile deploy requires at least one service.")

    services: list[dict[str, object]] = []
    seen_names: set[str] = set()
    public_count = 0
    for raw_service in raw_services:
        if not isinstance(raw_service, dict):
            raise bad_request("Each service must be an object.")
        name = validate_service_name(str(raw_service.get("name", "")))
        if name in seen_names:
            raise bad_request(f"Duplicate service name '{name}' is not allowed.")
        seen_names.add(name)

        health_check_path, health_check_url = validate_health_check(raw_service.get("health_check_path") or "/", None)
        if health_check_url:
            raise bad_request("Service health checks must use a path, not a URL.")
        is_public = bool(raw_service.get("public", False))
        if is_public:
            public_count += 1
        build_env = raw_service.get("build_env") or {}
        runtime_env = raw_service.get("runtime_env") or {}
        required_secrets = raw_service.get("required_secrets") or []
        if not isinstance(build_env, dict):
            raise bad_request(f"services.{name}.build_env must be an object.")
        if not isinstance(runtime_env, dict):
            raise bad_request(f"services.{name}.runtime_env must be an object.")
        if not isinstance(required_secrets, list):
            raise bad_request(f"services.{name}.required_secrets must be a list.")

        services.append(
            {
                "name": name,
                "build_context_path": validate_relative_path(
                    str(raw_service.get("build_context_path", ".")),
                    f"services.{name}.build_context_path",
                ),
                "dockerfile_path": validate_relative_path(
                    str(raw_service.get("dockerfile_path", "Dockerfile")),
                    f"services.{name}.dockerfile_path",
                ),
                "container_port": validate_container_port(int(raw_service.get("container_port", 0))),
                "public": is_public,
                "health_check_path": health_check_path,
                "startup_order": int(raw_service.get("startup_order", 0)),
                "build_env": validate_env_map(build_env, f"services.{name}.build_env"),
                "runtime_env": validate_env_map(runtime_env, f"services.{name}.runtime_env"),
                "required_secrets": validate_required_secrets(required_secrets),
            }
        )

    if public_count != 1:
        raise bad_request("Multi-service Dockerfile deploy requires exactly one public service.")
    return services


def _public_service(services: list[dict[str, object]]) -> dict[str, object]:
    for service in services:
        if bool(service["public"]):
            return service
    raise bad_request("Multi-service Dockerfile deploy requires exactly one public service.")


def _normalize_project_payload(
    payload: dict[str, object],
    settings: Settings,
    existing: dict[str, object] | None = None,
    existing_services: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    name = str(payload.get("name", existing["name"] if existing else "")).strip()
    if not name:
        raise bad_request("Project name is required.")

    raw_slug = payload.get("slug", existing["slug"] if existing else None)
    slug = validate_slug(str(raw_slug).strip()) if raw_slug else validate_slug(slugify(name))

    provider = str(_enum_value(payload.get("provider", existing["provider"] if existing else ""))).strip()
    repo_url = validate_repo_url(str(payload.get("repo_url", existing["repo_url"] if existing else "")).strip())
    default_branch = str(payload.get("default_branch", existing["default_branch"] if existing else "main")).strip()
    tracked_branch = str(payload.get("tracked_branch", existing["tracked_branch"] if existing else "main")).strip()
    if not tracked_branch:
        raise bad_request("tracked_branch is required.")

    deploy_mode = str(
        _enum_value(payload.get("deploy_mode", existing["deploy_mode"] if existing else DeployMode.DOCKERFILE.value))
    )
    if deploy_mode == DeployMode.COMPOSE.value:
        raise bad_request("Compose deploy mode is unsupported in the MVP local Docker executor.")
    if deploy_mode not in {DeployMode.DOCKERFILE.value, DeployMode.MULTI_SERVICE_DOCKERFILE.value}:
        raise bad_request("deploy_mode must be 'dockerfile' or 'multi_service_dockerfile'.")

    compose_file_raw = payload.get("compose_file_path", existing["compose_file_path"] if existing else None)
    compose_file_path = (
        validate_relative_path(str(compose_file_raw), "compose_file_path") if compose_file_raw else None
    )
    if compose_file_path:
        raise bad_request("compose_file_path is unsupported until compose mode is implemented.")

    preview_port_raw = payload.get("preview_port", existing["preview_port"] if existing else None)
    preview_port = None if preview_port_raw is None else validate_preview_port(int(preview_port_raw), settings)

    services: list[dict[str, object]]
    if deploy_mode == DeployMode.MULTI_SERVICE_DOCKERFILE.value:
        raw_services = payload.get("services", existing_services)
        services = _normalize_service_payloads(raw_services)
        public_service = _public_service(services)
        build_context_path = str(public_service["build_context_path"])
        dockerfile_path = str(public_service["dockerfile_path"])
        container_port = int(public_service["container_port"])
        health_check_path = public_service["health_check_path"]
        health_check_url = None
    else:
        if payload.get("services") is not None:
            raise bad_request("services are only supported for multi_service_dockerfile deploy mode.")
        build_context_path = validate_relative_path(
            str(payload.get("build_context_path", existing["build_context_path"] if existing else ".")),
            "build_context_path",
        )
        dockerfile_raw = payload.get("dockerfile_path", existing["dockerfile_path"] if existing else "Dockerfile")
        if not dockerfile_raw:
            raise bad_request("dockerfile_path is required for dockerfile deploy mode.")
        dockerfile_path = validate_relative_path(str(dockerfile_raw), "dockerfile_path")
        container_port_raw = payload.get("container_port", existing["container_port"] if existing else None)
        if container_port_raw is None:
            raise bad_request("container_port is required for dockerfile deploy mode.")
        container_port = validate_container_port(int(container_port_raw))
        health_check_path, health_check_url = validate_health_check(
            payload.get("health_check_path", existing["health_check_path"] if existing else None),
            payload.get("health_check_url", existing["health_check_url"] if existing else None),
        )
        services = [
            {
                "name": "app",
                "build_context_path": build_context_path,
                "dockerfile_path": dockerfile_path,
                "container_port": container_port,
                "public": True,
                "health_check_path": health_check_path,
                "startup_order": 0,
                "build_env": {},
                "runtime_env": {},
                "required_secrets": [],
            }
        ]
    auto_deploy_enabled = payload.get("auto_deploy_enabled", existing["auto_deploy_enabled"] if existing else False)

    return {
        "name": name,
        "slug": slug,
        "provider": provider,
        "repo_url": repo_url,
        "default_branch": default_branch,
        "tracked_branch": tracked_branch,
        "deploy_mode": deploy_mode,
        "build_context_path": build_context_path,
        "dockerfile_path": dockerfile_path,
        "compose_file_path": None,
        "container_port": container_port,
        "preview_port": preview_port,
        "health_check_path": health_check_path,
        "health_check_url": health_check_url,
        "auto_deploy_enabled": bool(auto_deploy_enabled),
        "services": services,
    }


def _fetch_latest_deployment(connection: sqlite3.Connection, project_id: str) -> dict[str, object] | None:
    row = connection.execute(
        """
        SELECT id, status, created_at
        FROM deployments
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    return row_to_dict(row)


def _fetch_project_services(
    connection: sqlite3.Connection,
    project: dict[str, object],
    *,
    synthesize_single: bool = True,
) -> list[dict[str, object]]:
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
        services.append(
            {
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
        )
    if services:
        return services
    if synthesize_single and str(project["deploy_mode"]) == DeployMode.DOCKERFILE.value:
        return [_single_service_from_project(project)]
    return []


def _replace_project_services(
    connection: sqlite3.Connection,
    project_id: str,
    services: list[dict[str, object]],
    timestamp: str,
) -> None:
    connection.execute("DELETE FROM project_services WHERE project_id = ?", (project_id,))
    for service in services:
        connection.execute(
            """
            INSERT INTO project_services (
                id, project_id, name, build_context_path, dockerfile_path, container_port,
                is_public, health_check_path, startup_order, build_env_json, runtime_env_json,
                required_secrets_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"service_{uuid.uuid4().hex[:12]}",
                project_id,
                service["name"],
                service["build_context_path"],
                service["dockerfile_path"],
                service["container_port"],
                int(bool(service["public"])),
                service["health_check_path"],
                service["startup_order"],
                json.dumps(service["build_env"], sort_keys=True),
                json.dumps(service["runtime_env"], sort_keys=True),
                json.dumps(service["required_secrets"]),
                timestamp,
                timestamp,
            ),
        )


def _fetch_webhook_registration(connection: sqlite3.Connection, project_id: str) -> WebhookRegistrationRead | None:
    row = connection.execute(
        """
        SELECT *
        FROM project_webhook_registrations
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        return None

    data = row_to_dict(row)
    assert data is not None
    try:
        events = json.loads(str(data.get("events") or "[]"))
    except json.JSONDecodeError:
        events = []
    return WebhookRegistrationRead(
        provider=str(data["provider"]),
        status=str(data["status"]),
        webhook_url=str(data["webhook_url"]),
        provider_project_id=str(data["provider_project_id"]),
        provider_webhook_id=data["provider_webhook_id"],
        active=_as_bool(data["active"]),
        events=[str(event) for event in events if isinstance(event, str)],
        registered_at=data["registered_at"],
        updated_at=data["updated_at"],
        message=str(data["message"] or ""),
    )


def _serialize_project(connection: sqlite3.Connection, row: sqlite3.Row) -> ProjectRead:
    data = row_to_dict(row)
    assert data is not None
    latest = _fetch_latest_deployment(connection, data["id"])
    normalized = {
        **data,
        "auto_deploy_enabled": _as_bool(data["auto_deploy_enabled"]),
        "services": [ProjectServiceRead(**service) for service in _fetch_project_services(connection, data)],
    }
    return ProjectRead(
        **normalized,
        has_real_preview=bool(data["current_release_id"]),
        last_deployment_id=latest["id"] if latest else None,
        last_deployment_status=latest["status"] if latest else None,
        last_deployment_at=latest["created_at"] if latest else None,
        webhook_registration=_fetch_webhook_registration(connection, data["id"]),
    )


def _ensure_port_available(
    connection: sqlite3.Connection,
    host: str,
    port: int,
    exclude_project_id: str | None = None,
) -> None:
    row = connection.execute(
        """
        SELECT project_id
        FROM port_allocations
        WHERE host = ? AND port = ?
        """,
        (host, port),
    ).fetchone()
    if row and row["project_id"] != exclude_project_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Preview port {port} is already allocated.")


def _allocate_preview_port(
    connection: sqlite3.Connection,
    settings: Settings,
    requested_port: int | None,
    exclude_project_id: str | None = None,
) -> int:
    if requested_port is not None:
        _ensure_port_available(connection, settings.preview_host, requested_port, exclude_project_id)
        return requested_port

    rows = connection.execute(
        "SELECT port, project_id FROM port_allocations WHERE host = ?",
        (settings.preview_host,),
    ).fetchall()
    allocated_ports = {row["port"] for row in rows if row["project_id"] != exclude_project_id}
    for port in range(settings.preview_port_start, settings.preview_port_end + 1):
        if port not in allocated_ports:
            return port
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No preview ports are available.")


def _get_project_row(connection: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise _project_not_found(project_id)
    return row


def list_projects() -> list[ProjectRead]:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        return [_serialize_project(connection, row) for row in rows]


def create_project(payload: ProjectCreate) -> ProjectRead:
    settings = get_settings()
    normalized = _normalize_project_payload(payload.model_dump(), settings)
    project_id = f"project_{uuid.uuid4().hex[:12]}"
    allocation_id = f"port_{uuid.uuid4().hex[:12]}"
    timestamp = utc_now()

    with connect(settings) as connection:
        preview_port = _allocate_preview_port(connection, settings, normalized["preview_port"])
        preview_url = f"http://{settings.preview_host}:{preview_port}"
        try:
            connection.execute(
                """
                INSERT INTO projects (
                    id, name, slug, provider, repo_url, default_branch, tracked_branch,
                    deploy_mode, build_context_path, dockerfile_path, compose_file_path,
                    container_port, preview_host, preview_port, preview_url, health_check_path,
                    health_check_url, auto_deploy_enabled, status, current_release_id,
                    current_commit_sha, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    normalized["name"],
                    normalized["slug"],
                    normalized["provider"],
                    normalized["repo_url"],
                    normalized["default_branch"],
                    normalized["tracked_branch"],
                    normalized["deploy_mode"],
                    normalized["build_context_path"],
                    normalized["dockerfile_path"],
                    normalized["compose_file_path"],
                    normalized["container_port"],
                    settings.preview_host,
                    preview_port,
                    preview_url,
                    normalized["health_check_path"],
                    normalized["health_check_url"],
                    int(normalized["auto_deploy_enabled"]),
                    ProjectStatus.NOT_DEPLOYED.value,
                    None,
                    None,
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO port_allocations (id, project_id, host, port, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    allocation_id,
                    project_id,
                    settings.preview_host,
                    preview_port,
                    PortAllocationStatus.RESERVED.value,
                    timestamp,
                    timestamp,
                ),
            )
            _replace_project_services(connection, project_id, normalized["services"], timestamp)
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "projects.slug" in message:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project slug already exists.") from exc
            if "port_allocations.host, port_allocations.port" in message:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Preview port is already allocated.") from exc
            raise

        row = _get_project_row(connection, project_id)
        return _serialize_project(connection, row)


def get_project(project_id: str) -> ProjectRead:
    with connect() as connection:
        return _serialize_project(connection, _get_project_row(connection, project_id))


def update_project(project_id: str, payload: ProjectUpdate) -> ProjectRead:
    settings = get_settings()
    changes = payload.model_dump(exclude_unset=True)

    with connect(settings) as connection:
        existing_row = _get_project_row(connection, project_id)
        existing = row_to_dict(existing_row)
        assert existing is not None
        existing_services = _fetch_project_services(connection, existing, synthesize_single=False)

        if changes.get("status") == ProjectStatus.DISABLED.value:
            existing["status"] = ProjectStatus.DISABLED.value
        normalized = _normalize_project_payload(changes, settings, existing, existing_services)
        preview_port = _allocate_preview_port(connection, settings, normalized["preview_port"], exclude_project_id=project_id)
        preview_url = f"http://{settings.preview_host}:{preview_port}"
        project_status = ProjectStatus.DISABLED.value if changes.get("status") == "disabled" else existing["status"]
        timestamp = utc_now()

        try:
            connection.execute(
                """
                UPDATE projects
                SET name = ?, slug = ?, provider = ?, repo_url = ?, default_branch = ?, tracked_branch = ?,
                    deploy_mode = ?, build_context_path = ?, dockerfile_path = ?, compose_file_path = ?,
                    container_port = ?, preview_host = ?, preview_port = ?, preview_url = ?, health_check_path = ?,
                    health_check_url = ?, auto_deploy_enabled = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    normalized["name"],
                    normalized["slug"],
                    normalized["provider"],
                    normalized["repo_url"],
                    normalized["default_branch"],
                    normalized["tracked_branch"],
                    normalized["deploy_mode"],
                    normalized["build_context_path"],
                    normalized["dockerfile_path"],
                    normalized["compose_file_path"],
                    normalized["container_port"],
                    settings.preview_host,
                    preview_port,
                    preview_url,
                    normalized["health_check_path"],
                    normalized["health_check_url"],
                    int(normalized["auto_deploy_enabled"]),
                    project_status,
                    timestamp,
                    project_id,
                ),
            )
            connection.execute(
                """
                UPDATE port_allocations
                SET host = ?, port = ?, status = ?, updated_at = ?
                WHERE project_id = ?
                """,
                (
                    settings.preview_host,
                    preview_port,
                    PortAllocationStatus.RESERVED.value if not existing["current_release_id"] else PortAllocationStatus.ACTIVE.value,
                    timestamp,
                    project_id,
                ),
            )
            _replace_project_services(connection, project_id, normalized["services"], timestamp)
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "projects.slug" in message:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project slug already exists.") from exc
            if "port_allocations.host, port_allocations.port" in message:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Preview port is already allocated.") from exc
            raise

        return _serialize_project(connection, _get_project_row(connection, project_id))


def delete_project(project_id: str) -> None:
    with connect() as connection:
        _get_project_row(connection, project_id)
        connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
