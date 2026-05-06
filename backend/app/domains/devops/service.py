"""In-process service layer for the DevOps MVP API skeleton."""

from __future__ import annotations

from collections import Counter

from app.domains.devops.schemas import (
    BackupStatus,
    CiCdActionPreviewResponse,
    CiCdRunCreateRequest,
    CiCdRunResponse,
    DatabaseStatusCreateRequest,
    DatabaseStatusResponse,
    DeploymentTargetReferenceCreateRequest,
    DeploymentTargetReferenceResponse,
    DeploymentTargetStatus,
    DevOpsDashboardResponse,
    DevOpsServiceCreateRequest,
    DevOpsServiceResponse,
    HealthStatus,
    MigrationStatus,
    RunStatus,
    ServiceEnvironmentCreateRequest,
    ServiceEnvironmentResponse,
    ServiceSummaryResponse,
)


class DevOpsCatalogError(RuntimeError):
    """Raised when the typed DevOps catalog skeleton cannot satisfy a request."""


class DevOpsCatalogService:
    """Transient typed catalog backing the MVP API skeleton.

    This deliberately avoids platform DB migrations in Set 2. Persistence can be added
    in a later Set once the API contract is stable.
    """

    def __init__(self) -> None:
        self._services: dict[str, DevOpsServiceResponse] = {}
        self._environments: dict[str, ServiceEnvironmentResponse] = {}
        self._deployment_targets: dict[str, DeploymentTargetReferenceResponse] = {}
        self._ci_runs: dict[str, CiCdRunResponse] = {}
        self._db_statuses: dict[str, DatabaseStatusResponse] = {}

    def list_services(self) -> list[DevOpsServiceResponse]:
        return sorted(self._services.values(), key=lambda item: item.service_id)

    def create_service(self, payload: DevOpsServiceCreateRequest) -> DevOpsServiceResponse:
        service = DevOpsServiceResponse(**payload.model_dump())
        self._services[service.service_id] = service
        return service

    def get_service(self, service_id: str) -> DevOpsServiceResponse:
        service = self._services.get(service_id)
        if service is None:
            raise DevOpsCatalogError(f"service not found: {service_id}")
        return service

    def list_environments(
        self,
        *,
        service_id: str | None = None,
        environment: str | None = None,
    ) -> list[ServiceEnvironmentResponse]:
        rows = list(self._environments.values())
        if service_id:
            rows = [row for row in rows if row.service_id == service_id]
        if environment:
            rows = [row for row in rows if row.environment == environment]
        return sorted(rows, key=lambda item: item.environment_id)

    def create_environment(
        self,
        payload: ServiceEnvironmentCreateRequest,
    ) -> ServiceEnvironmentResponse:
        if payload.service_id not in self._services:
            raise DevOpsCatalogError(f"service not found: {payload.service_id}")
        row = ServiceEnvironmentResponse(**payload.model_dump())
        self._environments[row.environment_id] = row
        return row

    def list_deployment_targets(
        self,
        *,
        environment_id: str | None = None,
    ) -> list[DeploymentTargetReferenceResponse]:
        rows = list(self._deployment_targets.values())
        if environment_id:
            rows = [row for row in rows if row.environment_id == environment_id]
        return sorted(rows, key=lambda item: item.target_id)

    def create_deployment_target(
        self,
        payload: DeploymentTargetReferenceCreateRequest,
    ) -> DeploymentTargetReferenceResponse:
        if payload.environment_id not in self._environments:
            raise DevOpsCatalogError(f"environment not found: {payload.environment_id}")
        row = DeploymentTargetReferenceResponse(**payload.model_dump())
        self._deployment_targets[row.target_id] = row
        return row

    def list_ci_runs(
        self,
        *,
        service_id: str | None = None,
        environment_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[CiCdRunResponse]:
        rows = list(self._ci_runs.values())
        if service_id:
            rows = [row for row in rows if row.service_id == service_id]
        if environment_id:
            rows = [row for row in rows if row.environment_id == environment_id]
        if status:
            rows = [row for row in rows if row.status == status]
        return sorted(rows, key=lambda item: item.run_id)[:limit]

    def create_ci_run(self, payload: CiCdRunCreateRequest) -> CiCdRunResponse:
        if payload.service_id not in self._services:
            raise DevOpsCatalogError(f"service not found: {payload.service_id}")
        if payload.environment_id is not None:
            environment = self._environments.get(payload.environment_id)
            if environment is None:
                raise DevOpsCatalogError(f"environment not found: {payload.environment_id}")
            if environment.service_id != payload.service_id:
                raise DevOpsCatalogError(
                    "environment does not belong to CI run service: "
                    f"{payload.environment_id}"
                )
        row = CiCdRunResponse(**payload.model_dump())
        self._ci_runs[row.run_id] = row
        return row

    def preview_ci_run_action(self, run_id: str, action: str) -> CiCdActionPreviewResponse:
        run = self._ci_runs.get(run_id)
        if run is None:
            raise DevOpsCatalogError(f"CI/CD run not found: {run_id}")
        allowed = action in set(run.allowed_actions)
        return CiCdActionPreviewResponse(
            run_id=run_id,
            action=action,
            allowed=allowed,
            requires_user_approval=run.requires_user_approval,
            reason=(
                "operator approval required before provider-side CI/CD action"
                if allowed and run.requires_user_approval
                else "CI/CD action allowed by stored run contract"
                if allowed
                else "CI/CD action is not allowed for this run"
            ),
        )

    def list_db_statuses(
        self,
        *,
        environment_id: str | None = None,
    ) -> list[DatabaseStatusResponse]:
        rows = list(self._db_statuses.values())
        if environment_id:
            rows = [row for row in rows if row.environment_id == environment_id]
        return sorted(rows, key=lambda item: item.db_status_id)

    def create_db_status(self, payload: DatabaseStatusCreateRequest) -> DatabaseStatusResponse:
        if payload.environment_id not in self._environments:
            raise DevOpsCatalogError(f"environment not found: {payload.environment_id}")
        row = DatabaseStatusResponse(**payload.model_dump())
        self._db_statuses[row.db_status_id] = row
        return row

    def build_service_summary(self, service_id: str) -> ServiceSummaryResponse:
        service = self.get_service(service_id)
        environments = self.list_environments(service_id=service_id)
        environment_ids = {row.environment_id for row in environments}
        return ServiceSummaryResponse(
            service=service,
            environments=environments,
            latest_ci_runs=[
                row
                for row in self.list_ci_runs(service_id=service_id, limit=20)
                if row.environment_id is None or row.environment_id in environment_ids
            ],
            db_statuses=[
                row for row in self.list_db_statuses() if row.environment_id in environment_ids
            ],
            deployment_targets=[
                row
                for row in self.list_deployment_targets()
                if row.environment_id in environment_ids
            ],
        )

    def build_dashboard_summary(self) -> DevOpsDashboardResponse:
        service_health = Counter(row.health_status for row in self._services.values())
        ci_status = Counter(row.status for row in self._ci_runs.values())
        db_migrations = Counter(row.migration_status for row in self._db_statuses.values())
        db_backups = Counter(row.backup_status for row in self._db_statuses.values())
        target_status = Counter(row.target_status for row in self._deployment_targets.values())

        return DevOpsDashboardResponse(
            services={
                "total": len(self._services),
                "healthy": service_health[HealthStatus.HEALTHY.value],
                "degraded": service_health[HealthStatus.DEGRADED.value],
                "down": service_health[HealthStatus.DOWN.value],
                "unknown": service_health[HealthStatus.UNKNOWN.value],
            },
            ci_runs={
                "queued": ci_status[RunStatus.QUEUED.value],
                "running": ci_status[RunStatus.RUNNING.value],
                "failed": ci_status[RunStatus.FAILED.value],
                "success": ci_status[RunStatus.SUCCESS.value],
                "cancelled": ci_status[RunStatus.CANCELLED.value],
            },
            db_status={
                "healthy": sum(
                    1 for row in self._db_statuses.values() if row.connection_health == "healthy"
                ),
                "pending_migrations": db_migrations[MigrationStatus.PENDING.value],
                "backup_attention": db_backups[BackupStatus.STALE.value]
                + db_backups[BackupStatus.FAILED.value]
                + db_backups[BackupStatus.NOT_CONFIGURED.value],
            },
            deployment_targets={
                "ready": target_status[DeploymentTargetStatus.READY.value],
                "draining": target_status[DeploymentTargetStatus.DRAINING.value],
                "unreachable": target_status[DeploymentTargetStatus.UNREACHABLE.value],
                "unknown": target_status[DeploymentTargetStatus.UNKNOWN.value],
            },
        )
