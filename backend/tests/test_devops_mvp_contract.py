from __future__ import annotations

import asyncio
from pathlib import Path
import unittest

from fastapi import FastAPI
from pydantic import ValidationError

from app.domains.devops.router import DevOpsCatalogService, get_dashboard, router as devops_router
from app.domains.devops.schemas import (
    CiCdRunCreateRequest,
    DatabaseEngine,
    DatabaseRole,
    DatabaseStatusCreateRequest,
    DeploymentTargetKind,
    DeploymentTargetReferenceCreateRequest,
    DevOpsServiceCreateRequest,
    EnvironmentName,
    PipelineProvider,
    ServiceEnvironmentCreateRequest,
)
from app.domains.devops.service import DevOpsCatalogError


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class DevOpsMvpContractTest(unittest.TestCase):
    def test_devops_routes_are_registered_under_api_prefix_without_vm_lifecycle(self):
        probe_app = FastAPI()
        probe_app.include_router(devops_router, prefix="/api", tags=["devops"])
        paths = {route.path for route in probe_app.routes}

        expected_paths = {
            "/api/devops/services",
            "/api/devops/environments",
            "/api/devops/deployment-targets",
            "/api/devops/ci-runs",
            "/api/devops/db-status",
            "/api/devops/dashboard",
        }
        self.assertTrue(expected_paths.issubset(paths))

        forbidden_lifecycle_paths = {
            "/api/devops/vms",
            "/api/devops/proxmox",
            "/api/devops/instances",
            "/api/devops/create-instance",
        }
        self.assertTrue(paths.isdisjoint(forbidden_lifecycle_paths))

    def test_main_app_includes_devops_router_without_importing_env_loading_app(self):
        main_source = (BACKEND_ROOT / "app" / "main.py").read_text()

        self.assertIn(
            "from app.domains.devops.router import router as devops_router",
            main_source,
        )
        self.assertIn(
            'app.include_router(devops_router, prefix="/api", tags=["devops"])',
            main_source,
        )

    def test_service_catalog_contract_accepts_safe_repo_metadata_and_rejects_credentialed_urls(self):
        service = DevOpsServiceCreateRequest(
            service_id="sample-app",
            name="Sample App",
            owner_team="homelab",
            repo_url="https://git.example.invalid/group/sample-app.git",
            repo_provider="gitlab",
            runtime="python",
            framework="fastapi",
        )

        self.assertEqual(service.service_id, "sample-app")
        self.assertEqual(service.health_status, "unknown")
        self.assertEqual(service.lifecycle_status, "active")

        credentialed_repo_url = (
            "https://"
            + "sample-user"
            + ":"
            + "sample-pass"
            + "@git.example.invalid/group/bad-app.git"
        )
        with self.assertRaises(ValidationError):
            DevOpsServiceCreateRequest(
                service_id="bad-app",
                name="Bad App",
                repo_url=credentialed_repo_url,
            )

    def test_url_fields_reject_sensitive_query_parameters(self):
        credentialed_repo_query = (
            "https://git.example.invalid/group/app.git?"
            + "access_"
            + "token=sample-value"
        )
        with self.assertRaises(ValidationError):
            DevOpsServiceCreateRequest(
                service_id="bad-query-app",
                name="Bad Query App",
                repo_url=credentialed_repo_query,
            )

        credentialed_runbook_query = (
            "https://docs.example.invalid/runbook?"
            + "api_"
            + "key=sample-value"
        )
        with self.assertRaises(ValidationError):
            DevOpsServiceCreateRequest(
                service_id="bad-runbook-app",
                name="Bad Runbook App",
                repo_url="https://git.example.invalid/group/bad-runbook-app.git",
                runbook_url=credentialed_runbook_query,
            )

        credentialed_environment_query = (
            "https://app.example.invalid?"
            + "client_"
            + "secret=sample-value"
        )
        with self.assertRaises(ValidationError):
            ServiceEnvironmentCreateRequest(
                environment_id="sample-app:prod",
                service_id="sample-app",
                environment=EnvironmentName.PROD,
                url=credentialed_environment_query,
            )

        credentialed_pipeline_query = (
            "https://ci.example.invalid/pipelines/1?"
            + "private_"
            + "token=sample-value"
        )
        with self.assertRaises(ValidationError):
            CiCdRunCreateRequest(
                run_id="sample-run-1",
                service_id="sample-app",
                provider=PipelineProvider.GITLAB,
                pipeline_url=credentialed_pipeline_query,
            )

    def test_database_status_contract_accepts_secret_reference_and_rejects_raw_connection_string(self):
        db_status = DatabaseStatusCreateRequest(
            db_status_id="sample-app:staging:primary",
            environment_id="sample-app:staging",
            database_role=DatabaseRole.PRIMARY,
            engine=DatabaseEngine.POSTGRES,
            secret_ref="vault/heimdall/sample-app/staging/db",
        )

        self.assertEqual(db_status.connection_health, "unknown")
        self.assertEqual(db_status.migration_status, "unknown")
        self.assertEqual(db_status.backup_status, "unknown")
        self.assertEqual(db_status.restore_readiness, "unknown")

        raw_connection_string = (
            "postgresql://"
            + "sample-user"
            + ":"
            + "sample-pass"
            + "@db.example.invalid:5432/app"
        )
        with self.assertRaises(ValidationError):
            DatabaseStatusCreateRequest(
                db_status_id="sample-app:prod:primary",
                environment_id="sample-app:prod",
                database_role=DatabaseRole.PRIMARY,
                engine=DatabaseEngine.POSTGRES,
                secret_ref=raw_connection_string,
            )

    def test_database_secret_reference_rejects_raw_secret_assignments(self):
        raw_secret_assignment = "db_" + "password=sample-value"
        with self.assertRaises(ValidationError):
            DatabaseStatusCreateRequest(
                db_status_id="sample-app:prod:primary",
                environment_id="sample-app:prod",
                database_role=DatabaseRole.PRIMARY,
                engine=DatabaseEngine.POSTGRES,
                secret_ref=raw_secret_assignment,
            )

        dashed_raw_secret_assignment = "api-" + "key=sample-value"
        with self.assertRaises(ValidationError):
            DatabaseStatusCreateRequest(
                db_status_id="sample-app:prod:replica",
                environment_id="sample-app:prod",
                database_role=DatabaseRole.REPLICA,
                engine=DatabaseEngine.POSTGRES,
                secret_ref=dashed_raw_secret_assignment,
            )

    def test_catalog_rejects_orphan_nested_resources(self):
        catalog = DevOpsCatalogService()

        with self.assertRaises(DevOpsCatalogError):
            catalog.create_environment(
                ServiceEnvironmentCreateRequest(
                    environment_id="missing-service:prod",
                    service_id="missing-service",
                    environment=EnvironmentName.PROD,
                )
            )

        with self.assertRaises(DevOpsCatalogError):
            catalog.create_deployment_target(
                DeploymentTargetReferenceCreateRequest(
                    target_id="missing-env:vm-1",
                    environment_id="missing-service:prod",
                    target_kind=DeploymentTargetKind.VM,
                )
            )

        with self.assertRaises(DevOpsCatalogError):
            catalog.create_db_status(
                DatabaseStatusCreateRequest(
                    db_status_id="missing-env:primary",
                    environment_id="missing-service:prod",
                    database_role=DatabaseRole.PRIMARY,
                    engine=DatabaseEngine.POSTGRES,
                )
            )

    def test_catalog_rejects_orphan_or_cross_parent_ci_runs(self):
        catalog = DevOpsCatalogService()

        with self.assertRaises(DevOpsCatalogError):
            catalog.create_ci_run(
                CiCdRunCreateRequest(
                    run_id="missing-service-run",
                    service_id="missing-service",
                    provider=PipelineProvider.GITLAB,
                )
            )

        catalog.create_service(
            DevOpsServiceCreateRequest(
                service_id="sample-app",
                name="Sample App",
                repo_url="https://git.example.invalid/group/sample-app.git",
            )
        )
        catalog.create_service(
            DevOpsServiceCreateRequest(
                service_id="other-app",
                name="Other App",
                repo_url="https://git.example.invalid/group/other-app.git",
            )
        )
        catalog.create_environment(
            ServiceEnvironmentCreateRequest(
                environment_id="sample-app:prod",
                service_id="sample-app",
                environment=EnvironmentName.PROD,
            )
        )

        with self.assertRaises(DevOpsCatalogError):
            catalog.create_ci_run(
                CiCdRunCreateRequest(
                    run_id="cross-parent-run",
                    service_id="other-app",
                    environment_id="sample-app:prod",
                    provider=PipelineProvider.GITLAB,
                )
            )

    def test_ci_action_preview_requires_existing_allowed_action(self):
        catalog = DevOpsCatalogService()

        with self.assertRaises(DevOpsCatalogError):
            catalog.preview_ci_run_action("missing-run", "retry")

        catalog.create_service(
            DevOpsServiceCreateRequest(
                service_id="sample-app",
                name="Sample App",
                repo_url="https://git.example.invalid/group/sample-app.git",
            )
        )
        catalog.create_ci_run(
            CiCdRunCreateRequest(
                run_id="sample-run",
                service_id="sample-app",
                provider=PipelineProvider.GITLAB,
                allowed_actions=["retry"],
                requires_user_approval=True,
            )
        )

        denied = catalog.preview_ci_run_action("sample-run", "approve")
        self.assertFalse(denied.allowed)
        self.assertTrue(denied.requires_user_approval)

        allowed = catalog.preview_ci_run_action("sample-run", "retry")
        self.assertTrue(allowed.allowed)
        self.assertTrue(allowed.requires_user_approval)

    def test_dashboard_summary_contract_defaults_to_zero_counts(self):
        summary = DevOpsCatalogService().build_dashboard_summary()

        self.assertEqual(summary.services["total"], 0)
        self.assertEqual(summary.ci_runs["failed"], 0)
        self.assertEqual(summary.db_status["backup_attention"], 0)
        self.assertEqual(summary.deployment_targets["ready"], 0)

    def test_dashboard_route_returns_typed_summary(self):
        summary = asyncio.run(get_dashboard())

        self.assertEqual(summary.services["total"], 0)
        self.assertEqual(summary.ci_runs["running"], 0)
        self.assertEqual(summary.db_status["pending_migrations"], 0)

    def test_environment_enum_is_limited_to_dev_staging_prod(self):
        self.assertEqual(EnvironmentName.DEV.value, "dev")
        self.assertEqual(EnvironmentName.STAGING.value, "staging")
        self.assertEqual(EnvironmentName.PROD.value, "prod")


if __name__ == "__main__":
    unittest.main()
