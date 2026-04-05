"""GitLab project inventory service."""

from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv4Interface, ip_address, ip_interface
from pathlib import PurePosixPath
import re
import time
from uuid import uuid4
from typing import Any
from urllib.parse import quote, urljoin

import requests
import yaml
from fastapi import BackgroundTasks
from sqlalchemy import select

from app.domains.deploy.service import DeploymentService
from app.shared.gitlab_settings import GitLabSettings, get_gitlab_settings
from app.shared.platform_db import create_platform_engine, create_session_factory
from app.shared.platform_models import GitLabProject, GitLabProjectSettings, PlatformMetadata
from app.shared.tasks import TaskStatus, task_manager


GITLAB_SYNC_METADATA_KEY = "gitlab_projects_sync"
ALLOWED_DATABASE_ENGINES = {"postgres"}
ALLOWED_DATABASE_MODES = {"shared-cluster", "dedicated-instance"}
ALLOWED_BOOTSTRAP_STRATEGIES = {"merge_request", "direct_commit", "manual"}
MANIFEST_FILE_PATH = ".heimdall/project.yaml"


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
        self._deployment_service = DeploymentService()

    def list_projects(self) -> dict[str, Any]:
        settings = get_gitlab_settings()
        manifest_context = self._create_manifest_lookup_context(settings)
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
                        manifest_context=manifest_context,
                    )
                    for project in projects
                ],
                "last_sync": metadata.value_json if metadata is not None else None,
            }

    def get_project_settings(self, project_id: int) -> dict[str, Any]:
        project_id = self._coerce_project_id(project_id)
        settings = get_gitlab_settings()
        manifest_context = self._create_manifest_lookup_context(settings)

        with self._session_factory() as session:
            project = session.get(GitLabProject, project_id)
            if project is None:
                raise GitLabProjectNotFoundError(f"GitLab project {project_id} was not found.")

            project_settings = session.get(GitLabProjectSettings, project_id)
            return self._serialize_project_settings_detail(
                project=project,
                project_id=project_id,
                project_settings=project_settings,
                manifest_context=manifest_context,
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
            project_settings.staging_server_name = normalized_payload["staging_server_name"]
            project_settings.staging_server_id = normalized_payload["staging_server_id"]
            project_settings.staging_template_id = normalized_payload["staging_template_id"]
            project_settings.staging_storage_id = normalized_payload["staging_storage_id"]
            project_settings.staging_network_ids = normalized_payload["staging_network_ids"]
            project_settings.staging_cpu_cores = normalized_payload["staging_cpu_cores"]
            project_settings.staging_memory_gb = normalized_payload["staging_memory_gb"]
            project_settings.staging_disk_size_gb = normalized_payload["staging_disk_size_gb"]
            project_settings.staging_vm_ip = normalized_payload["staging_vm_ip"]
            project_settings.staging_vm_gateway = normalized_payload["staging_vm_gateway"]
            project_settings.staging_ansible_packages = normalized_payload["staging_ansible_packages"]
            project_settings.staging_ansible_roles = normalized_payload["staging_ansible_roles"]
            project_settings.notes = normalized_payload["notes"]
            project_settings.updated_at = now

        with self._session_factory() as session:
            settings = get_gitlab_settings()
            manifest_context = self._create_manifest_lookup_context(settings)
            project = session.get(GitLabProject, project_id)
            if project is None:
                raise GitLabProjectNotFoundError(f"GitLab project {project_id} was not found.")
            persisted_settings = session.get(GitLabProjectSettings, project_id)
            return self._serialize_project_settings_detail(
                project=project,
                project_id=project_id,
                project_settings=persisted_settings,
                manifest_context=manifest_context,
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
        manifest_seed_result = self._seed_project_manifest_draft(
            settings=settings,
            project_payload=project_payload,
            initialize_with_readme=initialize_with_readme,
        )
        now = self._now_iso()

        with self._session_factory.begin() as session:
            record = self._upsert_project_record(
                session=session,
                project_payload=project_payload,
                synced_at=now,
                existing_by_id=None,
            )

        return {
            "project": self._serialize_project(
                project=record,
                project_settings=None,
                manifest_context=self._create_manifest_lookup_context(settings),
            ),
            "manifest_seeded": bool(manifest_seed_result["seeded"]),
            "manifest_seed_message": manifest_seed_result["message"],
        }

    def request_staging_deploy(
        self,
        project_id: int,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        project_id = self._coerce_project_id(project_id)

        with self._session_factory() as session:
            project = session.get(GitLabProject, project_id)
            if project is None:
                raise GitLabProjectNotFoundError(f"GitLab project {project_id} was not found.")
            if project.archived:
                raise GitLabProjectSettingsError("Archived projects cannot request staging deploys.")

            project_settings = session.get(GitLabProjectSettings, project_id)
            if project_settings is None:
                raise GitLabProjectSettingsError(
                    "Project settings must exist before requesting a staging deploy."
                )
            if not project_settings.staging_enabled:
                raise GitLabProjectSettingsError(
                    "staging_enabled must be true before requesting a staging deploy."
                )
            if not project_settings.ready_for_bootstrap:
                raise GitLabProjectSettingsError(
                    "ready_for_bootstrap must be true before requesting a staging deploy."
                )
            if project_settings.database_required:
                raise GitLabProjectSettingsError(
                    "database_required=true projects are not supported yet for Deploy Staging."
                )

            manifest = self._load_project_manifest(
                project=project,
                manifest_context=self._create_manifest_lookup_context(get_gitlab_settings()),
                ref=project_settings.deploy_branch,
            )
            if manifest["manifest_status"] != "valid":
                raise GitLabProjectSettingsError(
                    f"Staging deploy requires a valid {MANIFEST_FILE_PATH}: "
                    f"{manifest['manifest_summary']}"
                )
            self._validate_staging_infra_profile(project_settings)

            duplicate_task = self._find_live_staging_request(project_id)
            if duplicate_task is not None:
                return {
                    "task_id": str(duplicate_task.get("task_id")),
                    "message": "이미 진행 중인 staging deploy 요청이 있습니다. Task Board에서 상태를 확인하세요.",
                    "status": str(duplicate_task.get("status") or "pending").lower(),
                    "already_exists": True,
                }

            task_id = f"gitlab-staging-deploy-{project_id}-{uuid4().hex[:8]}"
            task_metadata = {
                "action": "gitlab_staging_deploy",
                "environment": "staging",
                "trigger_source": "gitlab",
                "gitlab_project_id": project.gitlab_project_id,
                "path_with_namespace": project.path_with_namespace,
                "deploy_branch": project_settings.deploy_branch,
                "execution_mode": "manual_staging_app_deploy",
                "infra_execution": "starting",
                "note": (
                    "GitLab staging wrapper task. This slice runs manual staging infra "
                    "provisioning plus docker-compose app deployment. DB automation is excluded."
                ),
            }
            task_manager.create_task(task_id, metadata=task_metadata)
            task_manager.update_status(task_id, TaskStatus.PENDING)
            task_manager.update_status(task_id, TaskStatus.RUNNING)
            task_manager.update_progress(
                task_id,
                5.0,
                text="GitLab staging wrapper started",
                source="phase",
            )
            task_manager.append_log(task_id, "=== GitLab staging deploy wrapper 시작 ===")
            task_manager.append_log(
                task_id,
                "이 작업은 manual staging app deploy 모드로 실제 인프라 배포 task를 연결합니다.",
            )
            task_manager.append_log(
                task_id,
                f"대상 프로젝트: {project.path_with_namespace} (GitLab project ID: {project_id})",
            )
            task_manager.append_log(task_id, f"배포 브랜치: {project_settings.deploy_branch}")

            deploy_request = self._build_staging_deploy_request(
                project,
                project_settings,
                manifest_payload=manifest["manifest_payload"],
            )
            deploy_task_id = self._deployment_service.start_deployment_with_request(
                background_tasks=background_tasks,
                deploy_request=deploy_request,
            )
            task_manager.update_metadata(
                deploy_task_id,
                {
                    "trigger_source": "gitlab",
                    "environment": "staging",
                    "gitlab_project_id": project.gitlab_project_id,
                    "path_with_namespace": project.path_with_namespace,
                    "deploy_branch": project_settings.deploy_branch,
                    "linked_wrapper_task_id": task_id,
                    "execution_mode": "manual_staging_app_deploy",
                    "app_deploy_enabled": True,
                },
            )
            task_manager.append_log(
                deploy_task_id,
                "GitLab Deploy Staging 연결됨: 실제 인프라 배포 후 docker-compose 앱 배포까지 수행합니다. DB 자동화는 제외됩니다.",
            )
            task_manager.update_metadata(
                task_id,
                {
                    "linked_deploy_task_id": deploy_task_id,
                    "app_deploy_enabled": True,
                },
            )
            task_manager.append_log(task_id, f"실제 인프라 배포 task 생성: {deploy_task_id}")
            task_manager.update_progress(
                task_id,
                15.0,
                text="Infra provisioning task linked",
                source="phase",
            )

        background_tasks.add_task(
            self._finalize_staging_deploy_wrapper,
            task_id,
            deploy_task_id,
            {
                "project_id": project_id,
                "path_with_namespace": project.path_with_namespace,
                "deploy_branch": project_settings.deploy_branch,
            },
        )

        return {
            "task_id": task_id,
            "message": (
                "Staging infra 및 app deploy가 시작되었습니다. "
                "Task Board에서 wrapper task와 linked deploy task를 확인하세요."
            ),
            "status": "running",
            "already_exists": False,
        }

    def _validate_sync_settings(self, settings: GitLabSettings) -> None:
        if settings.validation_error is not None:
            raise GitLabConfigurationError(settings.validation_error)
        if not settings.api_token:
            raise GitLabConfigurationError("GITLAB_API_TOKEN is not configured.")

    def _find_live_staging_request(self, project_id: int) -> dict[str, Any] | None:
        tasks = task_manager.list_tasks(limit=1000, include_archived=True)
        for task in tasks:
            metadata = task.get("metadata") or {}
            if not isinstance(metadata, dict):
                continue
            action = metadata.get("action")
            is_wrapper = action == "gitlab_staging_deploy"
            is_gitlab_deploy = action == "deploy" and metadata.get("trigger_source") == "gitlab"
            if not is_wrapper and not is_gitlab_deploy:
                continue
            if metadata.get("environment") != "staging":
                continue
            metadata_project_id = metadata.get("gitlab_project_id")
            try:
                if int(metadata_project_id) != project_id:
                    continue
            except (TypeError, ValueError):
                continue
            if task.get("status") not in {TaskStatus.PENDING.value, TaskStatus.RUNNING.value}:
                continue
            return task
        return None

    def _validate_staging_infra_profile(self, project_settings: GitLabProjectSettings) -> None:
        required_fields = {
            "staging_server_name": project_settings.staging_server_name,
            "staging_server_id": project_settings.staging_server_id,
            "staging_template_id": project_settings.staging_template_id,
            "staging_storage_id": project_settings.staging_storage_id,
        }
        missing_fields = [
            field_name for field_name, value in required_fields.items() if not str(value or "").strip()
        ]
        network_ids = [
            str(item).strip() for item in list(project_settings.staging_network_ids or []) if str(item).strip()
        ]
        if not network_ids:
            missing_fields.append("staging_network_ids")
        if missing_fields:
            raise GitLabProjectSettingsError(
                "Staging infra profile is incomplete. Missing required fields: "
                + ", ".join(missing_fields)
            )

    def _build_staging_deploy_request(
        self,
        project: GitLabProject,
        project_settings: GitLabProjectSettings,
        *,
        manifest_payload: dict[str, Any],
    ) -> dict[str, Any]:
        network_ids = [
            str(item).strip() for item in list(project_settings.staging_network_ids or []) if str(item).strip()
        ]
        deploy_config = manifest_payload.get("deploy") if isinstance(manifest_payload.get("deploy"), dict) else {}
        deploy_request = {
            "server_name": str(project_settings.staging_server_name or "").strip(),
            "server_id": str(project_settings.staging_server_id or "").strip(),
            "template_id": str(project_settings.staging_template_id or "").strip(),
            "storage_id": str(project_settings.staging_storage_id or "").strip(),
            "network_ids": network_ids,
            "disk_size_gb": project_settings.staging_disk_size_gb,
            "ansible_packages": list(project_settings.staging_ansible_packages or []),
            "ansible_roles": list(project_settings.staging_ansible_roles or []),
            "metadata": {
                "trigger_source": "gitlab",
                "environment": "staging",
                "gitlab_project_id": project.gitlab_project_id,
                "path_with_namespace": project.path_with_namespace,
                "deploy_branch": project_settings.deploy_branch,
                "execution_mode": "manual_staging_app_deploy",
            },
            "gitlab_project_id": project.gitlab_project_id,
            "path_with_namespace": project.path_with_namespace,
            "deploy_branch": project_settings.deploy_branch,
            "app_deploy_enabled": True,
            "app_project_slug": self._build_app_project_slug(project.path_with_namespace),
            "app_runtime": str(manifest_payload.get("runtime") or "").strip(),
            "compose_file": str(self._normalize_compose_file_path(deploy_config.get("compose_file")) or ""),
            "app_port": int(deploy_config.get("app_port")),
            "healthcheck_path": str(deploy_config.get("healthcheck_path") or "").strip(),
        }
        if project_settings.staging_cpu_cores is not None:
            deploy_request["cpu_cores"] = project_settings.staging_cpu_cores
        if project_settings.staging_memory_gb is not None:
            deploy_request["memory_gb"] = project_settings.staging_memory_gb
        if project_settings.staging_vm_ip is not None:
            deploy_request["vm_ip"] = project_settings.staging_vm_ip
        if project_settings.staging_vm_gateway is not None:
            deploy_request["vm_gateway"] = project_settings.staging_vm_gateway
        return deploy_request

    def _finalize_staging_deploy_wrapper(
        self,
        task_id: str,
        deploy_task_id: str,
        context: dict[str, Any],
    ) -> None:
        try:
            task_manager.append_log(task_id, "연결된 실제 배포 task 완료를 기다리는 중입니다.")
            task_manager.update_progress(task_id, 25.0, text="Waiting for linked deploy", source="phase")
            deploy_task = None
            for _ in range(5):
                deploy_task = task_manager.get_task_detail(deploy_task_id)
                if deploy_task is not None:
                    break
                time.sleep(0.2)
            if deploy_task is None:
                raise RuntimeError(f"Linked deploy task {deploy_task_id} was not found.")

            deploy_status = str(deploy_task.get("status") or "").lower()
            deploy_progress = float(deploy_task.get("progress") or 0.0)
            task_manager.append_log(
                task_id,
                f"실제 인프라 배포 task 상태: {deploy_task.get('status')} (task_id: {deploy_task_id})",
            )
            task_manager.update_progress(
                task_id,
                min(95.0, max(30.0, deploy_progress)),
                text="Linked staging deploy completed",
                source="phase",
            )
            task_manager.update_metadata(
                task_id,
                {
                    "request_recorded_at": self._now_iso(),
                    "execution_mode": "manual_staging_app_deploy",
                    "infra_execution": "completed" if deploy_status == "success" else "failed",
                    "linked_deploy_task_id": deploy_task_id,
                    "linked_deploy_status": deploy_task.get("status"),
                    "app_deploy_enabled": True,
                },
            )
            task_manager.append_log(
                task_id,
                "이 slice는 manual staging app deploy 입니다. 인프라 프로비저닝 뒤 docker-compose 앱 배포까지 수행했고, DB 자동화는 제외했습니다.",
            )
            if deploy_status == "success":
                task_manager.update_progress(
                    task_id,
                    100.0,
                    text="Linked staging deploy completed",
                    source="phase",
                )
                task_manager.update_status(task_id, TaskStatus.SUCCESS)
                task_manager.append_log(task_id, "=== GitLab staging deploy wrapper 완료 ===")
                return

            task_manager.update_status(task_id, TaskStatus.FAILED)
            task_manager.append_log(
                task_id,
                "GitLab staging wrapper 실패: linked staging deploy task did not succeed.",
            )
        except Exception as exc:
            task_manager.update_status(task_id, TaskStatus.FAILED)
            task_manager.append_log(
                task_id,
                f"GitLab staging wrapper 실패: {exc}",
            )

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

    def _seed_project_manifest_draft(
        self,
        *,
        settings: GitLabSettings,
        project_payload: dict[str, Any],
        initialize_with_readme: bool,
    ) -> dict[str, Any]:
        if not initialize_with_readme:
            return {"seeded": False, "message": None}

        project_id = project_payload.get("id")
        default_branch = str(project_payload.get("default_branch") or "").strip()
        if project_id is None or not default_branch:
            return {
                "seeded": False,
                "message": (
                    "프로젝트는 생성되었지만 기본 브랜치를 확인할 수 없어 "
                    ".heimdall/project.yaml draft는 자동 생성하지 못했습니다."
                ),
            }

        session = self._create_gitlab_session(settings)
        encoded_path = quote(MANIFEST_FILE_PATH, safe="")
        url = urljoin(
            f"{settings.base_url}/",
            f"api/v4/projects/{int(project_id)}/repository/files/{encoded_path}",
        )
        content = self._build_project_manifest_draft(project_payload)

        try:
            self._request_gitlab(
                session=session,
                method="POST",
                url=url,
                settings=settings,
                data={
                    "branch": default_branch,
                    "content": content,
                    "commit_message": "Add Heimdall bootstrap draft manifest",
                },
                error_cls=GitLabProjectCreateError,
            )
            return {
                "seeded": True,
                "message": (
                    "기본 .heimdall/project.yaml draft를 생성했습니다. "
                    "이 초안은 아직 deploy-ready가 아니며 "
                    "runtime, deploy.compose_file, deploy.app_port, "
                    "deploy.healthcheck_path를 repo에서 채워야 합니다."
                ),
            }
        except GitLabProjectCreateError as exc:
            return {
                "seeded": False,
                "message": (
                    "프로젝트는 생성되었지만 .heimdall/project.yaml draft 자동 생성에는 실패했습니다: "
                    f"{exc}"
                ),
            }

    def _build_project_manifest_draft(self, project_payload: dict[str, Any]) -> str:
        manifest_name = str(project_payload.get("path") or project_payload.get("name") or "app").strip()
        payload = {
            "name": manifest_name,
            "runtime": "unknown",
            "deploy": {
                "strategy": "docker-compose",
            },
            "database": {
                "required": False,
            },
            "environments": {
                "staging": {
                    "enabled": True,
                }
            },
        }
        content = yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
        )
        return (
            "# Heimdall bootstrap draft\n"
            "# This draft is intentionally incomplete.\n"
            "# Fill runtime, deploy.compose_file, deploy.app_port, and deploy.healthcheck_path\n"
            "# before relying on this manifest for app deployment.\n"
            "# Example placeholders:\n"
            "# deploy:\n"
            "#   compose_file: deploy/docker-compose.yml\n"
            "#   app_port: 3000\n"
            "#   healthcheck_path: /health\n\n"
            f"{content}"
        )

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
        staging_server_name = self._normalize_optional_string(payload.get("staging_server_name"))
        staging_server_id = self._normalize_optional_string(payload.get("staging_server_id"))
        staging_template_id = self._normalize_optional_string(payload.get("staging_template_id"))
        staging_storage_id = self._normalize_optional_string(payload.get("staging_storage_id"))
        staging_network_ids = self._normalize_string_list(payload.get("staging_network_ids"))
        staging_cpu_cores = self._normalize_optional_positive_int(
            payload.get("staging_cpu_cores"),
            "staging_cpu_cores",
        )
        staging_memory_gb = self._normalize_optional_positive_int(
            payload.get("staging_memory_gb"),
            "staging_memory_gb",
        )
        staging_disk_size_gb = self._normalize_optional_positive_int(
            payload.get("staging_disk_size_gb"),
            "staging_disk_size_gb",
        )
        staging_vm_ip = self._normalize_optional_string(payload.get("staging_vm_ip"))
        staging_vm_gateway = self._normalize_optional_string(payload.get("staging_vm_gateway"))
        staging_ansible_packages = self._normalize_string_list(payload.get("staging_ansible_packages"))
        staging_ansible_roles = self._normalize_string_list(payload.get("staging_ansible_roles"))
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

        if bool(staging_vm_ip) != bool(staging_vm_gateway):
            raise GitLabProjectSettingsError(
                "staging_vm_ip and staging_vm_gateway must be provided together."
            )
        if staging_vm_ip is not None and staging_vm_gateway is not None:
            self._validate_static_network_pair(staging_vm_ip, staging_vm_gateway)

        return {
            "staging_enabled": staging_enabled,
            "ready_for_bootstrap": ready_for_bootstrap,
            "database_required": database_required,
            "database_engine": database_engine,
            "database_mode": database_mode,
            "migration_command": migration_command,
            "deploy_branch": deploy_branch,
            "bootstrap_strategy": bootstrap_strategy,
            "staging_server_name": staging_server_name,
            "staging_server_id": staging_server_id,
            "staging_template_id": staging_template_id,
            "staging_storage_id": staging_storage_id,
            "staging_network_ids": staging_network_ids,
            "staging_cpu_cores": staging_cpu_cores,
            "staging_memory_gb": staging_memory_gb,
            "staging_disk_size_gb": staging_disk_size_gb,
            "staging_vm_ip": staging_vm_ip,
            "staging_vm_gateway": staging_vm_gateway,
            "staging_ansible_packages": staging_ansible_packages,
            "staging_ansible_roles": staging_ansible_roles,
            "notes": notes,
        }

    def _serialize_project(
        self,
        project: GitLabProject,
        project_settings: GitLabProjectSettings | None,
        manifest_context: dict[str, Any],
    ) -> dict[str, Any]:
        manifest = self._load_project_manifest_status(
            project=project,
            manifest_context=manifest_context,
            ref=self._resolve_manifest_ref(project, project_settings),
        )
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
            "manifest_status": manifest["manifest_status"],
            "manifest_summary": manifest["manifest_summary"],
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
            "staging_server_name": project_settings.staging_server_name,
            "staging_server_id": project_settings.staging_server_id,
            "staging_template_id": project_settings.staging_template_id,
            "staging_storage_id": project_settings.staging_storage_id,
            "staging_network_ids": list(project_settings.staging_network_ids or []),
            "staging_cpu_cores": project_settings.staging_cpu_cores,
            "staging_memory_gb": project_settings.staging_memory_gb,
            "staging_disk_size_gb": project_settings.staging_disk_size_gb,
            "staging_vm_ip": project_settings.staging_vm_ip,
            "staging_vm_gateway": project_settings.staging_vm_gateway,
            "staging_ansible_packages": list(project_settings.staging_ansible_packages or []),
            "staging_ansible_roles": list(project_settings.staging_ansible_roles or []),
            "updated_at": project_settings.updated_at,
        }

    def _serialize_project_settings_detail(
        self,
        project: GitLabProject,
        project_id: int,
        project_settings: GitLabProjectSettings | None,
        manifest_context: dict[str, Any],
    ) -> dict[str, Any]:
        summary = self._serialize_project_settings_summary(project_settings)
        manifest = self._load_project_manifest_status(
            project=project,
            manifest_context=manifest_context,
            ref=self._resolve_manifest_ref(project, project_settings),
        )
        return {
            "gitlab_project_id": project_id,
            "configuration_status": self._derive_configuration_status(project_settings),
            "manifest_status": manifest["manifest_status"],
            "manifest_summary": manifest["manifest_summary"],
            "staging_enabled": project_settings.staging_enabled if project_settings is not None else False,
            "ready_for_bootstrap": project_settings.ready_for_bootstrap if project_settings is not None else False,
            "database_required": project_settings.database_required if project_settings is not None else False,
            "database_engine": project_settings.database_engine if project_settings is not None else None,
            "database_mode": project_settings.database_mode if project_settings is not None else None,
            "migration_command": project_settings.migration_command if project_settings is not None else None,
            "deploy_branch": project_settings.deploy_branch if project_settings is not None else "main",
            "bootstrap_strategy": project_settings.bootstrap_strategy if project_settings is not None else "merge_request",
            "staging_server_name": project_settings.staging_server_name if project_settings is not None else None,
            "staging_server_id": project_settings.staging_server_id if project_settings is not None else None,
            "staging_template_id": project_settings.staging_template_id if project_settings is not None else None,
            "staging_storage_id": project_settings.staging_storage_id if project_settings is not None else None,
            "staging_network_ids": list(project_settings.staging_network_ids or []) if project_settings is not None else [],
            "staging_cpu_cores": project_settings.staging_cpu_cores if project_settings is not None else None,
            "staging_memory_gb": project_settings.staging_memory_gb if project_settings is not None else None,
            "staging_disk_size_gb": project_settings.staging_disk_size_gb if project_settings is not None else None,
            "staging_vm_ip": project_settings.staging_vm_ip if project_settings is not None else None,
            "staging_vm_gateway": project_settings.staging_vm_gateway if project_settings is not None else None,
            "staging_ansible_packages": list(project_settings.staging_ansible_packages or []) if project_settings is not None else [],
            "staging_ansible_roles": list(project_settings.staging_ansible_roles or []) if project_settings is not None else [],
            "notes": project_settings.notes if project_settings is not None else None,
            "updated_at": project_settings.updated_at if project_settings is not None else None,
            "settings_summary": summary,
        }

    def _resolve_manifest_ref(
        self,
        project: GitLabProject,
        project_settings: GitLabProjectSettings | None,
    ) -> str:
        deploy_branch = (
            str(project_settings.deploy_branch).strip()
            if project_settings is not None
            else ""
        )
        if deploy_branch:
            return deploy_branch
        default_branch = str(project.default_branch or "").strip()
        return default_branch or "HEAD"

    def _derive_configuration_status(
        self,
        project_settings: GitLabProjectSettings | None,
    ) -> str:
        if project_settings is None:
            return "discovered"
        if project_settings.ready_for_bootstrap:
            return "ready_for_bootstrap"
        return "configured"

    def _create_manifest_lookup_context(self, settings: GitLabSettings) -> dict[str, Any]:
        if settings.validation_error is not None:
            return {
                "available": False,
                "error": f"GitLab configuration unavailable: {settings.validation_error}",
            }
        if not settings.api_token:
            return {
                "available": False,
                "error": "GitLab configuration unavailable: GITLAB_API_TOKEN is not configured.",
            }

        return {
            "available": True,
            "settings": settings,
            "session": self._create_gitlab_session(settings),
        }

    def _normalize_optional_string(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    def _normalize_optional_positive_int(self, value: Any, field_name: str) -> int | None:
        if value in (None, ""):
            return None
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise GitLabProjectSettingsError(f"{field_name} must be a positive integer.") from exc
        if normalized <= 0:
            raise GitLabProjectSettingsError(f"{field_name} must be a positive integer.")
        return normalized

    def _normalize_string_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            raw_items = value.replace("\n", ",").split(",")
        elif isinstance(value, list):
            raw_items = value
        else:
            raise GitLabProjectSettingsError(
                "List fields must be arrays or comma-separated strings."
            )

        normalized: list[str] = []
        for item in raw_items:
            text = str(item or "").strip()
            if text:
                normalized.append(text)
        return normalized

    def _validate_static_network_pair(self, vm_ip: str, vm_gateway: str) -> None:
        if "/" not in vm_ip:
            raise GitLabProjectSettingsError(
                "staging_vm_ip must be an IPv4 host CIDR like 192.168.2.100/24."
            )

        try:
            parsed_ip = ip_interface(vm_ip)
        except ValueError as exc:
            raise GitLabProjectSettingsError(
                "staging_vm_ip must be an IPv4 host CIDR like 192.168.2.100/24."
            ) from exc

        if not isinstance(parsed_ip, IPv4Interface):
            raise GitLabProjectSettingsError(
                "staging_vm_ip must be an IPv4 host CIDR like 192.168.2.100/24."
            )

        try:
            parsed_gateway = ip_address(vm_gateway)
        except ValueError as exc:
            raise GitLabProjectSettingsError(
                "staging_vm_gateway must be a valid IPv4 address like 192.168.2.1."
            ) from exc

        if not isinstance(parsed_gateway, IPv4Address):
            raise GitLabProjectSettingsError(
                "staging_vm_gateway must be a valid IPv4 address like 192.168.2.1."
            )

    def _load_project_manifest_status(
        self,
        project: GitLabProject,
        manifest_context: dict[str, Any],
        ref: str | None = None,
    ) -> dict[str, str]:
        manifest = self._load_project_manifest(
            project=project,
            manifest_context=manifest_context,
            ref=ref,
        )
        return {
            "manifest_status": str(manifest["manifest_status"]),
            "manifest_summary": str(manifest["manifest_summary"]),
        }

    def _load_project_manifest(
        self,
        project: GitLabProject,
        manifest_context: dict[str, Any],
        ref: str | None = None,
    ) -> dict[str, Any]:
        if not manifest_context.get("available"):
            return {
                "manifest_status": "unchecked",
                "manifest_summary": str(
                    manifest_context.get("error") or "GitLab manifest validation is unavailable."
                ),
                "manifest_payload": None,
            }

        settings = manifest_context["settings"]
        session = manifest_context["session"]
        encoded_path = quote(MANIFEST_FILE_PATH, safe="")
        resolved_ref = str(ref or project.default_branch or "HEAD").strip() or "HEAD"
        url = urljoin(
            f"{settings.base_url}/",
            f"api/v4/projects/{project.gitlab_project_id}/repository/files/{encoded_path}/raw",
        )

        try:
            response = session.request(
                method="GET",
                url=url,
                params={"ref": resolved_ref},
                timeout=(5, 30),
                verify=settings.verify_ssl,
            )
            if response.status_code == 404:
                return {
                    "manifest_status": "missing",
                    "manifest_summary": f"{MANIFEST_FILE_PATH} was not found on ref {resolved_ref}.",
                    "manifest_payload": None,
                }
            response.raise_for_status()
        except requests.RequestException as exc:
            return {
                "manifest_status": "unchecked",
                "manifest_summary": self._map_gitlab_request_error(exc),
                "manifest_payload": None,
            }

        try:
            payload = yaml.safe_load(response.text)
        except yaml.YAMLError as exc:
            return {
                "manifest_status": "invalid",
                "manifest_summary": f"{MANIFEST_FILE_PATH} YAML parse error: {exc}",
                "manifest_payload": None,
            }

        validation_error = self._validate_manifest_payload(payload)
        if validation_error is not None:
            return {
                "manifest_status": "invalid",
                "manifest_summary": validation_error,
                "manifest_payload": payload,
            }

        return {
            "manifest_status": "valid",
            "manifest_summary": f"{MANIFEST_FILE_PATH} passed the minimum staging validation on ref {resolved_ref}.",
            "manifest_payload": payload,
        }

    def _validate_manifest_payload(self, payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return f"{MANIFEST_FILE_PATH} must contain a YAML object."

        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            return "Manifest validation failed: top-level name must be a non-empty string."

        runtime = payload.get("runtime")
        if not isinstance(runtime, str) or not runtime.strip():
            return "Manifest validation failed: top-level runtime must be a non-empty string."

        deploy = payload.get("deploy")
        if not isinstance(deploy, dict) or deploy.get("strategy") != "docker-compose":
            return "Manifest validation failed: deploy.strategy must be docker-compose."
        compose_file = self._normalize_compose_file_path(deploy.get("compose_file"))
        if compose_file is None:
            return "Manifest validation failed: deploy.compose_file must be a non-empty string."
        if compose_file.startswith("/") or ".." in PurePosixPath(compose_file).parts:
            return (
                "Manifest validation failed: deploy.compose_file must be a relative repo path "
                "without '..'."
            )
        app_port = deploy.get("app_port")
        if isinstance(app_port, bool) or not isinstance(app_port, int) or app_port <= 0:
            return "Manifest validation failed: deploy.app_port must be a positive integer."
        healthcheck_path = deploy.get("healthcheck_path")
        if (
            not isinstance(healthcheck_path, str)
            or not healthcheck_path.strip()
            or not healthcheck_path.startswith("/")
        ):
            return (
                "Manifest validation failed: deploy.healthcheck_path must be "
                "a non-empty path starting with /."
            )

        environments = payload.get("environments")
        staging = environments.get("staging") if isinstance(environments, dict) else None
        if not isinstance(staging, dict) or staging.get("enabled") is not True:
            return "Manifest validation failed: environments.staging.enabled must be true."

        database = payload.get("database")
        if isinstance(database, dict) and database.get("required") is True:
            if database.get("engine") != "postgres":
                return "Manifest validation failed: database.engine must be postgres when database.required is true."

        return None

    def _normalize_compose_file_path(self, value: Any) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        normalized = str(PurePosixPath(raw))
        if normalized in {"", "."}:
            return None
        return normalized

    def _build_app_project_slug(self, value: str) -> str:
        lowered = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
        normalized = lowered.strip("-")
        if not normalized:
            normalized = "heimdall-app"
        return normalized[:48]

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
