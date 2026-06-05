from enum import Enum


class Provider(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"


class DeployMode(str, Enum):
    DOCKERFILE = "dockerfile"
    MULTI_SERVICE_DOCKERFILE = "multi_service_dockerfile"
    COMPOSE = "compose"


class ProjectStatus(str, Enum):
    NOT_DEPLOYED = "not_deployed"
    DEPLOYING = "deploying"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    FAILED = "failed"
    DISABLED = "disabled"


class DeploymentStatus(str, Enum):
    QUEUED = "queued"
    FETCHING = "fetching"
    BUILDING = "building"
    STARTING = "starting"
    HEALTH_CHECKING = "health_checking"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLBACK_SUCCESS = "rollback_success"
    ROLLBACK_FAILED = "rollback_failed"
    DRY_RUN_SUCCESS = "dry_run_success"


class ReleaseStatus(str, Enum):
    AVAILABLE = "available"
    CURRENT = "current"
    SUPERSEDED = "superseded"
    MISSING_IMAGE = "missing_image"
    DISABLED = "disabled"
    SIMULATED = "simulated"


class TriggerType(str, Enum):
    MANUAL = "manual"
    GITHUB_WEBHOOK = "github_webhook"
    GITLAB_WEBHOOK = "gitlab_webhook"
    ROLLBACK = "rollback"
    RETRY = "retry"


class PortAllocationStatus(str, Enum):
    RESERVED = "reserved"
    ACTIVE = "active"
    RELEASED = "released"
    CONFLICT = "conflict"


class WebhookEventStatus(str, Enum):
    RECEIVED = "received"
    IGNORED = "ignored"
    ACCEPTED = "accepted"
    INVALID_SIGNATURE = "invalid_signature"
    UNKNOWN_PROJECT = "unknown_project"
    FAILED = "failed"


ACTIVE_DEPLOYMENT_STATUSES = {
    DeploymentStatus.QUEUED.value,
    DeploymentStatus.FETCHING.value,
    DeploymentStatus.BUILDING.value,
    DeploymentStatus.STARTING.value,
    DeploymentStatus.HEALTH_CHECKING.value,
}
