"""GitLab inventory API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domains.gitlab.service import (
    GitLabConfigurationError,
    GitLabInventoryService,
    GitLabProjectCreateError,
    GitLabProjectNotFoundError,
    GitLabProjectSettingsError,
    GitLabSyncError,
)


router = APIRouter()
gitlab_inventory_service = GitLabInventoryService()


class GitLabProjectResponse(BaseModel):
    gitlab_project_id: int
    name: str
    path_with_namespace: str
    web_url: str
    http_url_to_repo: str
    ssh_url_to_repo: str | None = None
    default_branch: str | None = None
    visibility: str
    archived: bool
    last_activity_at: str | None = None
    synced_at: str
    configuration_status: str
    settings_summary: dict[str, Any] | None = None


class GitLabProjectsListResponse(BaseModel):
    configured: bool
    can_sync: bool
    default_namespace_path: str
    configuration_error: str | None = None
    projects: list[GitLabProjectResponse] = Field(default_factory=list)
    last_sync: dict[str, Any] | None = None


class GitLabProjectsSyncResponse(BaseModel):
    status: str
    project_count: int
    updated_at: str


class GitLabNamespaceResponse(BaseModel):
    id: int
    name: str
    path: str
    full_path: str
    kind: str
    web_url: str


class GitLabNamespacesListResponse(BaseModel):
    namespaces: list[GitLabNamespaceResponse] = Field(default_factory=list)


class GitLabProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    path: str | None = None
    description: str | None = None
    visibility: str = "private"
    initialize_with_readme: bool = False
    default_branch: str | None = None


class GitLabProjectCreateResponse(BaseModel):
    project: GitLabProjectResponse


class GitLabProjectSettingsResponse(BaseModel):
    gitlab_project_id: int
    configuration_status: str
    staging_enabled: bool
    ready_for_bootstrap: bool
    database_required: bool
    database_engine: str | None = None
    database_mode: str | None = None
    migration_command: str | None = None
    deploy_branch: str
    bootstrap_strategy: str
    notes: str | None = None
    updated_at: str | None = None
    settings_summary: dict[str, Any] | None = None


class GitLabProjectSettingsUpdateRequest(BaseModel):
    staging_enabled: bool = False
    ready_for_bootstrap: bool = False
    database_required: bool = False
    database_engine: str | None = None
    database_mode: str | None = None
    migration_command: str | None = None
    deploy_branch: str = "main"
    bootstrap_strategy: str = "merge_request"
    notes: str | None = None


@router.get("/gitlab/projects", response_model=GitLabProjectsListResponse)
async def get_gitlab_projects() -> GitLabProjectsListResponse:
    return GitLabProjectsListResponse(**gitlab_inventory_service.list_projects())


@router.get("/gitlab/namespaces", response_model=GitLabNamespacesListResponse)
async def get_gitlab_namespaces() -> GitLabNamespacesListResponse:
    try:
        return GitLabNamespacesListResponse(namespaces=gitlab_inventory_service.list_namespaces())
    except GitLabConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitLabSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/gitlab/projects", response_model=GitLabProjectCreateResponse, status_code=201)
async def create_gitlab_project(payload: GitLabProjectCreateRequest) -> GitLabProjectCreateResponse:
    try:
        return GitLabProjectCreateResponse(**gitlab_inventory_service.create_project(payload.model_dump()))
    except GitLabConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitLabProjectCreateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/gitlab/projects/{project_id}/settings", response_model=GitLabProjectSettingsResponse)
async def get_gitlab_project_settings(project_id: int) -> GitLabProjectSettingsResponse:
    try:
        return GitLabProjectSettingsResponse(
            **gitlab_inventory_service.get_project_settings(project_id)
        )
    except GitLabProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GitLabProjectSettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/gitlab/projects/{project_id}/settings", response_model=GitLabProjectSettingsResponse)
async def update_gitlab_project_settings(
    project_id: int,
    payload: GitLabProjectSettingsUpdateRequest,
) -> GitLabProjectSettingsResponse:
    try:
        return GitLabProjectSettingsResponse(
            **gitlab_inventory_service.upsert_project_settings(project_id, payload.model_dump())
        )
    except GitLabProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GitLabProjectSettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/gitlab/projects/sync", response_model=GitLabProjectsSyncResponse)
async def sync_gitlab_projects() -> GitLabProjectsSyncResponse:
    try:
        return GitLabProjectsSyncResponse(**gitlab_inventory_service.sync_projects())
    except GitLabConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitLabSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


__all__ = ["router"]
