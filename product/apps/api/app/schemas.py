from __future__ import annotations

from typing import Literal, Optional

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
    base_url_configured: Optional[bool] = None
    base_url: Optional[str] = None


class ProvidersStatus(BaseModel):
    public_base_url: str
    webhook_urls: dict[str, str]
    public_base_url_usable: bool
    public_base_url_message: str
    providers: dict[str, ProviderReadiness]


class RepoValidationRequest(BaseModel):
    repo_url: str = Field(min_length=1, max_length=500)
    provider: Optional[Provider] = None


class RepoValidationRead(BaseModel):
    provider: str
    repo_url: str
    normalized_repo: str
    provider_project_id: str
    full_name: str
    default_branch: Optional[str]
    private: bool
    access_valid: bool
    can_register_webhook: bool
    message: str


class WebhookRegistrationRead(BaseModel):
    provider: str
    status: str
    webhook_url: str
    provider_project_id: str
    provider_webhook_id: Optional[str] = None
    active: bool = False
    events: list[str] = Field(default_factory=list)
    registered_at: Optional[str] = None
    updated_at: Optional[str] = None
    message: str


class ProjectDatabaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: bool = False
    type: Literal["postgres"] = "postgres"
    env_var: str = Field(default="DATABASE_URL", pattern=r"^[A-Z_][A-Z0-9_]*$", max_length=63)


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    slug: Optional[str] = Field(default=None, max_length=63)
    provider: Provider
    repo_url: str = Field(min_length=1, max_length=500)
    default_branch: str = Field(default="main", min_length=1, max_length=120)
    tracked_branch: str = Field(default="main", min_length=1, max_length=120)
    deploy_mode: DeployMode = DeployMode.DOCKERFILE
    build_context_path: str = Field(default=".", max_length=255)
    dockerfile_path: Optional[str] = Field(default="Dockerfile", max_length=255)
    compose_file_path: Optional[str] = Field(default=None, max_length=255)
    container_port: Optional[int] = None
    preview_port: Optional[int] = None
    health_check_path: Optional[str] = Field(default=None, max_length=255)
    health_check_url: Optional[str] = Field(default=None, max_length=500)
    auto_deploy_enabled: bool = False
    volumes: Optional[list["ProjectServiceVolumeConfig"]] = None
    services: Optional[list["ProjectServiceConfig"]] = None
    database: Optional[ProjectDatabaseConfig] = None


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    slug: Optional[str] = Field(default=None, max_length=63)
    provider: Optional[Provider] = None
    repo_url: Optional[str] = Field(default=None, min_length=1, max_length=500)
    default_branch: Optional[str] = Field(default=None, min_length=1, max_length=120)
    tracked_branch: Optional[str] = Field(default=None, min_length=1, max_length=120)
    deploy_mode: Optional[DeployMode] = None
    build_context_path: Optional[str] = Field(default=None, max_length=255)
    dockerfile_path: Optional[str] = Field(default=None, max_length=255)
    compose_file_path: Optional[str] = Field(default=None, max_length=255)
    container_port: Optional[int] = None
    preview_port: Optional[int] = None
    health_check_path: Optional[str] = Field(default=None, max_length=255)
    health_check_url: Optional[str] = Field(default=None, max_length=500)
    auto_deploy_enabled: Optional[bool] = None
    status: Optional[Literal["disabled"]] = None
    volumes: Optional[list["ProjectServiceVolumeConfig"]] = None
    services: Optional[list["ProjectServiceConfig"]] = None
    database: Optional[ProjectDatabaseConfig] = None


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
    health_check_path: Optional[str] = Field(default="/", max_length=255)
    startup_order: int = 0
    build_env: dict[str, str] = Field(default_factory=dict)
    runtime_env: dict[str, str] = Field(default_factory=dict)
    required_secrets: list[str] = Field(default_factory=list)
    volumes: list[ProjectServiceVolumeConfig] = Field(default_factory=list)


class ProjectServiceRead(ProjectServiceConfig):
    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = None
    volumes: list[ProjectServiceVolumeRead] = Field(default_factory=list)


class ProjectServiceEnvBundleWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str


class ProjectServiceEnvBundleRead(BaseModel):
    id: Optional[str] = None
    project_id: str
    service_id: str
    configured: bool
    key_names: list[str] = Field(default_factory=list)
    checksum_sha256: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectDatabaseRead(BaseModel):
    id: str
    required: bool
    type: Literal["postgres"]
    env_var: str
    status: str
    app_host: str
    app_port: int
    network_name: str
    retention_policy: str
    orphaned_at: Optional[str] = None
    provisioned_at: Optional[str] = None
    last_error: Optional[str] = None


class ProjectDatabasePurgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database_id: str = Field(min_length=1)
    confirmation: Literal["purge managed project database"]


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
    dockerfile_path: Optional[str]
    compose_file_path: Optional[str]
    container_port: int
    preview_host: str
    preview_port: int
    preview_url: str
    health_check_path: Optional[str]
    health_check_url: Optional[str]
    auto_deploy_enabled: bool
    status: str
    current_release_id: Optional[str]
    current_commit_sha: Optional[str]
    created_at: str
    updated_at: str
    last_deployment_id: Optional[str] = None
    last_deployment_status: Optional[str] = None
    last_deployment_at: Optional[str] = None
    has_real_preview: bool
    services: list[ProjectServiceRead] = Field(default_factory=list)
    database: Optional[ProjectDatabaseRead] = None
    webhook_registration: Optional[WebhookRegistrationRead] = None


class DeploymentRequest(BaseModel):
    ref: Optional[str] = Field(default=None, max_length=255)
    commit_sha: Optional[str] = Field(default=None, max_length=64)
    trigger_type: TriggerType = TriggerType.MANUAL
    dry_run: bool = False


class DeploymentRead(BaseModel):
    id: str
    project_id: str
    trigger_type: str
    requested_ref: Optional[str]
    requested_commit_sha: Optional[str]
    resolved_commit_sha: Optional[str]
    image_tag: Optional[str]
    previous_release_id: Optional[str]
    target_release_id: Optional[str]
    status: str
    status_message: Optional[str]
    is_dry_run: bool
    started_at: Optional[str]
    finished_at: Optional[str]
    duration_ms: Optional[int]
    log_path: Optional[str]
    created_at: str


class ReleaseRead(BaseModel):
    id: str
    project_id: str
    deployment_id: str
    commit_sha: str
    short_commit_sha: str
    image_tag: str
    image_id: Optional[str]
    status: str
    is_current: bool
    is_dry_run: bool
    created_at: str
    activated_at: Optional[str]
    last_used_at: Optional[str]
    rollback_supported: bool
    services: list["ReleaseServiceRead"] = Field(default_factory=list)


class ReleaseServiceRead(BaseModel):
    name: str
    image_tag: str
    image_id: Optional[str] = None
    container_name: Optional[str] = None
    container_port: int
    public: bool
    preview_url: Optional[str] = None
    internal_url: Optional[str] = None
    status: str


class DeploymentResult(BaseModel):
    deployment: DeploymentRead
    release: Optional[ReleaseRead] = None


class DeploymentLogsRead(BaseModel):
    deployment_id: str
    log_path: Optional[str]
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
    event_type: Optional[str]
    delivery_id: Optional[str]
    project_id: Optional[str]
    branch: Optional[str]
    commit_sha: Optional[str]
    status: str
    received_at: str
    deployment_id: Optional[str]
    error_message: Optional[str]


class WebhookResponse(BaseModel):
    status: str
    webhook_event: WebhookEventRead
    deployment: Optional[DeploymentRead] = None
