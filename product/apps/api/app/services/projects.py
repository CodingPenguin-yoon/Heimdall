from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum

from fastapi import HTTPException, status

from ..config import Settings, get_settings
from ..db import (
    DATABASE_INTEGRITY_ERRORS,
    DBConnection,
    DBRow,
    connect,
    is_unique_constraint_violation,
    row_to_dict,
)
from ..models import ACTIVE_DEPLOYMENT_STATUSES, DeployMode, PortAllocationStatus, ProjectStatus
from ..schemas import (
    ProjectCreate,
    ProjectDatabasePurgeRequest,
    ProjectDatabaseRead,
    ProjectRead,
    ProjectServiceRead,
    ProjectUpdate,
    WebhookRegistrationRead,
)
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
    validate_service_volumes,
    validate_slug,
)
from . import project_database_secrets, project_databases

UTC = timezone.utc


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _as_bool(value: object) -> bool:
    return bool(int(value)) if value is not None else False


def _project_not_found(project_id: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' was not found.")


def _project_conflict_exception(exc: BaseException) -> HTTPException | None:
    if is_unique_constraint_violation(
        exc,
        constraint_names={"projects_slug_unique"},
        sqlite_fragments={"projects.slug"},
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project slug already exists.")
    if is_unique_constraint_violation(
        exc,
        constraint_names={"port_allocations_host_port_unique"},
        sqlite_fragments={"port_allocations.host, port_allocations.port"},
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Preview port is already allocated.")
    return None


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


def _project_database_identifier(project_id: str, suffix: str) -> str:
    stem = "".join(char if char.isalnum() or char == "_" else "_" for char in project_id.lower())
    candidate = f"hm_{stem}_{suffix}"
    if len(candidate) <= 63:
        return candidate

    digest = uuid.uuid5(uuid.NAMESPACE_URL, project_id).hex[:12]
    prefix_length = 63 - len("hm__") - len(digest) - len(suffix)
    return f"hm_{stem[:prefix_length]}_{digest}_{suffix}"


def _normalize_project_database_config(raw_database: object) -> dict[str, object] | None:
    if raw_database is None:
        return None
    if hasattr(raw_database, "model_dump"):
        raw_data = raw_database.model_dump()
    elif isinstance(raw_database, dict):
        raw_data = raw_database
    else:
        raise bad_request("database must be an object.")

    database_type = str(raw_data.get("type") or "postgres")
    if database_type != "postgres":
        raise bad_request("database.type must be 'postgres'.")
    env_var = validate_required_secrets([str(raw_data.get("env_var") or "DATABASE_URL").strip()])[0]
    return {
        "required": bool(raw_data.get("required", False)),
        "type": database_type,
        "env_var": env_var,
    }


def _require_project_database_settings_if_needed(
    settings: Settings,
    database_config: dict[str, object] | None,
) -> None:
    if not database_config or not bool(database_config["required"]):
        return
    try:
        settings.require_project_database_settings()
    except ValueError as exc:
        raise bad_request(str(exc)) from exc


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
        "volumes": [],
    }


def _normalize_service_payloads(
    raw_services: object,
    existing_services_by_name: dict[str, dict[str, object]] | None = None,
) -> list[dict[str, object]]:
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
        if "volumes" in raw_service and raw_service.get("volumes") is not None:
            volumes = validate_service_volumes(raw_service.get("volumes"), f"services.{name}")
        elif existing_services_by_name and name in existing_services_by_name:
            volumes = validate_service_volumes(existing_services_by_name[name].get("volumes"), f"services.{name}")
        else:
            volumes = []

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
                "volumes": volumes,
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
        if payload.get("volumes") is not None:
            raise bad_request("Top-level volumes are only supported for dockerfile deploy mode.")
        raw_services = payload.get("services", existing_services)
        existing_services_by_name = {str(service["name"]): service for service in existing_services or []}
        services = _normalize_service_payloads(raw_services, existing_services_by_name)
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
        existing_app_service = next(
            (service for service in existing_services or [] if str(service.get("name")) == "app"),
            None,
        )
        if "volumes" in payload and payload.get("volumes") is not None:
            volumes = validate_service_volumes(payload.get("volumes"), "volumes")
        elif existing_app_service:
            volumes = validate_service_volumes(existing_app_service.get("volumes"), "volumes")
        else:
            volumes = []
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
                "volumes": volumes,
            }
        ]
    auto_deploy_enabled = payload.get("auto_deploy_enabled", existing["auto_deploy_enabled"] if existing else False)

    normalized = {
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
        "database": _normalize_project_database_config(payload.get("database")),
    }
    return normalized


def _fetch_latest_deployment(connection: DBConnection, project_id: str) -> dict[str, object] | None:
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
    connection: DBConnection,
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
        service_id = str(data["id"])
        services.append(
            {
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
                "volumes": _fetch_service_volumes(connection, str(project["id"]), service_id),
            }
        )
    if services:
        return services
    if synthesize_single and str(project["deploy_mode"]) == DeployMode.DOCKERFILE.value:
        return [_single_service_from_project(project)]
    return []


def _fetch_service_volumes(
    connection: DBConnection,
    project_id: str,
    service_id: str,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT id, name, target_path, read_only, source_relative_path, status
        FROM project_service_volumes
        WHERE project_id = ? AND service_id = ?
        ORDER BY name ASC
        """,
        (project_id, service_id),
    ).fetchall()
    volumes: list[dict[str, object]] = []
    for row in rows:
        data = row_to_dict(row)
        assert data is not None
        volumes.append(
            {
                "id": str(data["id"]),
                "name": str(data["name"]),
                "target_path": str(data["target_path"]),
                "read_only": _as_bool(data["read_only"]),
                "source_relative_path": str(data["source_relative_path"]),
                "status": str(data["status"]),
            }
        )
    return volumes


def _replace_service_volumes(
    connection: DBConnection,
    project_id: str,
    service_id: str,
    service_name: str,
    volumes: list[dict[str, object]],
    timestamp: str,
) -> None:
    rows = connection.execute(
        """
        SELECT *
        FROM project_service_volumes
        WHERE project_id = ? AND service_id = ?
        """,
        (project_id, service_id),
    ).fetchall()
    existing_by_name = {str(row["name"]): row_to_dict(row) for row in rows}
    retained_names: set[str] = set()

    for volume in volumes:
        name = str(volume["name"])
        retained_names.add(name)
        existing = existing_by_name.get(name)
        if existing:
            connection.execute(
                """
                UPDATE project_service_volumes
                SET service_display_name_snapshot = ?, target_path = ?, read_only = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    service_name,
                    volume["target_path"],
                    int(bool(volume["read_only"])),
                    str(existing["status"] or "active"),
                    timestamp,
                    existing["id"],
                ),
            )
            continue

        volume_id = f"volume_{uuid.uuid4().hex[:12]}"
        connection.execute(
            """
            INSERT INTO project_service_volumes (
                id, project_id, service_id, service_display_name_snapshot, name, target_path,
                read_only, source_relative_path, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                volume_id,
                project_id,
                service_id,
                service_name,
                name,
                volume["target_path"],
                int(bool(volume["read_only"])),
                f"{project_id}/{service_id}/{volume_id}",
                "active",
                timestamp,
                timestamp,
            ),
        )

    for name, existing in existing_by_name.items():
        if name not in retained_names:
            connection.execute("DELETE FROM project_service_volumes WHERE id = ?", (existing["id"],))


def _upsert_project_services(
    connection: DBConnection,
    project_id: str,
    services: list[dict[str, object]],
    timestamp: str,
) -> None:
    rows = connection.execute(
        """
        SELECT *
        FROM project_services
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchall()
    existing_by_name = {str(row["name"]): row_to_dict(row) for row in rows}
    retained_service_ids: set[str] = set()

    for service in services:
        service_name = str(service["name"])
        existing = existing_by_name.get(service_name)
        if existing:
            service_id = str(existing["id"])
            connection.execute(
                """
                UPDATE project_services
                SET build_context_path = ?, dockerfile_path = ?, container_port = ?, is_public = ?,
                    health_check_path = ?, startup_order = ?, build_env_json = ?, runtime_env_json = ?,
                    required_secrets_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
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
                    service_id,
                ),
            )
        else:
            service_id = f"service_{uuid.uuid4().hex[:12]}"
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
                    service_id,
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

        retained_service_ids.add(service_id)
        _replace_service_volumes(
            connection,
            project_id,
            service_id,
            service_name,
            service.get("volumes") or [],
            timestamp,
        )

    for existing in existing_by_name.values():
        service_id = str(existing["id"])
        if service_id not in retained_service_ids:
            connection.execute(
                "DELETE FROM project_service_volumes WHERE project_id = ? AND service_id = ?",
                (project_id, service_id),
            )
            connection.execute(
                "DELETE FROM project_services WHERE project_id = ? AND id = ?",
                (project_id, service_id),
            )


def _fetch_project_database(connection: DBConnection, project_id: str) -> dict[str, object] | None:
    row = connection.execute(
        """
        SELECT *
        FROM project_databases
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    return row_to_dict(row)


def _fetch_project_database_for_purge(
    connection: DBConnection,
    project_id: str,
    database_id: str,
) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT *
        FROM project_databases
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    data = row_to_dict(row)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project database metadata was not found.")
    if str(data["id"]) != database_id:
        raise bad_request("database_id does not match the managed project database.")
    return data


def _project_database_env_var(connection: DBConnection, project_database_id: str) -> str:
    row = connection.execute(
        """
        SELECT env_var_name
        FROM project_database_bindings
        WHERE project_database_id = ?
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (project_database_id,),
    ).fetchone()
    data = row_to_dict(row)
    if data is None:
        return "DATABASE_URL"
    return str(data["env_var_name"])


def _database_binding_services(
    services: list[dict[str, object]],
    deploy_mode: str,
    env_var: str,
) -> list[tuple[str | None, str | None]]:
    if deploy_mode == DeployMode.MULTI_SERVICE_DOCKERFILE.value:
        return [
            (str(service["id"]), env_var)
            for service in services
            if env_var in [str(item) for item in service.get("required_secrets", [])]
        ]

    for service in services:
        if str(service["name"]) == "app":
            required_secret_name = (
                env_var if env_var in [str(item) for item in service.get("required_secrets", [])] else None
            )
            return [(str(service["id"]), required_secret_name)]
    return [(None, None)]


def _replace_project_database_bindings(
    connection: DBConnection,
    project_database_id: str,
    project_id: str,
    services: list[dict[str, object]],
    deploy_mode: str,
    env_var: str,
    timestamp: str,
) -> None:
    connection.execute("DELETE FROM project_database_bindings WHERE project_database_id = ?", (project_database_id,))
    for service_id, required_secret_name in _database_binding_services(services, deploy_mode, env_var):
        connection.execute(
            """
            INSERT INTO project_database_bindings (
                id, project_database_id, project_id, service_id, env_var_name,
                required_secret_name, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"pdbind_{uuid.uuid4().hex[:12]}",
                project_database_id,
                project_id,
                service_id,
                env_var,
                required_secret_name,
                timestamp,
                timestamp,
            ),
        )


def _refresh_project_database_bindings(
    connection: DBConnection,
    project_id: str,
    deploy_mode: str,
    env_var: str,
    timestamp: str,
) -> None:
    existing = _fetch_project_database(connection, project_id)
    if not existing:
        return
    services = _fetch_project_services(
        connection,
        {"id": project_id, "deploy_mode": deploy_mode},
        synthesize_single=False,
    )
    _replace_project_database_bindings(
        connection,
        str(existing["id"]),
        project_id,
        services,
        deploy_mode,
        env_var,
        timestamp,
    )


def _sync_project_database_metadata(
    connection: DBConnection,
    project_id: str,
    deploy_mode: str,
    settings: Settings,
    database_config: dict[str, object] | None,
    timestamp: str,
) -> None:
    if database_config is None:
        return

    existing = _fetch_project_database(connection, project_id)
    if not bool(database_config["required"]):
        if not existing:
            return
        if str(existing["status"]) == "purged":
            return
        has_secret = project_database_secrets.secret_exists(settings, str(existing["password_secret_ref"]))
        has_attempt = bool(existing["provisioned_at"] or existing["last_error"] or has_secret)
        if str(existing["status"]) == "pending" and not has_attempt:
            connection.execute("DELETE FROM project_database_bindings WHERE project_database_id = ?", (existing["id"],))
            connection.execute("DELETE FROM project_databases WHERE id = ?", (existing["id"],))
        else:
            connection.execute("DELETE FROM project_database_bindings WHERE project_database_id = ?", (existing["id"],))
            connection.execute(
                """
                UPDATE project_databases
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                ("disabled", timestamp, existing["id"]),
            )
        return

    _, app_host, app_port, network = settings.require_project_database_settings()
    database_name = _project_database_identifier(project_id, "db")
    role_name = _project_database_identifier(project_id, "role")
    password_secret_ref = f"project-databases/{project_id}/password"
    retention_policy = str(existing["retention_policy"]) if existing and existing.get("retention_policy") else "retain"
    project_database_id = str(existing["id"]) if existing else f"pdb_{uuid.uuid4().hex[:12]}"

    if existing:
        existing_status = str(existing["status"])
        if existing_status == "purged":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Purged managed project database metadata cannot be re-enabled.",
            )
        status_value = "pending" if existing_status in {"disabled", "orphaned"} else existing_status
        connection.execute(
            """
            UPDATE project_databases
            SET database_name = ?, role_name = ?, password_secret_ref = ?, app_host = ?,
                app_port = ?, network_name = ?, status = ?, retention_policy = ?, orphaned_at = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (
                database_name,
                role_name,
                password_secret_ref,
                app_host,
                app_port,
                network,
                status_value,
                retention_policy,
                timestamp,
                project_database_id,
            ),
        )
    else:
        connection.execute(
            """
            INSERT INTO project_databases (
                id, project_id, database_name, role_name, password_secret_ref, app_host,
                app_port, network_name, status, retention_policy, orphaned_at, created_at,
                updated_at, provisioned_at, last_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_database_id,
                project_id,
                database_name,
                role_name,
                password_secret_ref,
                app_host,
                app_port,
                network,
                "pending",
                retention_policy,
                None,
                timestamp,
                timestamp,
                None,
                None,
            ),
        )

    services = _fetch_project_services(
        connection,
        {"id": project_id, "deploy_mode": deploy_mode},
        synthesize_single=False,
    )
    _replace_project_database_bindings(
        connection,
        project_database_id,
        project_id,
        services,
        deploy_mode,
        str(database_config["env_var"]),
        timestamp,
    )


def _require_volume_roots_if_needed(settings: Settings, services: list[dict[str, object]]) -> None:
    if not any(service.get("volumes") for service in services):
        return
    try:
        settings.require_volume_roots()
    except ValueError as exc:
        raise bad_request(str(exc)) from exc


def _fetch_webhook_registration(connection: DBConnection, project_id: str) -> WebhookRegistrationRead | None:
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


def _serialize_project_database_read(connection: DBConnection, data: dict[str, object]) -> ProjectDatabaseRead:
    return ProjectDatabaseRead(
        id=str(data["id"]),
        required=str(data["status"]) != "disabled",
        type="postgres",
        env_var=_project_database_env_var(connection, str(data["id"])),
        status=str(data["status"]),
        app_host=str(data["app_host"]),
        app_port=int(data["app_port"]),
        network_name=str(data["network_name"]),
        retention_policy=str(data["retention_policy"]),
        orphaned_at=data["orphaned_at"],
        provisioned_at=data["provisioned_at"],
        last_error=data["last_error"],
    )


def _fetch_project_database_read(connection: DBConnection, project_id: str) -> ProjectDatabaseRead | None:
    data = _fetch_project_database(connection, project_id)
    if data is None:
        return None
    return _serialize_project_database_read(connection, data)


def _serialize_project(connection: DBConnection, row: DBRow) -> ProjectRead:
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
        database=_fetch_project_database_read(connection, data["id"]),
        webhook_registration=_fetch_webhook_registration(connection, data["id"]),
    )


def _ensure_port_available(
    connection: DBConnection,
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
    connection: DBConnection,
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


def _get_project_row(connection: DBConnection, project_id: str) -> DBRow:
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
    _require_volume_roots_if_needed(settings, normalized["services"])
    _require_project_database_settings_if_needed(settings, normalized["database"])
    should_provision_database = bool(normalized["database"] and normalized["database"]["required"])
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
            _upsert_project_services(connection, project_id, normalized["services"], timestamp)
            _sync_project_database_metadata(
                connection,
                project_id,
                str(normalized["deploy_mode"]),
                settings,
                normalized["database"],
                timestamp,
            )
        except DATABASE_INTEGRITY_ERRORS as exc:
            conflict = _project_conflict_exception(exc)
            if conflict is not None:
                raise conflict from exc
            raise

    if should_provision_database:
        project_databases.provision_project_database(project_id, settings=settings)
    return get_project(project_id)


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
        existing_database = _fetch_project_database(connection, project_id)

        if changes.get("status") == ProjectStatus.DISABLED.value:
            existing["status"] = ProjectStatus.DISABLED.value
        normalized = _normalize_project_payload(changes, settings, existing, existing_services)
        _require_volume_roots_if_needed(settings, normalized["services"])
        if "database" in changes:
            database_config = _normalize_project_database_config(changes["database"])
            refresh_database_bindings_only = False
        elif existing_database and str(existing_database["status"]) not in {"disabled", "orphaned", "purged"}:
            database_config = {
                "required": True,
                "type": "postgres",
                "env_var": _project_database_env_var(connection, str(existing_database["id"])),
            }
            refresh_database_bindings_only = True
        else:
            database_config = None
            refresh_database_bindings_only = False
        if not refresh_database_bindings_only:
            _require_project_database_settings_if_needed(settings, database_config)
        should_provision_database = bool("database" in changes and database_config and database_config["required"])
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
            _upsert_project_services(connection, project_id, normalized["services"], timestamp)
            if refresh_database_bindings_only and database_config:
                _refresh_project_database_bindings(
                    connection,
                    project_id,
                    str(normalized["deploy_mode"]),
                    str(database_config["env_var"]),
                    timestamp,
                )
            else:
                _sync_project_database_metadata(
                    connection,
                    project_id,
                    str(normalized["deploy_mode"]),
                    settings,
                    database_config,
                    timestamp,
                )
        except DATABASE_INTEGRITY_ERRORS as exc:
            conflict = _project_conflict_exception(exc)
            if conflict is not None:
                raise conflict from exc
            raise

    if should_provision_database:
        project_databases.provision_project_database(project_id, settings=settings)
    return get_project(project_id)


def retry_project_database(project_id: str) -> ProjectRead:
    settings = get_settings()
    try:
        settings.require_project_database_settings()
    except ValueError as exc:
        raise bad_request(str(exc)) from exc

    with connect(settings) as connection:
        _get_project_row(connection, project_id)
        row = _fetch_project_database(connection, project_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project database metadata was not found.")

    database_status = str(row["status"])
    if database_status in project_databases.BLOCKED_RETRY_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project database status '{database_status}' cannot be retried.",
        )
    if database_status not in project_databases.RETRYABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project database status '{database_status}' cannot be retried.",
        )

    project_databases.provision_project_database(project_id, settings=settings)
    return get_project(project_id)


def _ensure_no_active_database_purge_deployment(connection: DBConnection, project_id: str) -> None:
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


def purge_project_database(project_id: str, payload: ProjectDatabasePurgeRequest) -> ProjectDatabaseRead:
    settings = get_settings()
    with connect(settings) as connection:
        row = _fetch_project_database_for_purge(connection, project_id, payload.database_id)
        database_status = str(row["status"])
        if database_status == "purged":
            return _serialize_project_database_read(connection, row)
        _ensure_no_active_database_purge_deployment(connection, project_id)
        if database_status not in project_databases.PURGEABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project database status '{database_status}' cannot be purged.",
            )
        timestamp = utc_now()
        connection.execute(
            """
            UPDATE project_databases
            SET status = ?, last_error = NULL, updated_at = ?
            WHERE id = ?
            """,
            ("purging", timestamp, row["id"]),
        )
        row = {**row, "status": "purging", "last_error": None, "updated_at": timestamp}

    project_databases.purge_project_database(row, settings=settings)
    with connect(settings) as connection:
        refreshed = _fetch_project_database_for_purge(connection, project_id, payload.database_id)
        return _serialize_project_database_read(connection, refreshed)


def delete_project(project_id: str) -> None:
    with connect() as connection:
        _get_project_row(connection, project_id)
        timestamp = utc_now()
        connection.execute(
            """
            UPDATE project_databases
            SET status = ?, orphaned_at = COALESCE(orphaned_at, ?), updated_at = ?
            WHERE project_id = ? AND status NOT IN ('orphaned', 'purged')
            """,
            ("orphaned", timestamp, timestamp, project_id),
        )
        connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
