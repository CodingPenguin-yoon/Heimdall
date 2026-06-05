from __future__ import annotations

import asyncio
import importlib
import os
import unittest

from app.domains.devops.fixtures import (
    SMOKE_FIXTURE_ENV_VAR,
    create_devops_catalog_service_from_env,
    seed_smoke_devops_catalog,
)
from app.domains.devops.service import DevOpsCatalogService


class DevOpsSmokeFixtureContractTest(unittest.TestCase):
    def test_default_catalog_factory_stays_empty_without_explicit_smoke_flag(self):
        catalog = create_devops_catalog_service_from_env({})
        dashboard = catalog.build_dashboard_summary()

        self.assertEqual(dashboard.services["total"], 0)
        self.assertEqual(catalog.list_services(), [])
        self.assertEqual(catalog.list_ci_runs(), [])
        self.assertEqual(catalog.list_db_statuses(), [])
        self.assertEqual(catalog.list_deployment_targets(), [])

    def test_explicit_smoke_fixture_seeds_read_only_dashboard_data(self):
        catalog = create_devops_catalog_service_from_env({SMOKE_FIXTURE_ENV_VAR: "1"})

        services = catalog.list_services()
        environments = catalog.list_environments(service_id="heimdall-api")
        ci_runs = catalog.list_ci_runs(service_id="heimdall-api")
        db_statuses = catalog.list_db_statuses(environment_id="heimdall-api:prod")
        targets = catalog.list_deployment_targets(environment_id="heimdall-api:prod")
        dashboard = catalog.build_dashboard_summary()
        summary = catalog.build_service_summary("heimdall-api")

        self.assertGreaterEqual(len(services), 1)
        self.assertGreaterEqual(len(environments), 2)
        self.assertGreaterEqual(len(ci_runs), 2)
        self.assertGreaterEqual(len(db_statuses), 1)
        self.assertGreaterEqual(len(targets), 1)
        self.assertEqual(dashboard.services["total"], len(services))
        self.assertGreaterEqual(dashboard.ci_runs["failed"], 1)
        self.assertGreaterEqual(dashboard.db_status["backup_attention"], 1)
        self.assertGreaterEqual(dashboard.deployment_targets["ready"], 1)
        self.assertEqual(summary.service.service_id, "heimdall-api")
        self.assertEqual(len(summary.environments), len(environments))
        self.assertTrue(all(run.allowed_actions == [] for run in ci_runs))

    def test_router_uses_env_factory_without_exposing_fixture_mutation_endpoint(self):
        from app.domains.devops import router as router_module

        original = os.environ.get(SMOKE_FIXTURE_ENV_VAR)
        try:
            os.environ[SMOKE_FIXTURE_ENV_VAR] = "1"
            seeded_router = importlib.reload(router_module)
            dashboard = asyncio.run(seeded_router.get_dashboard())
            paths = {route.path for route in seeded_router.router.routes}

            self.assertGreaterEqual(dashboard.services["total"], 1)
            self.assertTrue(all("fixtures" not in path for path in paths))
        finally:
            if original is None:
                os.environ.pop(SMOKE_FIXTURE_ENV_VAR, None)
            else:
                os.environ[SMOKE_FIXTURE_ENV_VAR] = original
            importlib.reload(router_module)

    def test_smoke_fixture_is_idempotent_non_production_and_secret_safe(self):
        catalog = DevOpsCatalogService()
        seed_smoke_devops_catalog(catalog)
        seed_smoke_devops_catalog(catalog)

        services = catalog.list_services()
        environments = catalog.list_environments()
        db_statuses = catalog.list_db_statuses()
        targets = catalog.list_deployment_targets()

        self.assertEqual(len({service.service_id for service in services}), len(services))
        self.assertEqual(len({environment.environment_id for environment in environments}), len(environments))
        self.assertTrue(all(service.repo_url.endswith(".git") for service in services))
        self.assertTrue(all(".invalid" in service.repo_url for service in services))
        self.assertTrue(all(db.secret_ref.startswith("vault/heimdall/devops-smoke/") for db in db_statuses))
        self.assertTrue(all("://" not in db.secret_ref and "@" not in db.secret_ref for db in db_statuses))
        self.assertTrue(all((target.host or "").endswith(".invalid") for target in targets))


if __name__ == "__main__":
    unittest.main()
