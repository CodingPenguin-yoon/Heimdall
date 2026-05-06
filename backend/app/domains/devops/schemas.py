"""Typed contracts for Heimdall DevOps MVP APIs."""

from __future__ import annotations

from enum import Enum
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EnvironmentName(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class LifecycleStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class RepoProvider(str, Enum):
    GITLAB = "gitlab"
    GITHUB = "github"
    LOCAL = "local"
    OTHER = "other"


class DeployStatus(str, Enum):
    NOT_DEPLOYED = "not_deployed"
    DEPLOYABLE = "deployable"
    BLOCKED = "blocked"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class DeploymentTargetKind(str, Enum):
    VM = "vm"
    HOST = "host"
    CONTAINER = "container"
    K8S_NAMESPACE = "k8s_namespace"
    EXTERNAL = "external"


class DeploymentTargetProvider(str, Enum):
    GJALLAR = "gjallar"
    MANUAL = "manual"
    GITLAB = "gitlab"
    OTHER = "other"


class DeploymentTargetScheme(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    SSH = "ssh"
    OTHER = "other"


class DeploymentTargetStatus(str, Enum):
    READY = "ready"
    DRAINING = "draining"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


class PipelineProvider(str, Enum):
    GITLAB = "gitlab"
    GITHUB_ACTIONS = "github_actions"
    LOCAL = "local"
    MANUAL = "manual"
    OTHER = "other"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    MANUAL = "manual"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"
    NOT_RUN = "not_run"


class DatabaseRole(str, Enum):
    PRIMARY = "primary"
    REPLICA = "replica"
    CACHE = "cache"
    QUEUE = "queue"
    OTHER = "other"


class DatabaseEngine(str, Enum):
    POSTGRES = "postgres"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    REDIS = "redis"
    OTHER = "other"


class ConnectionHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"
    NOT_CONFIGURED = "not_configured"


class MigrationStatus(str, Enum):
    UP_TO_DATE = "up_to_date"
    PENDING = "pending"
    FAILED = "failed"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class BackupStatus(str, Enum):
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"
    UNKNOWN = "unknown"
    NOT_CONFIGURED = "not_configured"


class RestoreReadiness(str, Enum):
    READY = "ready"
    NEEDS_TEST = "needs_test"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class DevOpsBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


SENSITIVE_QUERY_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "auth_token",
    "authorization",
    "client_secret",
    "password",
    "passwd",
    "private_token",
    "secret",
    "token",
}


def _normalize_sensitive_key(value: str) -> str:
    return "".join("_" if char in "-." else char for char in value.strip().lower())


def _reject_credentialed_url(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    parsed = urlsplit(value)
    if parsed.username or parsed.password:
        raise ValueError(f"{field_name} must not include credentials")
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = _normalize_sensitive_key(key)
        if normalized_key in SENSITIVE_QUERY_KEYS or any(
            normalized_key.endswith(f"_{sensitive_key}")
            for sensitive_key in SENSITIVE_QUERY_KEYS
        ):
            raise ValueError(f"{field_name} must not include credential query parameters")
    return value


def _reject_raw_secret_value(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    compact = normalized.replace(" ", "")
    if "://" in normalized or "@" in normalized:
        raise ValueError(f"{field_name} must be a secret reference, not a raw connection value")
    if "=" in compact:
        normalized_key = _normalize_sensitive_key(compact.split("=", 1)[0])
        if normalized_key in SENSITIVE_QUERY_KEYS or any(
            normalized_key.endswith(f"_{sensitive_key}")
            for sensitive_key in SENSITIVE_QUERY_KEYS
        ):
            raise ValueError(f"{field_name} must be a secret reference, not a raw secret assignment")
    return value


class DevOpsServiceCreateRequest(DevOpsBaseModel):
    service_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    owner_team: str | None = Field(default=None, max_length=255)
    repo_url: str = Field(min_length=1, max_length=2048)
    repo_provider: RepoProvider = RepoProvider.OTHER
    default_branch: str | None = Field(default=None, max_length=255)
    runtime: str | None = Field(default=None, max_length=128)
    framework: str | None = Field(default=None, max_length=128)
    health_status: HealthStatus = HealthStatus.UNKNOWN
    lifecycle_status: LifecycleStatus = LifecycleStatus.ACTIVE
    runbook_url: str | None = Field(default=None, max_length=2048)
    current_version: str | None = Field(default=None, max_length=255)
    current_commit: str | None = Field(default=None, max_length=128)
    labels: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=4096)

    @field_validator("repo_url", "runbook_url")
    @classmethod
    def url_fields_must_not_include_credentials(cls, value: str | None, info) -> str | None:
        return _reject_credentialed_url(value, info.field_name)


class DevOpsServiceResponse(DevOpsServiceCreateRequest):
    pass


class DevOpsServicesListResponse(DevOpsBaseModel):
    services: list[DevOpsServiceResponse] = Field(default_factory=list)
    total: int


class ServiceEnvironmentCreateRequest(DevOpsBaseModel):
    environment_id: str = Field(min_length=1, max_length=255)
    service_id: str = Field(min_length=1, max_length=128)
    environment: EnvironmentName
    enabled: bool = True
    url: str | None = Field(default=None, max_length=2048)
    branch: str | None = Field(default=None, max_length=255)
    desired_version: str | None = Field(default=None, max_length=255)
    deployed_version: str | None = Field(default=None, max_length=255)
    deployed_commit: str | None = Field(default=None, max_length=128)
    health_status: HealthStatus = HealthStatus.UNKNOWN
    deploy_status: DeployStatus = DeployStatus.NOT_DEPLOYED
    last_deployed_at: str | None = Field(default=None, max_length=128)
    labels: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=4096)

    @field_validator("url")
    @classmethod
    def url_must_not_include_credentials(cls, value: str | None) -> str | None:
        return _reject_credentialed_url(value, "url")


class ServiceEnvironmentResponse(ServiceEnvironmentCreateRequest):
    pass


class ServiceEnvironmentsListResponse(DevOpsBaseModel):
    environments: list[ServiceEnvironmentResponse] = Field(default_factory=list)
    total: int


class DeploymentTargetReferenceCreateRequest(DevOpsBaseModel):
    target_id: str = Field(min_length=1, max_length=255)
    environment_id: str = Field(min_length=1, max_length=255)
    target_kind: DeploymentTargetKind
    provider: DeploymentTargetProvider = DeploymentTargetProvider.MANUAL
    gjallar_ref: dict[str, Any] | None = None
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    scheme: DeploymentTargetScheme | None = None
    target_status: DeploymentTargetStatus = DeploymentTargetStatus.UNKNOWN
    capacity_note: str | None = Field(default=None, max_length=1024)
    labels: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=4096)


class DeploymentTargetReferenceResponse(DeploymentTargetReferenceCreateRequest):
    pass


class DeploymentTargetsListResponse(DevOpsBaseModel):
    deployment_targets: list[DeploymentTargetReferenceResponse] = Field(default_factory=list)
    total: int


class CiCdRunCreateRequest(DevOpsBaseModel):
    run_id: str = Field(min_length=1, max_length=255)
    service_id: str = Field(min_length=1, max_length=128)
    environment_id: str | None = Field(default=None, max_length=255)
    provider: PipelineProvider
    pipeline_url: str | None = Field(default=None, max_length=2048)
    commit_sha: str | None = Field(default=None, max_length=128)
    branch: str | None = Field(default=None, max_length=255)
    status: RunStatus = RunStatus.UNKNOWN
    stage: str | None = Field(default=None, max_length=128)
    build_status: RunStatus = RunStatus.NOT_RUN
    test_status: RunStatus = RunStatus.NOT_RUN
    lint_status: RunStatus = RunStatus.NOT_RUN
    deployable: bool = False
    failure_summary: str | None = Field(default=None, max_length=4096)
    started_at: str | None = Field(default=None, max_length=128)
    finished_at: str | None = Field(default=None, max_length=128)
    allowed_actions: list[str] = Field(default_factory=list)
    requires_user_approval: bool = False
    labels: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=4096)

    @field_validator("pipeline_url")
    @classmethod
    def pipeline_url_must_not_include_credentials(cls, value: str | None) -> str | None:
        return _reject_credentialed_url(value, "pipeline_url")


class CiCdRunResponse(CiCdRunCreateRequest):
    pass


class CiCdRunsListResponse(DevOpsBaseModel):
    ci_runs: list[CiCdRunResponse] = Field(default_factory=list)
    total: int


class CiCdActionPreviewResponse(DevOpsBaseModel):
    run_id: str
    action: str
    allowed: bool
    requires_user_approval: bool
    reason: str


class DatabaseStatusCreateRequest(DevOpsBaseModel):
    db_status_id: str = Field(min_length=1, max_length=255)
    environment_id: str = Field(min_length=1, max_length=255)
    database_role: DatabaseRole
    engine: DatabaseEngine
    version: str | None = Field(default=None, max_length=128)
    secret_ref: str | None = Field(default=None, max_length=512)
    host_ref: str | None = Field(default=None, max_length=255)
    connection_health: ConnectionHealth = ConnectionHealth.UNKNOWN
    migration_status: MigrationStatus = MigrationStatus.UNKNOWN
    pending_migration_count: int | None = Field(default=None, ge=0)
    backup_status: BackupStatus = BackupStatus.UNKNOWN
    restore_readiness: RestoreReadiness = RestoreReadiness.UNKNOWN
    last_checked_at: str | None = Field(default=None, max_length=128)
    last_backup_at: str | None = Field(default=None, max_length=128)
    summary: str | None = Field(default=None, max_length=4096)
    labels: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=4096)

    @field_validator("secret_ref")
    @classmethod
    def secret_ref_must_be_reference_only(cls, value: str | None) -> str | None:
        return _reject_raw_secret_value(value, "secret_ref")


class DatabaseStatusResponse(DatabaseStatusCreateRequest):
    pass


class DatabaseStatusesListResponse(DevOpsBaseModel):
    db_statuses: list[DatabaseStatusResponse] = Field(default_factory=list)
    total: int


class DatabaseCheckRecordRequest(DevOpsBaseModel):
    connection_health: ConnectionHealth | None = None
    migration_status: MigrationStatus | None = None
    backup_status: BackupStatus | None = None
    restore_readiness: RestoreReadiness | None = None
    summary: str | None = Field(default=None, max_length=4096)
    checked_at: str | None = Field(default=None, max_length=128)


class ServiceSummaryResponse(DevOpsBaseModel):
    service: DevOpsServiceResponse
    environments: list[ServiceEnvironmentResponse] = Field(default_factory=list)
    latest_ci_runs: list[CiCdRunResponse] = Field(default_factory=list)
    db_statuses: list[DatabaseStatusResponse] = Field(default_factory=list)
    deployment_targets: list[DeploymentTargetReferenceResponse] = Field(default_factory=list)


class DevOpsDashboardResponse(DevOpsBaseModel):
    services: dict[str, int]
    ci_runs: dict[str, int]
    db_status: dict[str, int]
    deployment_targets: dict[str, int]
