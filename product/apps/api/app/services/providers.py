from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from urllib.parse import quote, urlparse, urlunparse

import httpx
from fastapi import HTTPException, status

from ..config import Settings, get_settings
from ..db import DBRow, connect, row_to_dict
from ..models import Provider
from ..schemas import (
    ProviderReadiness,
    ProvidersStatus,
    RepoValidationRead,
    RepoValidationRequest,
    WebhookRegistrationRead,
)
from .projects import utc_now


GITHUB_API_BASE_URL = "https://api.github.com"
HTTP_TIMEOUT_SECONDS = 10.0
REPO_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class ParsedRepo:
    provider: str
    repo_url: str
    normalized_repo: str
    api_path: str
    host: str
    owner: str | None = None
    repo: str | None = None


def _provider_value(provider: Provider | str | None) -> str | None:
    if provider is None:
        return None
    if isinstance(provider, Provider):
        return provider.value
    return str(provider)


def _base_url_without_auth(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return raw_url.rstrip("/")
    host = parsed.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    return urlunparse((parsed.scheme, netloc, parsed.path.rstrip("/"), "", "", "")).rstrip("/")


def _gitlab_base_parts(settings: Settings) -> tuple[str, str, int | None]:
    if not settings.gitlab_base_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="HEIMDALL_GITLAB_BASE_URL is required for GitLab provider operations.",
        )
    parsed = urlparse(settings.gitlab_base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="HEIMDALL_GITLAB_BASE_URL must use http:// or https:// and include a host.",
        )
    return settings.gitlab_base_url.rstrip("/"), parsed.hostname.lower(), parsed.port


def _public_base_url_usable(public_base_url: str) -> tuple[bool, str]:
    parsed = urlparse(public_base_url)
    if parsed.scheme != "https":
        return False, "HEIMDALL_PUBLIC_BASE_URL must be an HTTPS URL providers can call."
    if not parsed.hostname:
        return False, "HEIMDALL_PUBLIC_BASE_URL must include a public host."

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "local"} or hostname.endswith(".localhost") or hostname.endswith(".local"):
        return False, "HEIMDALL_PUBLIC_BASE_URL points at a local host; use a public URL or tunnel."

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return True, "HEIMDALL_PUBLIC_BASE_URL appears externally usable."

    if (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_unspecified
        or address.is_reserved
        or address.is_multicast
    ):
        return False, "HEIMDALL_PUBLIC_BASE_URL points at a non-public IP address."
    return True, "HEIMDALL_PUBLIC_BASE_URL appears externally usable."


def _webhook_urls(settings: Settings) -> dict[str, str]:
    base_url = settings.public_base_url.rstrip("/")
    return {
        Provider.GITHUB.value: f"{base_url}/api/webhooks/github",
        Provider.GITLAB.value: f"{base_url}/api/webhooks/gitlab",
    }


def _readiness_message(missing: list[str]) -> str:
    if not missing:
        return "Provider configuration is ready."
    return f"Missing {', '.join(missing)}."


def get_provider_status() -> ProvidersStatus:
    settings = get_settings()
    public_usable, public_message = _public_base_url_usable(settings.public_base_url)

    github_missing = []
    if not settings.github_api_token:
        github_missing.append("GitHub API token")
    if not settings.github_webhook_secret:
        github_missing.append("GitHub webhook secret")

    gitlab_missing = []
    if not settings.gitlab_base_url:
        gitlab_missing.append("GitLab base URL")
    if not settings.gitlab_api_token:
        gitlab_missing.append("GitLab API token")
    if not settings.gitlab_webhook_secret:
        gitlab_missing.append("GitLab webhook secret")

    github_ready = not github_missing
    gitlab_ready = not gitlab_missing
    return ProvidersStatus(
        public_base_url=settings.public_base_url,
        webhook_urls=_webhook_urls(settings),
        public_base_url_usable=public_usable,
        public_base_url_message=public_message,
        providers={
            Provider.GITHUB.value: ProviderReadiness(
                provider=Provider.GITHUB.value,
                token_configured=bool(settings.github_api_token),
                webhook_secret_configured=bool(settings.github_webhook_secret),
                ready=github_ready,
                can_validate_repo=bool(settings.github_api_token),
                can_register_webhook=github_ready and public_usable,
                message=_readiness_message(github_missing),
            ),
            Provider.GITLAB.value: ProviderReadiness(
                provider=Provider.GITLAB.value,
                token_configured=bool(settings.gitlab_api_token),
                webhook_secret_configured=bool(settings.gitlab_webhook_secret),
                base_url_configured=bool(settings.gitlab_base_url),
                base_url=_base_url_without_auth(settings.gitlab_base_url),
                ready=gitlab_ready,
                can_validate_repo=bool(settings.gitlab_base_url and settings.gitlab_api_token),
                can_register_webhook=gitlab_ready and public_usable,
                message=_readiness_message(gitlab_missing),
            ),
        },
    )


def _validate_repo_segment(segment: str, provider_name: str) -> str:
    if not segment or segment in {".", ".."} or not REPO_SEGMENT_RE.fullmatch(segment):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{provider_name} repository paths may only contain letters, digits, '.', '_', and '-'.",
        )
    return segment


def _parse_github_repo_url(repo_url: str) -> ParsedRepo:
    parsed = urlparse(repo_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="GitHub repository URLs must use http:// or https://.",
        )
    if (parsed.hostname or "").lower() != "github.com":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="GitHub repository URLs must use github.com.",
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Repository URLs must not include credentials, query strings, or fragments.",
        )

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="GitHub repository URLs must look like https://github.com/owner/repo.git.",
        )
    owner = _validate_repo_segment(parts[0], "GitHub")
    repo = _validate_repo_segment(parts[1].removesuffix(".git"), "GitHub")
    api_path = f"{owner}/{repo}"
    return ParsedRepo(
        provider=Provider.GITHUB.value,
        repo_url=repo_url,
        normalized_repo=f"github.com/{api_path}",
        api_path=api_path,
        host="github.com",
        owner=owner,
        repo=repo,
    )


def _parse_gitlab_repo_url(repo_url: str, settings: Settings) -> ParsedRepo:
    _, gitlab_host, gitlab_port = _gitlab_base_parts(settings)
    parsed = urlparse(repo_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="GitLab repository URLs must use http:// or https://.",
        )
    if not parsed.hostname or parsed.hostname.lower() != gitlab_host or parsed.port != gitlab_port:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="GitLab repository URL host must match HEIMDALL_GITLAB_BASE_URL.",
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Repository URLs must not include credentials, query strings, or fragments.",
        )

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="GitLab repository URLs must include a group path and repository name.",
        )
    normalized_parts = [_validate_repo_segment(part, "GitLab") for part in parts[:-1]]
    normalized_parts.append(_validate_repo_segment(parts[-1].removesuffix(".git"), "GitLab"))
    api_path = "/".join(normalized_parts)
    normalized_host = gitlab_host if gitlab_port is None else f"{gitlab_host}:{gitlab_port}"
    return ParsedRepo(
        provider=Provider.GITLAB.value,
        repo_url=repo_url,
        normalized_repo=f"{normalized_host}/{api_path}",
        api_path=api_path,
        host=normalized_host,
    )


def parse_repo_url(repo_url: str, provider: Provider | str | None = None, settings: Settings | None = None) -> ParsedRepo:
    active_settings = settings or get_settings()
    expected_provider = _provider_value(provider)
    parsed = urlparse(repo_url.strip())
    hostname = (parsed.hostname or "").lower()

    if expected_provider == Provider.GITHUB.value or (expected_provider is None and hostname == "github.com"):
        result = _parse_github_repo_url(repo_url)
    elif expected_provider == Provider.GITLAB.value:
        result = _parse_gitlab_repo_url(repo_url, active_settings)
    elif expected_provider is None and active_settings.gitlab_base_url:
        _, gitlab_host, gitlab_port = _gitlab_base_parts(active_settings)
        if hostname == gitlab_host and parsed.port == gitlab_port:
            result = _parse_gitlab_repo_url(repo_url, active_settings)
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Repository URL host is not supported by a configured provider.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Repository URL host is not supported by a configured provider.",
        )

    if expected_provider and result.provider != expected_provider:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Repository URL does not match provider '{expected_provider}'.",
        )
    return result


def _github_headers(settings: Settings) -> dict[str, str]:
    assert settings.github_api_token is not None
    return {
        "Authorization": f"Bearer {settings.github_api_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gitlab_headers(settings: Settings) -> dict[str, str]:
    assert settings.gitlab_api_token is not None
    return {"PRIVATE-TOKEN": settings.gitlab_api_token}


def _provider_http_error(provider_name: str, response: httpx.Response, action: str) -> HTTPException:
    if response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
        return HTTPException(
            status_code=response.status_code,
            detail=f"{provider_name} token was rejected or lacks access for {action}.",
        )
    if response.status_code == status.HTTP_404_NOT_FOUND:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{provider_name} repository or project was not found, or the token lacks access.",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"{provider_name} API request failed while {action}.",
    )


def _http_get_json(url: str, headers: dict[str, str], provider_name: str, action: str) -> object:
    try:
        response = httpx.get(url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{provider_name} API request failed while {action}.",
        ) from exc

    if response.status_code >= 400:
        raise _provider_http_error(provider_name, response, action)
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{provider_name} API returned invalid JSON while {action}.",
        ) from exc


def _http_post_json(
    url: str,
    headers: dict[str, str],
    provider_name: str,
    action: str,
    payload: dict[str, object],
) -> object:
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=HTTP_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{provider_name} API request failed while {action}.",
        ) from exc

    if response.status_code >= 400:
        raise _provider_http_error(provider_name, response, action)
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{provider_name} API returned invalid JSON while {action}.",
        ) from exc


def _registration_capability(settings: Settings, provider: str) -> bool:
    public_usable, _ = _public_base_url_usable(settings.public_base_url)
    if provider == Provider.GITHUB.value:
        return bool(settings.github_api_token and settings.github_webhook_secret and public_usable)
    return bool(settings.gitlab_base_url and settings.gitlab_api_token and settings.gitlab_webhook_secret and public_usable)


def validate_repo(payload: RepoValidationRequest) -> RepoValidationRead:
    settings = get_settings()
    parsed = parse_repo_url(payload.repo_url, payload.provider, settings)

    if parsed.provider == Provider.GITHUB.value:
        if not settings.github_api_token:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="HEIMDALL_GITHUB_API_TOKEN is required to validate GitHub repository access.",
            )
        metadata = _http_get_json(
            f"{GITHUB_API_BASE_URL}/repos/{parsed.api_path}",
            _github_headers(settings),
            "GitHub",
            "validating repository access",
        )
        if not isinstance(metadata, dict):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub API returned invalid metadata.")
        full_name = str(metadata.get("full_name") or parsed.api_path)
        provider_project_id = str(metadata.get("id") or full_name)
        return RepoValidationRead(
            provider=Provider.GITHUB.value,
            repo_url=payload.repo_url,
            normalized_repo=parsed.normalized_repo,
            provider_project_id=provider_project_id,
            full_name=full_name,
            default_branch=metadata.get("default_branch"),
            private=bool(metadata.get("private")),
            access_valid=True,
            can_register_webhook=_registration_capability(settings, Provider.GITHUB.value),
            message="GitHub repository access validated.",
        )

    if not settings.gitlab_api_token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="HEIMDALL_GITLAB_API_TOKEN is required to validate GitLab project access.",
        )
    gitlab_base_url, _, _ = _gitlab_base_parts(settings)
    metadata = _http_get_json(
        f"{gitlab_base_url}/api/v4/projects/{quote(parsed.api_path, safe='')}",
        _gitlab_headers(settings),
        "GitLab",
        "validating project access",
    )
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitLab API returned invalid metadata.")
    full_name = str(metadata.get("path_with_namespace") or parsed.api_path)
    visibility = str(metadata.get("visibility") or "")
    return RepoValidationRead(
        provider=Provider.GITLAB.value,
        repo_url=payload.repo_url,
        normalized_repo=parsed.normalized_repo,
        provider_project_id=str(metadata.get("id") or full_name),
        full_name=full_name,
        default_branch=metadata.get("default_branch"),
        private=visibility != "public",
        access_valid=True,
        can_register_webhook=_registration_capability(settings, Provider.GITLAB.value),
        message="GitLab project access validated.",
    )


def _events_from_value(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    return []


def _serialize_registration(row: DBRow) -> WebhookRegistrationRead:
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
        active=bool(int(data["active"])),
        events=_events_from_value(events),
        registered_at=data["registered_at"],
        updated_at=data["updated_at"],
        message=str(data["message"] or ""),
    )


def _save_registration_state(
    settings: Settings,
    *,
    project_id: str,
    provider: str,
    provider_project_id: str,
    provider_webhook_id: str | None,
    webhook_url: str,
    status_value: str,
    message: str,
    active: bool,
    events: list[str],
) -> WebhookRegistrationRead:
    timestamp = utc_now()
    registered_at = timestamp if status_value in {"registered", "already_registered"} else None
    with connect(settings) as connection:
        existing = connection.execute(
            "SELECT registered_at FROM project_webhook_registrations WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if existing is None:
            connection.execute(
                """
                INSERT INTO project_webhook_registrations (
                    project_id, provider, provider_project_id, provider_webhook_id, webhook_url,
                    status, message, active, events, registered_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    provider,
                    provider_project_id,
                    provider_webhook_id,
                    webhook_url,
                    status_value,
                    message,
                    int(active),
                    json.dumps(events),
                    registered_at,
                    timestamp,
                ),
            )
        else:
            connection.execute(
                """
                UPDATE project_webhook_registrations
                SET provider = ?, provider_project_id = ?, provider_webhook_id = ?, webhook_url = ?,
                    status = ?, message = ?, active = ?, events = ?,
                    registered_at = COALESCE(?, registered_at), updated_at = ?
                WHERE project_id = ?
                """,
                (
                    provider,
                    provider_project_id,
                    provider_webhook_id,
                    webhook_url,
                    status_value,
                    message,
                    int(active),
                    json.dumps(events),
                    registered_at,
                    timestamp,
                    project_id,
                ),
            )
        row = connection.execute(
            "SELECT * FROM project_webhook_registrations WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        assert row is not None
        return _serialize_registration(row)


def _get_project(project_id: str, settings: Settings) -> dict[str, object]:
    with connect(settings) as connection:
        row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' was not found.")
    project = row_to_dict(row)
    assert project is not None
    return project


def _save_not_ready(
    settings: Settings,
    project: dict[str, object],
    parsed: ParsedRepo,
    webhook_url: str,
    message: str,
) -> None:
    _save_registration_state(
        settings,
        project_id=str(project["id"]),
        provider=parsed.provider,
        provider_project_id=parsed.api_path,
        provider_webhook_id=None,
        webhook_url=webhook_url,
        status_value="not_ready",
        message=message,
        active=False,
        events=[],
    )


def _save_failed(
    settings: Settings,
    project: dict[str, object],
    parsed: ParsedRepo,
    webhook_url: str,
    provider_project_id: str,
    message: str,
) -> None:
    _save_registration_state(
        settings,
        project_id=str(project["id"]),
        provider=parsed.provider,
        provider_project_id=provider_project_id,
        provider_webhook_id=None,
        webhook_url=webhook_url,
        status_value="failed",
        message=message,
        active=False,
        events=[],
    )


def _require_registration_ready(settings: Settings, project: dict[str, object], parsed: ParsedRepo, webhook_url: str) -> None:
    public_usable, public_message = _public_base_url_usable(settings.public_base_url)
    if not public_usable:
        _save_not_ready(settings, project, parsed, webhook_url, public_message)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=public_message)

    if parsed.provider == Provider.GITHUB.value:
        if not settings.github_api_token:
            message = "HEIMDALL_GITHUB_API_TOKEN is required to register GitHub webhooks."
            _save_not_ready(settings, project, parsed, webhook_url, message)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)
        if not settings.github_webhook_secret:
            message = "HEIMDALL_GITHUB_WEBHOOK_SECRET is required to register GitHub webhooks."
            _save_not_ready(settings, project, parsed, webhook_url, message)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)
        return

    if not settings.gitlab_base_url:
        message = "HEIMDALL_GITLAB_BASE_URL is required to register GitLab webhooks."
        _save_not_ready(settings, project, parsed, webhook_url, message)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)
    if not settings.gitlab_api_token:
        message = "HEIMDALL_GITLAB_API_TOKEN is required to register GitLab webhooks."
        _save_not_ready(settings, project, parsed, webhook_url, message)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)
    if not settings.gitlab_webhook_secret:
        message = "HEIMDALL_GITLAB_WEBHOOK_SECRET is required to register GitLab webhooks."
        _save_not_ready(settings, project, parsed, webhook_url, message)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)


def _github_hook_matches(hook: dict[str, object], webhook_url: str) -> bool:
    config = hook.get("config")
    events = _events_from_value(hook.get("events"))
    return isinstance(config, dict) and bool(hook.get("active")) and config.get("url") == webhook_url and "push" in events


def _register_github_webhook(
    settings: Settings,
    project: dict[str, object],
    parsed: ParsedRepo,
    webhook_url: str,
) -> WebhookRegistrationRead:
    assert settings.github_webhook_secret is not None
    try:
        hooks = _http_get_json(
            f"{GITHUB_API_BASE_URL}/repos/{parsed.api_path}/hooks",
            _github_headers(settings),
            "GitHub",
            "listing webhooks",
        )
        if not isinstance(hooks, list):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub API returned invalid hook list.")

        for hook in hooks:
            if isinstance(hook, dict) and _github_hook_matches(hook, webhook_url):
                return _save_registration_state(
                    settings,
                    project_id=str(project["id"]),
                    provider=Provider.GITHUB.value,
                    provider_project_id=parsed.api_path,
                    provider_webhook_id=str(hook.get("id")) if hook.get("id") is not None else None,
                    webhook_url=webhook_url,
                    status_value="already_registered",
                    message="Existing active GitHub push webhook reused.",
                    active=bool(hook.get("active")),
                    events=_events_from_value(hook.get("events")),
                )

        hook = _http_post_json(
            f"{GITHUB_API_BASE_URL}/repos/{parsed.api_path}/hooks",
            _github_headers(settings),
            "GitHub",
            "creating webhook",
            {
                "name": "web",
                "active": True,
                "events": ["push"],
                "config": {
                    "url": webhook_url,
                    "content_type": "json",
                    "secret": settings.github_webhook_secret,
                    "insecure_ssl": "0",
                },
            },
        )
        if not isinstance(hook, dict):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub API returned invalid hook metadata.")
        return _save_registration_state(
            settings,
            project_id=str(project["id"]),
            provider=Provider.GITHUB.value,
            provider_project_id=parsed.api_path,
            provider_webhook_id=str(hook.get("id")) if hook.get("id") is not None else None,
            webhook_url=webhook_url,
            status_value="registered",
            message="GitHub push webhook registered.",
            active=bool(hook.get("active", True)),
            events=_events_from_value(hook.get("events")) or ["push"],
        )
    except HTTPException as exc:
        _save_failed(settings, project, parsed, webhook_url, parsed.api_path, str(exc.detail))
        raise


def _gitlab_hook_matches(hook: dict[str, object], webhook_url: str) -> bool:
    return bool(hook.get("push_events")) and hook.get("url") == webhook_url


def _register_gitlab_webhook(
    settings: Settings,
    project: dict[str, object],
    parsed: ParsedRepo,
    webhook_url: str,
) -> WebhookRegistrationRead:
    assert settings.gitlab_webhook_secret is not None
    gitlab_base_url, _, _ = _gitlab_base_parts(settings)
    provider_project_id = parsed.api_path
    try:
        metadata = _http_get_json(
            f"{gitlab_base_url}/api/v4/projects/{quote(parsed.api_path, safe='')}",
            _gitlab_headers(settings),
            "GitLab",
            "looking up project",
        )
        if not isinstance(metadata, dict):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitLab API returned invalid metadata.")
        provider_project_id = str(metadata.get("id") or parsed.api_path)

        hooks = _http_get_json(
            f"{gitlab_base_url}/api/v4/projects/{quote(provider_project_id, safe='')}/hooks",
            _gitlab_headers(settings),
            "GitLab",
            "listing webhooks",
        )
        if not isinstance(hooks, list):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitLab API returned invalid hook list.")

        for hook in hooks:
            if isinstance(hook, dict) and _gitlab_hook_matches(hook, webhook_url):
                return _save_registration_state(
                    settings,
                    project_id=str(project["id"]),
                    provider=Provider.GITLAB.value,
                    provider_project_id=provider_project_id,
                    provider_webhook_id=str(hook.get("id")) if hook.get("id") is not None else None,
                    webhook_url=webhook_url,
                    status_value="already_registered",
                    message="Existing GitLab push webhook reused.",
                    active=True,
                    events=["push"],
                )

        hook = _http_post_json(
            f"{gitlab_base_url}/api/v4/projects/{quote(provider_project_id, safe='')}/hooks",
            _gitlab_headers(settings),
            "GitLab",
            "creating webhook",
            {
                "url": webhook_url,
                "push_events": True,
                "push_events_branch_filter": str(project["tracked_branch"]),
                "enable_ssl_verification": True,
                "token": settings.gitlab_webhook_secret,
            },
        )
        if not isinstance(hook, dict):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitLab API returned invalid hook metadata.")
        return _save_registration_state(
            settings,
            project_id=str(project["id"]),
            provider=Provider.GITLAB.value,
            provider_project_id=provider_project_id,
            provider_webhook_id=str(hook.get("id")) if hook.get("id") is not None else None,
            webhook_url=webhook_url,
            status_value="registered",
            message="GitLab push webhook registered.",
            active=True,
            events=["push"],
        )
    except HTTPException as exc:
        _save_failed(settings, project, parsed, webhook_url, provider_project_id, str(exc.detail))
        raise


def register_project_webhook(project_id: str) -> WebhookRegistrationRead:
    settings = get_settings()
    project = _get_project(project_id, settings)
    provider = str(project["provider"])
    if provider not in {Provider.GITHUB.value, Provider.GITLAB.value}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Project provider is unsupported.")

    parsed = parse_repo_url(str(project["repo_url"]), provider, settings)
    webhook_url = _webhook_urls(settings)[provider]
    _require_registration_ready(settings, project, parsed, webhook_url)

    if provider == Provider.GITHUB.value:
        return _register_github_webhook(settings, project, parsed, webhook_url)
    return _register_gitlab_webhook(settings, project, parsed, webhook_url)
