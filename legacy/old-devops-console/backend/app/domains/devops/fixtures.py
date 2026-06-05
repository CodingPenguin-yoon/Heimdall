"""Safe non-production fixtures for DevOps dashboard smoke checks."""

from __future__ import annotations

import os
from collections.abc import Mapping

from app.domains.devops.schemas import (
    BackupStatus,
    CiCdRunCreateRequest,
    ConnectionHealth,
    DatabaseEngine,
    DatabaseRole,
    DatabaseStatusCreateRequest,
    DeployStatus,
    DeploymentTargetKind,
    DeploymentTargetProvider,
    DeploymentTargetReferenceCreateRequest,
    DeploymentTargetScheme,
    DeploymentTargetStatus,
    DevOpsServiceCreateRequest,
    EnvironmentName,
    HealthStatus,
    MigrationStatus,
    PipelineProvider,
    RestoreReadiness,
    RunStatus,
    ServiceEnvironmentCreateRequest,
)
from app.domains.devops.service import DevOpsCatalogService

SMOKE_FIXTURE_ENV_VAR = "HEIMDALL_DEVOPS_SMOKE_FIXTURES"
_TRUE_VALUES = {"1", "true", "yes", "on", "smoke"}


def smoke_fixtures_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether the non-production smoke fixture seed is explicitly enabled."""

    values = os.environ if environ is None else environ
    return str(values.get(SMOKE_FIXTURE_ENV_VAR, "")).strip().lower() in _TRUE_VALUES


def create_devops_catalog_service_from_env(
    environ: Mapping[str, str] | None = None,
) -> DevOpsCatalogService:
    """Create the in-memory catalog, optionally seeded for smoke/demo verification.

    The default remains an empty catalog. Operators must explicitly set
    ``HEIMDALL_DEVOPS_SMOKE_FIXTURES`` to a true value to load inert `.invalid`
    fixture data. This avoids accidental production-looking data and keeps Set 4
    away from persistence migrations or provider-side execution.
    """

    catalog = DevOpsCatalogService()
    if smoke_fixtures_enabled(environ):
        seed_smoke_devops_catalog(catalog)
    return catalog


def seed_smoke_devops_catalog(catalog: DevOpsCatalogService) -> DevOpsCatalogService:
    """Seed deterministic, idempotent, secret-safe DevOps smoke data."""

    catalog.create_service(
        DevOpsServiceCreateRequest(
            service_id="heimdall-api",
            name="Heimdall API smoke fixture",
            description="Non-production smoke service for read-only DevOps dashboard verification.",
            owner_team="homelab-devops",
            repo_url="https://git.example.invalid/homelab/heimdall-api.git",
            repo_provider="github",
            default_branch="main",
            runtime="python",
            framework="fastapi",
            health_status=HealthStatus.DEGRADED,
            lifecycle_status="active",
            runbook_url="https://docs.example.invalid/heimdall/devops-smoke-runbook",
            current_version="smoke-2026.05.06",
            current_commit="c310361",
            labels={"fixture": "devops-smoke", "environment": "non-production"},
            notes="Inert fixture data only; do not use for provider-side execution.",
        )
    )

    catalog.create_service(
        DevOpsServiceCreateRequest(
            service_id="heimdall-frontend",
            name="Heimdall Frontend smoke fixture",
            description="Non-production dashboard fixture companion service.",
            owner_team="homelab-devops",
            repo_url="https://git.example.invalid/homelab/heimdall-frontend.git",
            repo_provider="github",
            default_branch="main",
            runtime="node",
            framework="react",
            health_status=HealthStatus.HEALTHY,
            lifecycle_status="active",
            runbook_url="https://docs.example.invalid/heimdall/frontend-smoke-runbook",
            current_version="smoke-2026.05.06",
            current_commit="c310361",
            labels={"fixture": "devops-smoke", "environment": "non-production"},
        )
    )

    for environment_id, environment, health, deploy in [
        ("heimdall-api:staging", EnvironmentName.STAGING, HealthStatus.HEALTHY, DeployStatus.DEPLOYED),
        ("heimdall-api:prod", EnvironmentName.PROD, HealthStatus.DEGRADED, DeployStatus.BLOCKED),
    ]:
        catalog.create_environment(
            ServiceEnvironmentCreateRequest(
                environment_id=environment_id,
                service_id="heimdall-api",
                environment=environment,
                enabled=True,
                url=f"https://{environment.value}.heimdall-api.example.invalid",
                branch="main",
                desired_version="smoke-2026.05.06",
                deployed_version="smoke-2026.05.05" if environment == EnvironmentName.PROD else "smoke-2026.05.06",
                deployed_commit="c310361",
                health_status=health,
                deploy_status=deploy,
                last_deployed_at="2026-05-06T04:30:00Z",
                labels={"fixture": "devops-smoke"},
            )
        )

    catalog.create_environment(
        ServiceEnvironmentCreateRequest(
            environment_id="heimdall-frontend:prod",
            service_id="heimdall-frontend",
            environment=EnvironmentName.PROD,
            enabled=True,
            url="https://prod.heimdall-frontend.example.invalid",
            branch="main",
            desired_version="smoke-2026.05.06",
            deployed_version="smoke-2026.05.06",
            deployed_commit="c310361",
            health_status=HealthStatus.HEALTHY,
            deploy_status=DeployStatus.DEPLOYED,
            last_deployed_at="2026-05-06T04:35:00Z",
            labels={"fixture": "devops-smoke"},
        )
    )

    catalog.create_deployment_target(
        DeploymentTargetReferenceCreateRequest(
            target_id="heimdall-api:prod:app-host",
            environment_id="heimdall-api:prod",
            target_kind=DeploymentTargetKind.HOST,
            provider=DeploymentTargetProvider.MANUAL,
            host="heimdall-api-prod.example.invalid",
            port=443,
            scheme=DeploymentTargetScheme.HTTPS,
            target_status=DeploymentTargetStatus.READY,
            capacity_note="Fixture only: confirms dashboard target readiness rendering.",
            labels={"fixture": "devops-smoke"},
        )
    )

    catalog.create_deployment_target(
        DeploymentTargetReferenceCreateRequest(
            target_id="heimdall-frontend:prod:web-host",
            environment_id="heimdall-frontend:prod",
            target_kind=DeploymentTargetKind.HOST,
            provider=DeploymentTargetProvider.MANUAL,
            host="heimdall-frontend-prod.example.invalid",
            port=443,
            scheme=DeploymentTargetScheme.HTTPS,
            target_status=DeploymentTargetStatus.READY,
            capacity_note="Fixture only: confirms dashboard target readiness rendering.",
            labels={"fixture": "devops-smoke"},
        )
    )

    catalog.create_ci_run(
        CiCdRunCreateRequest(
            run_id="heimdall-api-smoke-build-1001",
            service_id="heimdall-api",
            environment_id="heimdall-api:staging",
            provider=PipelineProvider.GITHUB_ACTIONS,
            pipeline_url="https://ci.example.invalid/heimdall-api/runs/1001",
            commit_sha="c3103610946662ad7c0f9206700b28cf53990d07",
            branch="main",
            status=RunStatus.SUCCESS,
            stage="build-test",
            build_status=RunStatus.SUCCESS,
            test_status=RunStatus.SUCCESS,
            lint_status=RunStatus.SUCCESS,
            deployable=True,
            started_at="2026-05-06T03:00:00Z",
            finished_at="2026-05-06T03:08:00Z",
            allowed_actions=[],
            labels={"fixture": "devops-smoke"},
        )
    )

    catalog.create_ci_run(
        CiCdRunCreateRequest(
            run_id="heimdall-api-smoke-deploy-1002",
            service_id="heimdall-api",
            environment_id="heimdall-api:prod",
            provider=PipelineProvider.GITHUB_ACTIONS,
            pipeline_url="https://ci.example.invalid/heimdall-api/runs/1002",
            commit_sha="c3103610946662ad7c0f9206700b28cf53990d07",
            branch="main",
            status=RunStatus.FAILED,
            stage="deploy-preview",
            build_status=RunStatus.SUCCESS,
            test_status=RunStatus.SUCCESS,
            lint_status=RunStatus.SUCCESS,
            deployable=False,
            failure_summary="Fixture failure: production deployment intentionally blocked for smoke visibility.",
            started_at="2026-05-06T04:00:00Z",
            finished_at="2026-05-06T04:04:00Z",
            allowed_actions=[],
            requires_user_approval=True,
            labels={"fixture": "devops-smoke"},
        )
    )

    catalog.create_db_status(
        DatabaseStatusCreateRequest(
            db_status_id="heimdall-api:prod:primary",
            environment_id="heimdall-api:prod",
            database_role=DatabaseRole.PRIMARY,
            engine=DatabaseEngine.POSTGRES,
            version="16-smoke",
            secret_ref="vault/heimdall/devops-smoke/prod/postgres-primary",
            host_ref="heimdall-api-db-prod.example.invalid",
            connection_health=ConnectionHealth.DEGRADED,
            migration_status=MigrationStatus.PENDING,
            pending_migration_count=1,
            backup_status=BackupStatus.STALE,
            restore_readiness=RestoreReadiness.NEEDS_TEST,
            last_checked_at="2026-05-06T04:10:00Z",
            last_backup_at="2026-05-05T04:10:00Z",
            summary="Fixture signal: pending migration and stale backup for dashboard attention state.",
            labels={"fixture": "devops-smoke"},
        )
    )

    return catalog
