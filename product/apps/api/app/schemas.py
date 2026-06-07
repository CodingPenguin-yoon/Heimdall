from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import DeployMode, Provider, TriggerType


class ProviderReadiness(BaseModel):
    provider: str
    token_configured: bool
    webhook_secret_configured: bool
    ready: bool
    can_validate_repo: bool
    can_register_webhook: bool
    message: str
    base_url_configured: bool | None = None
    base_url: str | None = None


class ProvidersStatus(BaseModel):
    public_base_url: str
    webhook_urls: dict[str, str]
    public_base_url_usable: bool
    public_base_url_message: str
    providers: dict[str, ProviderReadiness]


class RepoValidationRequest(BaseModel):
    repo_url: str = Field(min_length=1, max_length=500)
    provider: Provider | None = None


class RepoValidationRead(BaseModel):
    provider: str
    repo_url: str
    normalized_repo: str
    provider_project_id: str
    full_name: str
    default_branch: str | None
    private: bool
    access_valid: bool
    can_register_webhook: bool
    message: str


class WebhookRegistrationRead(BaseModel):
    provider: str
    status: str
    webhook_url: str
    provider_project_id: str
    provider_webhook_id: str | None = None
    active: bool = False
    events: list[str] = Field(default_factory=list)
    registered_at: str | None = None
    updated_at: str | None = None
    message: str


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=63)
    provider: Provider
    repo_url: str = Field(min_length=1, max_length=500)
    default_branch: str = Field(default="main", min_length=1, max_length=120)
    tracked_branch: str = Field(default="main", min_length=1, max_length=120)
    deploy_mode: DeployMode = DeployMode.DOCKERFILE
    build_context_path: str = Field(default=".", max_length=255)
    dockerfile_path: str | None = Field(default="Dockerfile", max_length=255)
    compose_file_path: str | None = Field(default=None, max_length=255)
    container_port: int | None = None
    preview_port: int | None = None
    health_check_path: str | None = Field(default=None, max_length=255)
    health_check_url: str | None = Field(default=None, max_length=500)
    auto_deploy_enabled: bool = False
    run_as_heimdall_child: bool = False
    volumes: list["ProjectServiceVolumeConfig"] | None = None
    services: list["ProjectServiceConfig"] | None = None


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=63)
    provider: Provider | None = None
    repo_url: str | None = Field(default=None, min_length=1, max_length=500)
    default_branch: str | None = Field(default=None, min_length=1, max_length=120)
    tracked_branch: str | None = Field(default=None, min_length=1, max_length=120)
    deploy_mode: DeployMode | None = None
    build_context_path: str | None = Field(default=None, max_length=255)
    dockerfile_path: str | None = Field(default=None, max_length=255)
    compose_file_path: str | None = Field(default=None, max_length=255)
    container_port: int | None = None
    preview_port: int | None = None
    health_check_path: str | None = Field(default=None, max_length=255)
    health_check_url: str | None = Field(default=None, max_length=500)
    auto_deploy_enabled: bool | None = None
    run_as_heimdall_child: bool | None = None
    status: Literal["disabled"] | None = None
    volumes: list["ProjectServiceVolumeConfig"] | None = None
    services: list["ProjectServiceConfig"] | None = None


class ProjectServiceVolumeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=63)
    target_path: str = Field(min_length=1, max_length=255)
    read_only: bool = False


class ProjectServiceVolumeRead(BaseModel):
    id: str
    name: str
    target_path: str
    read_only: bool
    source_relative_path: str
    status: str


class ProjectServiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=63)
    build_context_path: str = Field(default=".", max_length=255)
    dockerfile_path: str = Field(default="Dockerfile", max_length=255)
    container_port: int
    public: bool = False
    health_check_path: str | None = Field(default="/", max_length=255)
    startup_order: int = 0
    build_env: dict[str, str] = Field(default_factory=dict)
    runtime_env: dict[str, str] = Field(default_factory=dict)
    required_secrets: list[str] = Field(default_factory=list)
    volumes: list[ProjectServiceVolumeConfig] = Field(default_factory=list)
    run_as_heimdall_child: bool = False


class ProjectServiceRead(ProjectServiceConfig):
    model_config = ConfigDict(extra="ignore")

    volumes: list[ProjectServiceVolumeRead] = Field(default_factory=list)


class ProjectRead(BaseModel):
    id: str
    name: str
    slug: str
    provider: str
    repo_url: str
    default_branch: str
    tracked_branch: str
    deploy_mode: str
    build_context_path: str
    dockerfile_path: str | None
    compose_file_path: str | None
    container_port: int
    preview_host: str
    preview_port: int
    preview_url: str
    health_check_path: str | None
    health_check_url: str | None
    auto_deploy_enabled: bool
    run_as_heimdall_child: bool
    status: str
    current_release_id: str | None
    current_commit_sha: str | None
    created_at: str
    updated_at: str
    last_deployment_id: str | None = None
    last_deployment_status: str | None = None
    last_deployment_at: str | None = None
    has_real_preview: bool
    services: list[ProjectServiceRead] = Field(default_factory=list)
    webhook_registration: WebhookRegistrationRead | None = None


class DeploymentRequest(BaseModel):
    ref: str | None = Field(default=None, max_length=255)
    commit_sha: str | None = Field(default=None, max_length=64)
    trigger_type: TriggerType = TriggerType.MANUAL
    dry_run: bool = False


class DeploymentRead(BaseModel):
    id: str
    project_id: str
    trigger_type: str
    requested_ref: str | None
    requested_commit_sha: str | None
    resolved_commit_sha: str | None
    image_tag: str | None
    previous_release_id: str | None
    target_release_id: str | None
    status: str
    status_message: str | None
    is_dry_run: bool
    started_at: str | None
    finished_at: str | None
    duration_ms: int | None
    log_path: str | None
    created_at: str


class ReleaseRead(BaseModel):
    id: str
    project_id: str
    deployment_id: str
    commit_sha: str
    short_commit_sha: str
    image_tag: str
    image_id: str | None
    status: str
    is_current: bool
    is_dry_run: bool
    created_at: str
    activated_at: str | None
    last_used_at: str | None
    rollback_supported: bool
    services: list["ReleaseServiceRead"] = Field(default_factory=list)


class ReleaseServiceRead(BaseModel):
    name: str
    image_tag: str
    image_id: str | None = None
    container_name: str | None = None
    container_port: int
    public: bool
    preview_url: str | None = None
    internal_url: str | None = None
    status: str


class DeploymentResult(BaseModel):
    deployment: DeploymentRead
    release: ReleaseRead | None = None


class DeploymentLogsRead(BaseModel):
    deployment_id: str
    log_path: str | None
    content: str


class RollbackRequest(BaseModel):
    release_id: str = Field(min_length=1, max_length=120)


class RollbackResponse(BaseModel):
    supported: bool
    message: str
    deployment: DeploymentRead


class WebhookEventRead(BaseModel):
    id: str
    provider: str
    event_type: str | None
    delivery_id: str | None
    project_id: str | None
    branch: str | None
    commit_sha: str | None
    status: str
    received_at: str
    deployment_id: str | None
    error_message: str | None


class WebhookResponse(BaseModel):
    status: str
    webhook_event: WebhookEventRead
    deployment: DeploymentRead | None = None
