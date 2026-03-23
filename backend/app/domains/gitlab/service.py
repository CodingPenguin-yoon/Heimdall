"""GitLab project inventory service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from sqlalchemy import select

from app.shared.gitlab_settings import GitLabSettings, get_gitlab_settings
from app.shared.platform_db import create_platform_engine, create_session_factory
from app.shared.platform_models import GitLabProject, GitLabProjectSettings, PlatformMetadata


GITLAB_SYNC_METADATA_KEY = "gitlab_projects_sync"
ALLOWED_DATABASE_ENGINES = {"postgres"}
ALLOWED_DATABASE_MODES = {"shared-cluster", "dedicated-instance"}
ALLOWED_BOOTSTRAP_STRATEGIES = {"merge_request", "direct_commit", "manual"}


class GitLabConfigurationError(RuntimeError):
    """Raised when GitLab settings are not safe to use."""


class GitLabSyncError(RuntimeError):
    """Raised when GitLab project sync fails."""


class GitLabProjectCreateError(RuntimeError):
    """Raised when GitLab project creation fails."""


class GitLabProjectNotFoundError(RuntimeError):
    """Raised when a persisted GitLab project cannot be found."""


class GitLabProjectSettingsError(RuntimeError):
    """Raised when a project settings payload is invalid."""


class GitLabInventoryService:
    """Persist and expose the first GitLab project inventory slice."""

    def __init__(self) -> None:
        self._engine = create_platform_engine()
        self._session_factory = create_session_factory(self._engine)

    def list_projects(self) -> dict[str, Any]:
        settings = get_gitlab_settings()
        with self._session_factory() as session:
            projects = list(
                session.execute(
                    select(GitLabProject).order_by(
                        GitLabProject.path_with_namespace.asc(),
                        GitLabProject.gitlab_project_id.asc(),
                    )
                ).scalars()
            )
            settings_by_project_id = self._load_settings_map(
                session=session,
                project_ids=[project.gitlab_project_id for project in projects],
            )
            metadata = session.get(PlatformMetadata, GITLAB_SYNC_METADATA_KEY)

            return {
                "configured": settings.is_configured,
                "can_sync": settings.can_sync,
                "default_namespace_path": settings.default_namespace_path,
                "configuration_error": settings.validation_error,
                "projects": [
                    self._serialize_project(
                        project=project,
                        project_settings=settings_by_project_id.get(project.gitlab_project_id),
                    )
                    for project in projects
                ],
                "last_sync": metadata.value_json if metadata is not None else None,
            }

    def get_project_settings(self, project_id: int) -> dict[str, Any]:
        project_id = self._coerce_project_id(project_id)

        with self._session_factory() as session:
            project = session.get(GitLabProject, project_id)
            if project is None:
                raise GitLabProjectNotFoundError(f"GitLab project {project_id} was not found.")

            project_settings = session.get(GitLabProjectSettings, project_id)
            return self._serialize_project_settings_detail(
                project_id=project_id,
                project_settings=project_settings,
            )

    def upsert_project_settings(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = self._coerce_project_id(project_id)
        normalized_payload = self._normalize_project_settings_payload(payload)
        now = self._now_iso()

        with self._session_factory.begin() as session:
            project = session.get(GitLabProject, project_id)
            if project is None:
                raise GitLabProjectNotFoundError(f"GitLab project {project_id} was not found.")

            project_settings = session.get(GitLabProjectSettings, project_id)
            if project_settings is None:
                project_settings = GitLabProjectSettings(gitlab_project_id=project_id)
                session.add(project_settings)

            project_settings.staging_enabled = normalized_payload["staging_enabled"]
            project_settings.ready_for_bootstrap = normalized_payload["ready_for_bootstrap"]
            project_settings.database_required = normalized_payload["database_required"]
            project_settings.database_engine = normalized_payload["database_engine"]
            project_settings.database_mode = normalized_payload["database_mode"]
            project_settings.migration_command = normalized_payload["migration_command"]
            project_settings.deploy_branch = normalized_payload["deploy_branch"]
            project_settings.bootstrap_strategy = normalized_payload["bootstrap_strategy"]
            project_settings.notes = normalized_payload["notes"]
            project_settings.updated_at = now

        with self._session_factory() as session:
            persisted_settings = session.get(GitLabProjectSettings, project_id)
            return self._serialize_project_settings_detail(
                project_id=project_id,
                project_settings=persisted_settings,
            )

    def sync_projects(self) -> dict[str, Any]:
        settings = get_gitlab_settings()
        self._validate_sync_settings(settings)

        now = self._now_iso()

        try:
            remote_projects = self._fetch_projects(settings)
        except GitLabSyncError as exc:
            self._save_sync_metadata(
                {
                    "status": "error",
                    "error": str(exc),
                    "updated_at": now,
                }
            )
            raise

        with self._session_factory.begin() as session:
            existing_by_id = {
                project.gitlab_project_id: project
                for project in session.execute(select(GitLabProject)).scalars()
            }
            seen_ids: set[int] = set()

            for project_payload in remote_projects:
                project_id = int(project_payload["id"])
                seen_ids.add(project_id)
                self._upsert_project_record(
                    session=session,
                    project_payload=project_payload,
                    synced_at=now,
                    existing_by_id=existing_by_id,
                )

            for project_id, record in existing_by_id.items():
                if project_id not in seen_ids:
                    session.delete(record)

            metadata = session.get(PlatformMetadata, GITLAB_SYNC_METADATA_KEY)
            value = {
                "status": "success",
                "project_count": len(remote_projects),
                "updated_at": now,
            }
            if metadata is None:
                session.add(PlatformMetadata(key=GITLAB_SYNC_METADATA_KEY, value_json=value))
            else:
                metadata.value_json = value

        return {
            "status": "success",
            "project_count": len(remote_projects),
            "updated_at": now,
        }

    def list_namespaces(self) -> list[dict[str, Any]]:
        settings = get_gitlab_settings()
        self._validate_sync_settings(settings)

        namespaces = self._fetch_namespaces(settings)
        return [
            {
                "id": int(namespace["id"]),
                "name": str(namespace.get("name") or ""),
                "path": str(namespace.get("path") or ""),
                "full_path": str(namespace.get("full_path") or ""),
                "kind": str(namespace.get("kind") or ""),
                "web_url": str(namespace.get("web_url") or ""),
            }
            for namespace in namespaces
        ]

    def create_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = get_gitlab_settings()
        self._validate_sync_settings(settings)

        initialize_with_readme = bool(payload.get("initialize_with_readme", False))
        default_branch = str(payload.get("default_branch") or "").strip()
        if default_branch and not initialize_with_readme:
            raise GitLabProjectCreateError(
                "default_branch can only be set when initialize_with_readme is true."
            )

        request_payload = {
            "name": str(payload.get("name") or "").strip(),
            "visibility": str(payload.get("visibility") or "private").strip(),
            "initialize_with_readme": initialize_with_readme,
        }
        if not request_payload["name"]:
            raise GitLabProjectCreateError("name is required.")
        if request_payload["visibility"] not in {"private", "internal", "public"}:
            raise GitLabProjectCreateError("visibility must be one of: private, internal, public.")

        for field_name in ("path", "description", "default_branch"):
            value = str(payload.get(field_name) or "").strip()
            if value:
                request_payload[field_name] = value

        request_payload["namespace_id"] = self._resolve_default_namespace_id(settings)

        project_payload = self._create_remote_project(settings, request_payload)
        now = self._now_iso()

        with self._session_factory.begin() as session:
            record = self._upsert_project_record(
                session=session,
                project_payload=project_payload,
                synced_at=now,
                existing_by_id=None,
            )

        return {
            "project": self._serialize_project(project=record, project_settings=None)
        }

    def _validate_sync_settings(self, settings: GitLabSettings) -> None:
        if settings.validation_error is not None:
            raise GitLabConfigurationError(settings.validation_error)
        if not settings.api_token:
            raise GitLabConfigurationError("GITLAB_API_TOKEN is not configured.")

    def _fetch_projects(self, settings: GitLabSettings) -> list[dict[str, Any]]:
        session = self._create_gitlab_session(settings)
        url = urljoin(f"{settings.base_url}/", "api/v4/projects")
        page = 1
        projects: list[dict[str, Any]] = []

        while True:
            response = self._request_gitlab(
                session=session,
                method="GET",
                url=url,
                settings=settings,
                params={
                    "page": page,
                    "per_page": 100,
                    "simple": True,
                    "order_by": "id",
                    "sort": "asc",
                },
                error_cls=GitLabSyncError,
            )

            payload = response.json()
            if not isinstance(payload, list):
                raise GitLabSyncError("GitLab API returned an unexpected projects payload.")

            projects.extend(item for item in payload if isinstance(item, dict))

            next_page = (response.headers.get("x-next-page") or "").strip()
            if not next_page:
                break
            page = int(next_page)

        return projects

    def _fetch_namespaces(self, settings: GitLabSettings) -> list[dict[str, Any]]:
        session = self._create_gitlab_session(settings)
        url = urljoin(f"{settings.base_url}/", "api/v4/namespaces")
        page = 1
        namespaces: list[dict[str, Any]] = []

        while True:
            response = self._request_gitlab(
                session=session,
                method="GET",
                url=url,
                settings=settings,
                params={"page": page, "per_page": 100},
                error_cls=GitLabSyncError,
            )

            payload = response.json()
            if not isinstance(payload, list):
                raise GitLabSyncError("GitLab API returned an unexpected namespaces payload.")

            namespaces.extend(item for item in payload if isinstance(item, dict))

            next_page = (response.headers.get("x-next-page") or "").strip()
            if not next_page:
                break
            page = int(next_page)

        namespaces.sort(
            key=lambda namespace: str(namespace.get("full_path") or namespace.get("name") or "").lower()
        )
        return namespaces

    def _create_remote_project(
        self,
        settings: GitLabSettings,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        session = self._create_gitlab_session(settings)
        url = urljoin(f"{settings.base_url}/", "api/v4/projects")
        response = self._request_gitlab(
            session=session,
            method="POST",
            url=url,
            settings=settings,
            data=payload,
            error_cls=GitLabProjectCreateError,
        )

        project_payload = response.json()
        if not isinstance(project_payload, dict):
            raise GitLabProjectCreateError("GitLab API returned an unexpected project payload.")
        return project_payload

    def _create_gitlab_session(self, settings: GitLabSettings) -> requests.Session:
        session = requests.Session()
        session.headers.update({"PRIVATE-TOKEN": settings.api_token})
        return session

    def _resolve_default_namespace_id(self, settings: GitLabSettings) -> int:
        target = settings.default_namespace_path.strip()
        if not target:
            raise GitLabProjectCreateError("GITLAB_DEFAULT_NAMESPACE_PATH is not configured.")

        normalized_target = target.lower()
        for namespace in self._fetch_namespaces(settings):
            candidates = [
                str(namespace.get("full_path") or "").strip(),
                str(namespace.get("path") or "").strip(),
                str(namespace.get("name") or "").strip(),
            ]
            if any(candidate.lower() == normalized_target for candidate in candidates if candidate):
                return int(namespace["id"])

        raise GitLabProjectCreateError(
            f"Configured GitLab namespace '{target}' could not be resolved."
        )

    def _request_gitlab(
        self,
        session: requests.Session,
        method: str,
        url: str,
        settings: GitLabSettings,
        error_cls: type[RuntimeError],
        **kwargs: Any,
    ) -> requests.Response:
        try:
            response = session.request(
                method=method,
                url=url,
                timeout=(5, 30),
                verify=settings.verify_ssl,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            raise error_cls(self._map_gitlab_request_error(exc)) from exc

    def _map_gitlab_request_error(self, exc: requests.RequestException) -> str:
        response = getattr(exc, "response", None)
        if response is None:
            return "GitLab API request failed."

        detail = self._extract_gitlab_error_detail(response)
        if detail:
            return f"GitLab API request failed with status {response.status_code}: {detail}"
        return f"GitLab API request failed with status {response.status_code}."

    def _extract_gitlab_error_detail(self, response: requests.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            return None

        if isinstance(payload, dict):
            message = payload.get("message")
            error = payload.get("error")

            if isinstance(message, str) and message.strip():
                return message.strip()
            if isinstance(error, str) and error.strip():
                return error.strip()
            if isinstance(message, dict):
                parts: list[str] = []
                for field_name, field_errors in message.items():
                    if isinstance(field_errors, list):
                        joined = ", ".join(str(item).strip() for item in field_errors if str(item).strip())
                        if joined:
                            parts.append(f"{field_name}: {joined}")
                    elif isinstance(field_errors, str) and field_errors.strip():
                        parts.append(f"{field_name}: {field_errors.strip()}")
                if parts:
                    return "; ".join(parts)

        return None

    def _coerce_project_id(self, project_id: int | str) -> int:
        try:
            return int(project_id)
        except (TypeError, ValueError) as exc:
            raise GitLabProjectSettingsError("project_id must be an integer.") from exc

    def _load_settings_map(
        self,
        session: Any,
        project_ids: list[int],
    ) -> dict[int, GitLabProjectSettings]:
        if not project_ids:
            return {}

        return {
            project_settings.gitlab_project_id: project_settings
            for project_settings in session.execute(
                select(GitLabProjectSettings).where(GitLabProjectSettings.gitlab_project_id.in_(project_ids))
            ).scalars()
        }

    def _normalize_project_settings_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        staging_enabled = bool(payload.get("staging_enabled", False))
        ready_for_bootstrap = bool(payload.get("ready_for_bootstrap", False))
        database_required = bool(payload.get("database_required", False))
        database_engine = str(payload.get("database_engine") or "").strip().lower() or None
        database_mode = str(payload.get("database_mode") or "").strip().lower() or None
        migration_command = str(payload.get("migration_command") or "").strip() or None
        deploy_branch = str(payload.get("deploy_branch") or "").strip()
        bootstrap_strategy = str(payload.get("bootstrap_strategy") or "").strip().lower()
        notes = str(payload.get("notes") or "").strip() or None

        if ready_for_bootstrap and not staging_enabled:
            raise GitLabProjectSettingsError(
                "ready_for_bootstrap requires staging_enabled to be true."
            )
        if not deploy_branch:
            raise GitLabProjectSettingsError("deploy_branch is required.")
        if bootstrap_strategy not in ALLOWED_BOOTSTRAP_STRATEGIES:
            raise GitLabProjectSettingsError(
                "bootstrap_strategy must be one of: merge_request, direct_commit, manual."
            )

        if not database_required:
            database_engine = None
            database_mode = None
            migration_command = None
        else:
            if database_engine not in ALLOWED_DATABASE_ENGINES:
                raise GitLabProjectSettingsError("database_engine must be postgres for this MVP.")
            if database_mode not in ALLOWED_DATABASE_MODES:
                raise GitLabProjectSettingsError(
                    "database_mode must be one of: shared-cluster, dedicated-instance."
                )

        return {
            "staging_enabled": staging_enabled,
            "ready_for_bootstrap": ready_for_bootstrap,
            "database_required": database_required,
            "database_engine": database_engine,
            "database_mode": database_mode,
            "migration_command": migration_command,
            "deploy_branch": deploy_branch,
            "bootstrap_strategy": bootstrap_strategy,
            "notes": notes,
        }

    def _serialize_project(
        self,
        project: GitLabProject,
        project_settings: GitLabProjectSettings | None,
    ) -> dict[str, Any]:
        return {
            "gitlab_project_id": project.gitlab_project_id,
            "name": project.name,
            "path_with_namespace": project.path_with_namespace,
            "web_url": project.web_url,
            "http_url_to_repo": project.http_url_to_repo,
            "ssh_url_to_repo": project.ssh_url_to_repo,
            "default_branch": project.default_branch,
            "visibility": project.visibility,
            "archived": project.archived,
            "last_activity_at": project.last_activity_at,
            "synced_at": project.synced_at,
            "configuration_status": self._derive_configuration_status(project_settings),
            "settings_summary": self._serialize_project_settings_summary(project_settings),
        }

    def _serialize_project_settings_summary(
        self,
        project_settings: GitLabProjectSettings | None,
    ) -> dict[str, Any] | None:
        if project_settings is None:
            return None

        return {
            "staging_enabled": project_settings.staging_enabled,
            "ready_for_bootstrap": project_settings.ready_for_bootstrap,
            "database_required": project_settings.database_required,
            "database_engine": project_settings.database_engine,
            "database_mode": project_settings.database_mode,
            "migration_command": project_settings.migration_command,
            "deploy_branch": project_settings.deploy_branch,
            "bootstrap_strategy": project_settings.bootstrap_strategy,
            "updated_at": project_settings.updated_at,
        }

    def _serialize_project_settings_detail(
        self,
        project_id: int,
        project_settings: GitLabProjectSettings | None,
    ) -> dict[str, Any]:
        summary = self._serialize_project_settings_summary(project_settings)
        return {
            "gitlab_project_id": project_id,
            "configuration_status": self._derive_configuration_status(project_settings),
            "staging_enabled": project_settings.staging_enabled if project_settings is not None else False,
            "ready_for_bootstrap": project_settings.ready_for_bootstrap if project_settings is not None else False,
            "database_required": project_settings.database_required if project_settings is not None else False,
            "database_engine": project_settings.database_engine if project_settings is not None else None,
            "database_mode": project_settings.database_mode if project_settings is not None else None,
            "migration_command": project_settings.migration_command if project_settings is not None else None,
            "deploy_branch": project_settings.deploy_branch if project_settings is not None else "main",
            "bootstrap_strategy": project_settings.bootstrap_strategy if project_settings is not None else "merge_request",
            "notes": project_settings.notes if project_settings is not None else None,
            "updated_at": project_settings.updated_at if project_settings is not None else None,
            "settings_summary": summary,
        }

    def _derive_configuration_status(
        self,
        project_settings: GitLabProjectSettings | None,
    ) -> str:
        if project_settings is None:
            return "discovered"
        if project_settings.ready_for_bootstrap:
            return "ready_for_bootstrap"
        return "configured"

    def _upsert_project_record(
        self,
        session: Any,
        project_payload: dict[str, Any],
        synced_at: str,
        existing_by_id: dict[int, GitLabProject] | None,
    ) -> GitLabProject:
        project_id = int(project_payload["id"])
        record = existing_by_id.get(project_id) if existing_by_id is not None else session.get(GitLabProject, project_id)
        if record is None:
            record = GitLabProject(gitlab_project_id=project_id)
            session.add(record)
            if existing_by_id is not None:
                existing_by_id[project_id] = record

        record.name = str(project_payload.get("name") or "")
        record.path_with_namespace = str(project_payload.get("path_with_namespace") or "")
        record.web_url = str(project_payload.get("web_url") or "")
        record.http_url_to_repo = str(project_payload.get("http_url_to_repo") or "")
        record.ssh_url_to_repo = str(project_payload.get("ssh_url_to_repo") or "") or None
        record.default_branch = project_payload.get("default_branch")
        record.visibility = str(project_payload.get("visibility") or "private")
        record.archived = bool(project_payload.get("archived", False))
        record.last_activity_at = project_payload.get("last_activity_at")
        record.synced_at = synced_at
        return record

    def _save_sync_metadata(self, value: dict[str, Any]) -> None:
        with self._session_factory.begin() as session:
            metadata = session.get(PlatformMetadata, GITLAB_SYNC_METADATA_KEY)
            if metadata is None:
                session.add(PlatformMetadata(key=GITLAB_SYNC_METADATA_KEY, value_json=value))
            else:
                metadata.value_json = value

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
