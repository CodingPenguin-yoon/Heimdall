from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256

from fastapi import HTTPException, status

from ..config import Settings, get_settings
from ..db import DBConnection, connect, row_to_dict
from ..validation import ENV_NAME_PATTERN, bad_request
from . import project_database_secrets

MAX_ENV_BUNDLE_BYTES = 64 * 1024
ENV_BUNDLE_REF_PREFIX = "env-bundles/"
UTC = timezone.utc


class EnvBundleError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedEnvBundle:
    key_names: list[str]
    checksum_sha256: str
    normalized_content: str


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_newlines(content: str) -> str:
    return content.replace("\r\n", "\n").replace("\r", "\n")


def parse_env_bundle_content(content: str) -> ParsedEnvBundle:
    if len(content.encode("utf-8")) > MAX_ENV_BUNDLE_BYTES:
        raise EnvBundleError("Env bundle file must be 64 KiB or smaller.")
    if "\x00" in content:
        raise EnvBundleError("Env bundle file cannot contain NUL bytes.")

    normalized = _normalize_newlines(content)
    output_lines: list[str] = []
    key_names: list[str] = []
    seen: set[str] = set()

    for line_number, raw_line in enumerate(normalized.split("\n"), start=1):
        if raw_line == "" or raw_line.strip() == "":
            output_lines.append("")
            continue
        if raw_line.lstrip().startswith("#"):
            output_lines.append(raw_line.lstrip())
            continue

        line = raw_line
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            raise EnvBundleError(f"Invalid env bundle line {line_number}: expected KEY=value.")

        raw_key, value = line.split("=", 1)
        key = raw_key.strip()
        if not ENV_NAME_PATTERN.fullmatch(key):
            raise EnvBundleError(f"Invalid env bundle line {line_number}: invalid environment variable name.")
        if key in seen:
            raise EnvBundleError(f"Duplicate env bundle key '{key}' is not allowed.")

        seen.add(key)
        key_names.append(key)
        output_lines.append(f"{key}={value}")

    normalized_content = "\n".join(output_lines)
    if normalized_content and not normalized_content.endswith("\n"):
        normalized_content += "\n"
    return ParsedEnvBundle(
        key_names=key_names,
        checksum_sha256=sha256(normalized_content.encode("utf-8")).hexdigest(),
        normalized_content=normalized_content,
    )


def current_env_bundle_ref(project_id: str, service_id: str) -> str:
    return f"env-bundles/projects/{project_id}/services/{service_id}/current.env"


def version_env_bundle_ref(project_id: str, service_id: str, bundle_id: str) -> str:
    return f"env-bundles/projects/{project_id}/services/{service_id}/versions/{bundle_id}.env"


def _require_env_bundle_ref(ref: str) -> str:
    if not ref.startswith(ENV_BUNDLE_REF_PREFIX):
        raise EnvBundleError("Env bundle ref must be under env-bundles.")
    return ref


def resolve_env_bundle_path(settings: Settings, ref: str):
    return project_database_secrets.resolve_secret_path(settings, _require_env_bundle_ref(ref))


def resolve_existing_env_bundle_path(settings: Settings, ref: str):
    path = resolve_env_bundle_path(settings, ref)
    if not path.is_file():
        raise EnvBundleError("Configured env bundle file is missing.")
    base = settings.secrets_dir.resolve(strict=True)
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise EnvBundleError("Configured env bundle file escapes the secrets directory.") from exc
    return path


def store_env_bundle_file(
    settings: Settings,
    *,
    project_id: str,
    service_id: str,
    bundle_id: str,
    content: str,
) -> ParsedEnvBundle:
    parsed = parse_env_bundle_content(content)
    current_ref = current_env_bundle_ref(project_id, service_id)
    version_ref = version_env_bundle_ref(project_id, service_id, bundle_id)
    project_database_secrets.write_secret(settings, version_ref, parsed.normalized_content)
    project_database_secrets.write_secret(settings, current_ref, parsed.normalized_content)
    return parsed


def _delete_ref(settings: Settings, ref: str) -> None:
    project_database_secrets.delete_secret(settings, _require_env_bundle_ref(ref))


def delete_env_bundle_files(
    settings: Settings,
    *,
    project_id: str,
    service_id: str,
    active_ref: str | None = None,
) -> None:
    refs = {current_env_bundle_ref(project_id, service_id)}
    if active_ref:
        refs.add(active_ref)
    for ref in refs:
        _delete_ref(settings, ref)

    versions_ref = f"env-bundles/projects/{project_id}/services/{service_id}/versions"
    versions_dir = resolve_env_bundle_path(settings, versions_ref)
    if not versions_dir.exists():
        return
    if versions_dir.is_symlink() or not versions_dir.is_dir():
        raise EnvBundleError("Env bundle versions path is not a directory.")
    for child in versions_dir.iterdir():
        if child.is_symlink() or not child.is_file():
            raise EnvBundleError("Env bundle versions directory contains an unsafe entry.")
        child.unlink()


def _fetch_project(connection: DBConnection, project_id: str) -> dict[str, object]:
    row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    data = row_to_dict(row)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' was not found.")
    return data


def _fetch_service(connection: DBConnection, project_id: str, service_id: str) -> dict[str, object]:
    _fetch_project(connection, project_id)
    row = connection.execute(
        "SELECT * FROM project_services WHERE project_id = ? AND id = ?",
        (project_id, service_id),
    ).fetchone()
    data = row_to_dict(row)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' was not found for project '{project_id}'.",
        )
    return data


def _read_bundle_row(connection: DBConnection, project_id: str, service_id: str) -> dict[str, object] | None:
    row = connection.execute(
        """
        SELECT *
        FROM project_service_env_bundles
        WHERE project_id = ? AND service_id = ?
        """,
        (project_id, service_id),
    ).fetchone()
    return row_to_dict(row)


def _empty_read(project_id: str, service_id: str) -> dict[str, object]:
    return {
        "id": None,
        "project_id": project_id,
        "service_id": service_id,
        "configured": False,
        "key_names": [],
        "checksum_sha256": None,
        "updated_at": None,
    }


def _bundle_read(row: dict[str, object] | None, project_id: str, service_id: str) -> dict[str, object]:
    if row is None:
        return _empty_read(project_id, service_id)
    try:
        key_names = json.loads(str(row["key_names_json"] or "[]"))
    except json.JSONDecodeError:
        key_names = []
    return {
        "id": str(row["id"]),
        "project_id": str(row["project_id"]),
        "service_id": str(row["service_id"]),
        "configured": True,
        "key_names": [str(key) for key in key_names if isinstance(key, str)],
        "checksum_sha256": str(row["checksum_sha256"]),
        "updated_at": str(row["updated_at"]),
    }


def get_service_env_bundle(project_id: str, service_id: str, settings: Settings | None = None) -> dict[str, object]:
    active_settings = settings or get_settings()
    with connect(active_settings) as connection:
        _fetch_service(connection, project_id, service_id)
        return _bundle_read(_read_bundle_row(connection, project_id, service_id), project_id, service_id)


def upsert_service_env_bundle(
    project_id: str,
    service_id: str,
    content: str,
    settings: Settings | None = None,
) -> dict[str, object]:
    active_settings = settings or get_settings()
    bundle_id = f"envbundle_{uuid.uuid4().hex[:12]}"
    with connect(active_settings) as connection:
        _fetch_service(connection, project_id, service_id)

    try:
        parsed = store_env_bundle_file(
            active_settings,
            project_id=project_id,
            service_id=service_id,
            bundle_id=bundle_id,
            content=content,
        )
    except (EnvBundleError, project_database_secrets.SecretRefError) as exc:
        raise bad_request(str(exc)) from exc

    timestamp = utc_now()
    active_ref = current_env_bundle_ref(project_id, service_id)
    with connect(active_settings) as connection:
        _fetch_service(connection, project_id, service_id)
        connection.execute(
            """
            INSERT INTO project_service_env_bundles (
                id, project_id, service_id, active_ref, key_names_json,
                checksum_sha256, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, service_id) DO UPDATE SET
                id = excluded.id,
                active_ref = excluded.active_ref,
                key_names_json = excluded.key_names_json,
                checksum_sha256 = excluded.checksum_sha256,
                updated_at = excluded.updated_at
            """,
            (
                bundle_id,
                project_id,
                service_id,
                active_ref,
                json.dumps(parsed.key_names),
                parsed.checksum_sha256,
                timestamp,
                timestamp,
            ),
        )
        row = _read_bundle_row(connection, project_id, service_id)
        return _bundle_read(row, project_id, service_id)


def delete_service_env_bundle(
    project_id: str,
    service_id: str,
    settings: Settings | None = None,
) -> None:
    active_settings = settings or get_settings()
    with connect(active_settings) as connection:
        _fetch_service(connection, project_id, service_id)
        row = _read_bundle_row(connection, project_id, service_id)
    try:
        delete_env_bundle_files(
            active_settings,
            project_id=project_id,
            service_id=service_id,
            active_ref=str(row["active_ref"]) if row else None,
        )
    except (EnvBundleError, project_database_secrets.SecretRefError) as exc:
        raise bad_request(str(exc)) from exc
    with connect(active_settings) as connection:
        connection.execute(
            """
            DELETE FROM project_service_env_bundles
            WHERE project_id = ? AND service_id = ?
            """,
            (project_id, service_id),
        )


def fetch_executor_env_bundle(
    connection: DBConnection,
    *,
    project_id: str,
    service_id: str,
) -> dict[str, object] | None:
    row = _read_bundle_row(connection, project_id, service_id)
    if row is None:
        return None
    try:
        key_names = json.loads(str(row["key_names_json"] or "[]"))
    except json.JSONDecodeError:
        key_names = []
    return {
        "active_ref": str(row["active_ref"]),
        "key_names": [str(key) for key in key_names if isinstance(key, str)],
        "checksum_sha256": str(row["checksum_sha256"]),
    }
