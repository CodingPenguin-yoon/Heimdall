from __future__ import annotations

import posixpath
import re
from pathlib import PurePosixPath
from urllib.parse import urlparse

from fastapi import HTTPException, status

from .config import Settings

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SERVICE_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VOLUME_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SECRET_NAME_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")
SSH_REPO_PATTERN = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+:[A-Za-z0-9._/-]+(?:\.git)?$")
SECRET_ENV_NAME_PATTERN = re.compile(
    r"(^|_)(SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE_KEY|API_KEY|ACCESS_KEY|JWT|DATABASE_URL|DB_PASSWORD|CREDENTIAL)(_|$)"
)
SECRET_VALUE_PATTERN = re.compile(
    r"(-----BEGIN|bearer\s+|secret|token|password|passwd|private[_ -]?key|api[_ -]?key|://[^/\s:@]+:[^@\s]+@)",
    re.IGNORECASE,
)
SERVER_ONLY_ENV_NAMES = {
    "DOCKER_CERT_PATH",
    "DOCKER_CONFIG",
    "DOCKER_CONTEXT",
    "DOCKER_HOST",
    "DOCKER_TLS_VERIFY",
    "HEIMDALL_CHILD_ROOT_CONTAINER",
    "HEIMDALL_CHILD_ROOT_HOST",
    "HEIMDALL_CHILD_RUNNER_ENABLED",
    "HEIMDALL_DATABASE_URL",
    "HEIMDALL_REPO_ROOT",
    "HEIMDALL_RUNTIME_DIR",
    "HEIMDALL_VOLUME_ROOT_CONTAINER",
    "HEIMDALL_VOLUME_ROOT_HOST",
}
SERVER_ONLY_ENV_NAME_PREFIXES = ("HEIMDALL_CHILD_", "HEIMDALL_VOLUME_ROOT_")
SERVER_ONLY_ENV_VALUE_PATTERN = re.compile(
    r"(docker\.sock|/var/run/docker\.sock|/var/lib/heimdall|/host/children|/host/project-volumes|HEIMDALL_CHILD_|HEIMDALL_VOLUME_ROOT_)",
    re.IGNORECASE,
)


def bad_request(message: str, code: int = status.HTTP_422_UNPROCESSABLE_ENTITY) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


def slugify(value: str) -> str:
    candidate = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not candidate:
        raise bad_request("Unable to derive a slug from the provided name.")
    return candidate


def validate_slug(slug: str) -> str:
    normalized = slug.strip().lower()
    if not SLUG_PATTERN.fullmatch(normalized):
        raise bad_request("Slug must contain lowercase letters, digits, and single hyphens only.")
    if len(normalized) < 2 or len(normalized) > 63:
        raise bad_request("Slug must be between 2 and 63 characters.")
    return normalized


def normalize_repo_url(repo_url: str) -> str:
    repo_url = repo_url.strip()
    if repo_url.startswith("git@"):
        _, remainder = repo_url.split("@", 1)
        host, path = remainder.split(":", 1)
        return f"{host.lower()}/{path.removesuffix('.git').strip('/')}"

    parsed = urlparse(repo_url)
    path = parsed.path.removesuffix(".git").strip("/")
    host = (parsed.hostname or "").lower()
    return f"{host}/{path}".strip("/")


def validate_repo_url(repo_url: str) -> str:
    repo_url = repo_url.strip()
    if repo_url.startswith("git@"):
        if not SSH_REPO_PATTERN.fullmatch(repo_url):
            raise bad_request("SSH repository URLs must look like git@host:owner/repo.git")
        if ".." in repo_url.split(":")[-1].split("/"):
            raise bad_request("Repository URL path cannot contain path traversal.")
        return repo_url

    parsed = urlparse(repo_url)
    if parsed.scheme not in {"http", "https", "ssh"}:
        raise bad_request("Repository URL must use https://, http://, ssh://, or git@host:path syntax.")
    if not parsed.hostname:
        raise bad_request("Repository URL must include a host.")
    if parsed.username or parsed.password:
        raise bad_request("Embedded repository credentials are not allowed.")
    if parsed.query or parsed.fragment:
        raise bad_request("Repository URL query strings and fragments are not allowed.")
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        raise bad_request("Repository URL must include an owner and repository path.")
    if ".." in path_parts:
        raise bad_request("Repository URL path cannot contain path traversal.")
    return repo_url


def validate_relative_path(value: str, field_name: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise bad_request(f"{field_name} is required.")
    if "\\" in candidate:
        raise bad_request(f"{field_name} must use forward slashes only.")
    path = PurePosixPath(candidate)
    if path.is_absolute():
        raise bad_request(f"{field_name} must be relative to the repository root.")
    if any(part == ".." for part in path.parts):
        raise bad_request(f"{field_name} cannot contain path traversal.")
    if any(part == "" for part in path.parts):
        raise bad_request(f"{field_name} cannot contain empty path segments.")
    return "." if candidate == "." else path.as_posix()


def validate_container_port(port: int) -> int:
    if port < 1 or port > 65535:
        raise bad_request("Container port must be between 1 and 65535.")
    return port


def validate_service_name(name: str) -> str:
    normalized = name.strip().lower()
    if not SERVICE_NAME_PATTERN.fullmatch(normalized):
        raise bad_request("Service name must contain lowercase letters, digits, and single hyphens only.")
    if len(normalized) > 63:
        raise bad_request("Service name must be 63 characters or fewer.")
    return normalized


def validate_volume_name(name: str) -> str:
    normalized = name.strip().lower()
    if not normalized:
        raise bad_request("Volume name is required.")
    if "/" in normalized or normalized in {".", ".."}:
        raise bad_request("Volume name must be a DNS-style label, not a path.")
    if not VOLUME_NAME_PATTERN.fullmatch(normalized):
        raise bad_request("Volume name must contain lowercase letters, digits, and single hyphens only.")
    if len(normalized) > 63:
        raise bad_request("Volume name must be 63 characters or fewer.")
    return normalized


def _path_equal_or_under(path: str, reserved_path: str) -> bool:
    return path == reserved_path or path.startswith(f"{reserved_path.rstrip('/')}/")


def validate_volume_target_path(path: str) -> str:
    candidate = path.strip()
    if not candidate:
        raise bad_request("Volume target_path is required.")
    if "\\" in candidate:
        raise bad_request("Volume target_path must use forward slashes only.")
    if not candidate.startswith("/"):
        raise bad_request("Volume target_path must be an absolute POSIX path.")

    raw_parts = [part for part in candidate.split("/") if part]
    if any(part == ".." for part in raw_parts):
        raise bad_request("Volume target_path cannot contain path traversal.")

    normalized = posixpath.normpath("/" + candidate.lstrip("/"))
    if normalized == "/":
        raise bad_request("Volume target_path cannot be '/'.")

    path_parts = PurePosixPath(normalized).parts
    if any(part == ".." for part in path_parts):
        raise bad_request("Volume target_path cannot contain path traversal.")

    reserved_paths = (
        "/var/run/docker.sock",
        "/proc",
        "/sys",
        "/dev",
        "/var/lib/docker",
        "/var/lib/heimdall",
        "/var/lib/heimdall/secrets",
        "/var/lib/heimdall/env",
    )
    for reserved_path in reserved_paths:
        if _path_equal_or_under(normalized, reserved_path):
            raise bad_request(f"Volume target_path cannot use reserved path '{reserved_path}'.")

    return normalized


def validate_service_volumes(volumes: object, field_prefix: str) -> list[dict[str, object]]:
    if volumes is None:
        return []
    if not isinstance(volumes, list):
        raise bad_request(f"{field_prefix}.volumes must be a list.")

    normalized_volumes: list[dict[str, object]] = []
    seen_names: set[str] = set()
    seen_targets: set[str] = set()
    for index, raw_volume in enumerate(volumes):
        if hasattr(raw_volume, "model_dump"):
            raw_data = raw_volume.model_dump()
        elif isinstance(raw_volume, dict):
            raw_data = raw_volume
        else:
            raise bad_request(f"{field_prefix}.volumes[{index}] must be an object.")

        name = validate_volume_name(str(raw_data.get("name", "")))
        if name in seen_names:
            raise bad_request(f"Duplicate volume name '{name}' is not allowed for {field_prefix}.")
        seen_names.add(name)

        target_path = validate_volume_target_path(str(raw_data.get("target_path", "")))
        if target_path in seen_targets:
            raise bad_request(f"Duplicate volume target_path '{target_path}' is not allowed for {field_prefix}.")
        seen_targets.add(target_path)

        normalized_volumes.append(
            {
                "name": name,
                "target_path": target_path,
                "read_only": bool(raw_data.get("read_only", False)),
            }
        )

    return normalized_volumes


def validate_env_map(values: dict[str, str], field_name: str) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in values.items():
        key = str(raw_key).strip()
        value = str(raw_value)
        if not ENV_NAME_PATTERN.fullmatch(key):
            raise bad_request(f"{field_name} contains invalid environment variable name '{key}'.")
        if key in SERVER_ONLY_ENV_NAMES or key.startswith(SERVER_ONLY_ENV_NAME_PREFIXES):
            raise bad_request(f"{field_name}.{key} is reserved for Heimdall server configuration.")
        if SECRET_ENV_NAME_PATTERN.search(key):
            raise bad_request(f"{field_name}.{key} looks secret; store secret names in required_secrets instead.")
        if "\n" in value or "\r" in value:
            raise bad_request(f"{field_name}.{key} cannot contain multiline or raw .env values.")
        if SERVER_ONLY_ENV_VALUE_PATTERN.search(value):
            raise bad_request(f"{field_name}.{key} contains a reserved Heimdall or Docker socket value.")
        if SECRET_VALUE_PATTERN.search(value):
            raise bad_request(f"{field_name}.{key} looks like a secret value and cannot be stored.")
        normalized[key] = value
    return normalized


def validate_required_secrets(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        secret_name = str(raw_value).strip()
        if not SECRET_NAME_PATTERN.fullmatch(secret_name):
            raise bad_request("Required secret names must use uppercase environment variable syntax.")
        if secret_name in seen:
            raise bad_request(f"Duplicate required secret name '{secret_name}' is not allowed.")
        seen.add(secret_name)
        normalized.append(secret_name)
    return normalized


def validate_preview_port(port: int, settings: Settings) -> int:
    if port < settings.preview_port_start or port > settings.preview_port_end:
        raise bad_request(
            f"Preview port must be between {settings.preview_port_start} and {settings.preview_port_end}."
        )
    return port


def validate_health_check(path_value: str | None, url_value: str | None) -> tuple[str | None, str | None]:
    if path_value and url_value:
        raise bad_request("Provide either health_check_path or health_check_url, not both.")
    if path_value:
        candidate = path_value.strip()
        if not candidate.startswith("/"):
            raise bad_request("Health check path must start with '/'.")
        parsed = urlparse(candidate)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise bad_request("Health check path must be a plain HTTP path.")
        if ".." in PurePosixPath(parsed.path).parts:
            raise bad_request("Health check path cannot contain path traversal.")
        return candidate, None
    if url_value:
        candidate = url_value.strip()
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise bad_request("Health check URL must use http:// or https:// and include a host.")
        if parsed.username or parsed.password:
            raise bad_request("Embedded credentials are not allowed in the health check URL.")
        if parsed.query or parsed.fragment:
            raise bad_request("Health check URL must not include query strings or fragments.")
        if ".." in PurePosixPath(parsed.path or "/").parts:
            raise bad_request("Health check URL path cannot contain path traversal.")
        return None, candidate
    return None, None


def branch_from_ref(ref: str | None) -> str | None:
    if not ref:
        return None
    if ref.startswith("refs/heads/"):
        return ref.removeprefix("refs/heads/")
    return ref
