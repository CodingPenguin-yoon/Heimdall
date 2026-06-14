from __future__ import annotations

from urllib.parse import quote

from fastapi import HTTPException, status

from ..config import Settings
from . import project_database_secrets


RESERVED_DOCKER_NETWORKS = {"heimdall-control"}


def validate_project_database_network(network_name: str) -> str:
    normalized = network_name.strip()
    if not normalized:
        raise ValueError("HEIMDALL_PROJECT_DATABASE_NETWORK must not be blank.")
    if normalized in RESERVED_DOCKER_NETWORKS:
        raise ValueError(f"HEIMDALL_PROJECT_DATABASE_NETWORK cannot use reserved Docker network '{normalized}'.")
    return normalized


def _database_url(*, role_name: str, password: str, app_host: str, app_port: int, database_name: str) -> str:
    return (
        f"postgresql://{quote(role_name, safe='')}:{quote(password, safe='')}"
        f"@{app_host}:{app_port}/{quote(database_name, safe='')}"
    )


def _bound_service(
    services: list[dict[str, object]],
    *,
    service_id: str | None,
) -> dict[str, object] | None:
    if service_id:
        for service in services:
            if str(service.get("id") or "") == service_id:
                return service
        return None

    if len(services) == 1:
        return services[0]
    for service in services:
        if str(service.get("name") or "") == "app":
            return service
    return None


def apply_managed_database_runtime(
    connection,
    *,
    settings: Settings,
    project: dict[str, object],
    services: list[dict[str, object]],
) -> list[str]:
    rows = connection.execute(
        """
        SELECT
            project_databases.id,
            project_databases.database_name,
            project_databases.role_name,
            project_databases.password_secret_ref,
            project_databases.app_host,
            project_databases.app_port,
            project_databases.network_name,
            project_databases.status,
            project_database_bindings.service_id,
            project_database_bindings.env_var_name
        FROM project_database_bindings
        JOIN project_databases ON project_databases.id = project_database_bindings.project_database_id
        WHERE project_database_bindings.project_id = ?
        ORDER BY project_database_bindings.created_at ASC
        """,
        (project["id"],),
    ).fetchall()
    if not rows:
        return []

    redactions: list[str] = []
    passwords_by_ref: dict[str, str] = {}
    for row in rows:
        if str(row["status"]) != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Managed project database is not active.",
            )

        network_name = str(row["network_name"])
        try:
            validate_project_database_network(network_name)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        ref = str(row["password_secret_ref"])
        if ref not in passwords_by_ref:
            try:
                passwords_by_ref[ref] = project_database_secrets.read_secret(settings, ref)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Managed project database secret is unavailable.",
                ) from exc
        password = passwords_by_ref[ref]

        service = _bound_service(services, service_id=row["service_id"])
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Managed project database binding does not match a deployable service.",
            )

        url = _database_url(
            role_name=str(row["role_name"]),
            password=password,
            app_host=str(row["app_host"]),
            app_port=int(row["app_port"]),
            database_name=str(row["database_name"]),
        )
        managed_env = service.setdefault("managed_runtime_env", {})
        if not isinstance(managed_env, dict):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Managed project database runtime environment is invalid.",
            )
        managed_env[str(row["env_var_name"])] = url
        service["managed_database_network"] = network_name

        encoded_password = quote(password, safe="")
        redactions.extend([password, encoded_password, url])

    return redactions
