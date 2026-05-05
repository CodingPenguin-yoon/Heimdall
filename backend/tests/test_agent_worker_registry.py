from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError
from unittest.mock import patch

from app.domains.workers.lifecycle import (
    AGENT_TASK_TERMINAL_STATES,
    can_transition_agent_task,
    normalize_agent_task_status,
)
from fastapi import HTTPException

from app.domains.workers.router import (
    AgentWorkerHeartbeatRequest,
    AgentWorkerRegisterRequest,
    AgentWorkerStatusUpdateRequest,
    require_worker_registry_api_key,
)
from app.domains.workers.service import AgentWorkerRegistryError, AgentWorkerRegistryService
from app.shared.platform_db import create_platform_engine
from app.shared.platform_models import Base


class AgentWorkerRegistryServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "platform_state.db"
        self.database_url = f"sqlite+pysqlite:///{db_path}"
        engine = create_platform_engine(self.database_url)
        Base.metadata.create_all(engine)
        self.service = AgentWorkerRegistryService(database_url=self.database_url)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_register_worker_normalizes_agent_types_and_never_stores_raw_tokens(self):
        worker = self.service.register_worker(
            {
                "worker_id": "codex-01",
                "display_name": "Codex Worker 01",
                "hostname": "codex-worker-01.local",
                "host_ip": "192.168.2.151",
                "ssh_user": "yoon",
                "agent_types": ["codex", "opencode", "codex", ""],
                "agent_auth_status": {
                    "codex": "authenticated",
                    "opencode": "not_applicable",
                    "token": "SHOULD_NOT_BE_STORED",
                    "refresh_token": "SHOULD_NOT_BE_STORED",
                },
                "status": "ready",
                "labels": {
                    "pool": "dev",
                    "token": "SHOULD_NOT_BE_STORED",
                    "apiKey": "SHOULD_NOT_BE_STORED",
                    "api-key": "SHOULD_NOT_BE_STORED",
                    "authorization": "SHOULD_NOT_BE_STORED",
                    "private_key": "SHOULD_NOT_BE_STORED",
                    "ssh_key": "SHOULD_NOT_BE_STORED",
                },
            }
        )

        self.assertEqual(worker["worker_id"], "codex-01")
        self.assertEqual(worker["agent_types"], ["codex", "opencode"])
        self.assertEqual(
            worker["agent_auth_status"],
            {"codex": "authenticated", "opencode": "not_applicable"},
        )
        self.assertEqual(worker["status"], "ready")
        self.assertEqual(worker["labels"], {"pool": "dev"})
        self.assertFalse(worker["is_stale"])
        self.assertNotIn("SHOULD_NOT_BE_STORED", repr(worker))

    def test_sensitive_label_string_value_is_rejected_and_not_persisted(self):
        with self.assertRaisesRegex(AgentWorkerRegistryError, "labels.note contains sensitive"):
            self.service.register_worker(
                {
                    "worker_id": "leaky-label",
                    "hostname": "worker.local",
                    "agent_types": ["codex"],
                    "labels": {"pool": "dev", "note": "Bearer sk-example-token"},
                }
            )

        self.assertIsNone(self.service.get_worker("leaky-label"))

    def test_sensitive_text_fields_are_rejected(self):
        field_values = {
            "display_name": "codex api_key sk-example",
            "hostname": "secret-host.local",
            "host_ip": "token=192.168.2.151",
            "ssh_user": "password-user",
            "current_task_id": "task-private-key",
            "last_checked_at": "bearer 2026-05-04T00:00:00Z",
        }

        for field_name, value in field_values.items():
            with self.subTest(field_name=field_name):
                payload = {
                    "worker_id": f"bad-{field_name.replace('_', '-')}",
                    "hostname": "worker.local",
                    "agent_types": ["codex"],
                }
                payload[field_name] = value

                with self.assertRaisesRegex(
                    AgentWorkerRegistryError,
                    f"{field_name} contains sensitive",
                ):
                    self.service.register_worker(payload)

    def test_sensitive_worker_id_is_rejected_and_not_persisted(self):
        with self.assertRaisesRegex(AgentWorkerRegistryError, "worker_id contains sensitive"):
            self.service.register_worker(
                {
                    "worker_id": "token-sk-example",
                    "hostname": "worker.local",
                    "agent_types": ["codex"],
                }
            )

        self.assertEqual(self.service.list_workers(), [])

    def test_worker_id_accepts_only_safe_identifier_characters(self):
        with self.assertRaisesRegex(AgentWorkerRegistryError, "worker_id may only contain"):
            self.service.register_worker(
                {
                    "worker_id": "codex worker/01",
                    "hostname": "worker.local",
                    "agent_types": ["codex"],
                }
            )

        self.assertEqual(self.service.list_workers(), [])

    def test_register_worker_upserts_identity_and_list_filters_by_agent_type(self):
        created = self.service.register_worker(
            {
                "worker_id": "codex-01",
                "hostname": "old-host.local",
                "host_ip": "192.168.2.151",
                "agent_types": ["codex"],
                "status": "unknown",
            }
        )
        updated = self.service.register_worker(
            {
                "worker_id": "codex-01",
                "hostname": "new-host.local",
                "host_ip": "192.168.2.152",
                "agent_types": ["codex", "claude"],
                "status": "ready",
                "current_task_id": "task-123",
            }
        )
        self.service.register_worker(
            {
                "worker_id": "opencode-01",
                "hostname": "opencode-worker.local",
                "agent_types": ["opencode"],
                "status": "offline",
            }
        )

        self.assertEqual(created["worker_id"], updated["worker_id"])
        self.assertEqual(updated["hostname"], "new-host.local")
        self.assertEqual(updated["host_ip"], "192.168.2.152")
        self.assertEqual(updated["agent_types"], ["claude", "codex"])
        self.assertEqual(updated["current_task_id"], "task-123")

        codex_workers = self.service.list_workers(agent_type="codex")
        self.assertEqual([worker["worker_id"] for worker in codex_workers], ["codex-01"])

        all_workers = self.service.list_workers()
        self.assertEqual([worker["worker_id"] for worker in all_workers], ["codex-01", "opencode-01"])

    def test_update_worker_status_can_clear_current_task_id(self):
        self.service.register_worker(
            {
                "worker_id": "codex-01",
                "hostname": "worker.local",
                "agent_types": ["codex"],
                "status": "busy",
                "current_task_id": "task-123",
            }
        )

        updated = self.service.update_worker_status(
            "codex-01",
            {"status": "ready", "current_task_id": None},
        )

        self.assertEqual(updated["status"], "ready")
        self.assertIsNone(updated["current_task_id"])

    def test_record_worker_heartbeat_updates_status_auth_task_and_observed_at(self):
        self.service.register_worker(
            {
                "worker_id": "codex-01",
                "hostname": "worker.local",
                "agent_types": ["codex", "claude"],
                "status": "offline",
                "agent_auth_status": {"codex": "expired", "claude": "needs_login"},
            }
        )

        updated = self.service.record_worker_heartbeat(
            "codex-01",
            {
                "status": "busy",
                "agent_auth_status": {"codex": "authenticated", "claude": "expired"},
                "current_task_id": "task-456",
                "observed_at": "2026-05-04T12:30:00+09:00",
            },
        )

        self.assertEqual(updated["status"], "busy")
        self.assertEqual(
            updated["agent_auth_status"],
            {"claude": "expired", "codex": "authenticated"},
        )
        self.assertEqual(updated["current_task_id"], "task-456")
        self.assertEqual(updated["last_checked_at"], "2026-05-04T03:30:00+00:00")

    def test_record_worker_heartbeat_can_clear_current_task_id_with_explicit_null(self):
        self.service.register_worker(
            {
                "worker_id": "codex-01",
                "hostname": "worker.local",
                "agent_types": ["codex"],
                "status": "busy",
                "current_task_id": "task-123",
            }
        )

        updated = self.service.record_worker_heartbeat(
            "codex-01",
            {"current_task_id": None},
        )

        self.assertIsNone(updated["current_task_id"])

    def test_record_worker_heartbeat_missing_worker_errors(self):
        with self.assertRaisesRegex(AgentWorkerRegistryError, "worker not found: missing-worker"):
            self.service.record_worker_heartbeat("missing-worker", {})

    def test_record_worker_heartbeat_invalid_observed_at_errors(self):
        self.service.register_worker(
            {
                "worker_id": "codex-01",
                "hostname": "worker.local",
                "agent_types": ["codex"],
            }
        )

        with self.assertRaisesRegex(AgentWorkerRegistryError, "observed_at must be an ISO timestamp"):
            self.service.record_worker_heartbeat(
                "codex-01",
                {"observed_at": "not-a-timestamp"},
            )

    def test_worker_stale_helper_and_serialized_response(self):
        now = datetime.now(timezone.utc)
        old_timestamp = (now - timedelta(seconds=301)).isoformat()
        fresh_timestamp = (now - timedelta(seconds=60)).isoformat()

        self.assertTrue(AgentWorkerRegistryService.is_worker_stale(old_timestamp))
        self.assertFalse(AgentWorkerRegistryService.is_worker_stale(fresh_timestamp))
        self.assertTrue(AgentWorkerRegistryService.is_worker_stale("not-a-timestamp"))

        worker = self.service.register_worker(
            {
                "worker_id": "old-worker",
                "hostname": "old-worker.local",
                "agent_types": ["codex"],
                "last_checked_at": old_timestamp,
            }
        )
        self.assertTrue(worker["is_stale"])

    def test_invalid_agent_worker_payload_is_rejected(self):
        with self.assertRaisesRegex(AgentWorkerRegistryError, "worker_id is required"):
            self.service.register_worker({"hostname": "missing-id.local", "agent_types": ["codex"]})

        with self.assertRaisesRegex(AgentWorkerRegistryError, "unsupported agent type"):
            self.service.register_worker(
                {"worker_id": "bad-agent", "hostname": "bad.local", "agent_types": ["raw-shell"]}
            )

        with self.assertRaisesRegex(AgentWorkerRegistryError, "unsupported worker status"):
            self.service.register_worker(
                {"worker_id": "bad-status", "hostname": "bad.local", "status": "root_shell"}
            )

    def test_gjallar_provisioning_handoff_registers_ready_worker_and_heartbeat_releases_task(self):
        provisioning_result = {
            "schema_version": "gjallar.worker_provisioning_result.v1",
            "provisioning_id": "gjallar-provisioning-20260505-001",
            "owner_project": "Gjallar",
            "worker_id": "codex-01",
            "display_name": "Codex Worker 01",
            "hostname": "codex-worker-01.local",
            "ssh_user": "yoon",
            "agent_types": ["codex"],
            "agent_auth_status": {"codex": "authenticated"},
            "bootstrap_status": "completed",
            "observed_at": "2026-05-05T01:30:00Z",
            "labels": {"pool": "dev", "capability": "repo-test-build"},
            "checks": {
                "ssh_reachable": True,
                "codex_cli_available": True,
                "workspace_ready": True,
            },
        }

        register_payload = self.service.build_registration_payload_from_gjallar_result(
            provisioning_result
        )
        registered = self.service.register_worker(register_payload)

        self.assertEqual(registered["worker_id"], "codex-01")
        self.assertEqual(registered["status"], "ready")
        self.assertEqual(registered["agent_auth_status"], {"codex": "authenticated"})
        self.assertEqual(registered["current_task_id"], None)
        self.assertEqual(registered["labels"]["provisioning_owner"], "Gjallar")
        self.assertEqual(registered["labels"]["bootstrap_status"], "completed")

        assigned = self.service.update_worker_status(
            "codex-01",
            {"status": "busy", "current_task_id": "task-456"},
        )
        self.assertEqual(assigned["status"], "busy")
        self.assertEqual(assigned["current_task_id"], "task-456")

        released = self.service.record_worker_heartbeat(
            "codex-01",
            {
                "status": "ready",
                "agent_auth_status": {"codex": "authenticated"},
                "current_task_id": None,
                "observed_at": "2026-05-05T01:35:00Z",
            },
        )

        self.assertEqual(released["status"], "ready")
        self.assertIsNone(released["current_task_id"])
        self.assertEqual(released["last_checked_at"], "2026-05-05T01:35:00+00:00")

    def test_build_registration_payload_from_gjallar_result_maps_safe_contract_fields(self):
        payload = self.service.build_registration_payload_from_gjallar_result(
            {
                "schema_version": "gjallar.worker_provisioning_result.v1",
                "provisioning_id": "gjallar-provisioning-20260504-001",
                "owner_project": "Gjallar",
                "worker_id": "codex-01",
                "display_name": "Codex Worker 01",
                "hostname": "codex-worker-01.local",
                "host_ip": "192.168.2.151",
                "ssh_user": "yoon",
                "agent_types": ["codex", "codex"],
                "agent_auth_status": {"codex": "authenticated"},
                "bootstrap_status": "completed",
                "observed_at": "2026-05-04T12:30:00Z",
                "labels": {
                    "pool": "dev",
                    "node": "pve-node-a",
                    "authorization": "SHOULD_NOT_BE_STORED",
                },
                "checks": {
                    "ssh_reachable": True,
                    "codex_cli_available": True,
                    "workspace_ready": True,
                },
            }
        )

        self.assertEqual(payload["worker_id"], "codex-01")
        self.assertEqual(payload["display_name"], "Codex Worker 01")
        self.assertEqual(payload["hostname"], "codex-worker-01.local")
        self.assertEqual(payload["host_ip"], "192.168.2.151")
        self.assertEqual(payload["ssh_user"], "yoon")
        self.assertEqual(payload["agent_types"], ["codex"])
        self.assertEqual(payload["agent_auth_status"], {"codex": "authenticated"})
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["last_checked_at"], "2026-05-04T12:30:00+00:00")
        self.assertEqual(
            payload["labels"],
            {
                "pool": "dev",
                "node": "pve-node-a",
                "provisioning_owner": "Gjallar",
                "provisioning_id": "gjallar-provisioning-20260504-001",
                "bootstrap_status": "completed",
            },
        )
        self.assertNotIn("SHOULD_NOT_BE_STORED", repr(payload))

    def test_build_registration_payload_from_gjallar_result_rejects_wrong_owner_and_sensitive_fields(self):
        valid_result = {
            "schema_version": "gjallar.worker_provisioning_result.v1",
            "owner_project": "Gjallar",
            "worker_id": "codex-01",
            "hostname": "codex-worker-01.local",
            "agent_types": ["codex"],
            "bootstrap_status": "completed",
            "observed_at": "2026-05-04T12:30:00Z",
            "checks": {"ssh_reachable": True, "workspace_ready": True},
        }

        wrong_owner = {**valid_result, "owner_project": "Heimdall"}
        with self.assertRaisesRegex(AgentWorkerRegistryError, "owner_project must be Gjallar"):
            self.service.build_registration_payload_from_gjallar_result(wrong_owner)

        sensitive_top_level = {**valid_result, "oauth_token": "SHOULD_NOT_BE_STORED"}
        with self.assertRaisesRegex(AgentWorkerRegistryError, "sensitive non-contract field"):
            self.service.build_registration_payload_from_gjallar_result(sensitive_top_level)

    def test_build_registration_payload_from_gjallar_result_requires_explicit_agent_types(self):
        result = {
            "schema_version": "gjallar.worker_provisioning_result.v1",
            "owner_project": "Gjallar",
            "worker_id": "codex-01",
            "hostname": "codex-worker-01.local",
            "bootstrap_status": "completed",
            "observed_at": "2026-05-04T12:30:00Z",
            "checks": {"ssh_reachable": True, "workspace_ready": True},
        }

        with self.assertRaisesRegex(AgentWorkerRegistryError, "agent_types is required"):
            self.service.build_registration_payload_from_gjallar_result(result)

    def test_build_registration_payload_from_gjallar_result_allows_missing_observed_at(self):
        payload = self.service.build_registration_payload_from_gjallar_result(
            {
                "schema_version": "gjallar.worker_provisioning_result.v1",
                "owner_project": "Gjallar",
                "worker_id": "codex-02",
                "hostname": "codex-worker-02.local",
                "agent_types": ["codex"],
                "bootstrap_status": "completed",
                "checks": {
                    "ssh_reachable": True,
                    "codex_cli_available": True,
                    "workspace_ready": True,
                },
            }
        )

        self.assertNotIn("last_checked_at", payload)
        registered = self.service.register_worker(payload)
        self.assertEqual(registered["worker_id"], "codex-02")
        self.assertEqual(registered["status"], "ready")
        self.assertFalse(registered["is_stale"])

    def test_build_registration_payload_from_gjallar_result_requires_explicit_agent_cli_ready_check(self):
        payload = self.service.build_registration_payload_from_gjallar_result(
            {
                "schema_version": "gjallar.worker_provisioning_result.v1",
                "owner_project": "Gjallar",
                "worker_id": "codex-01",
                "hostname": "codex-worker-01.local",
                "agent_types": ["codex"],
                "bootstrap_status": "completed",
                "observed_at": "2026-05-04T12:30:00Z",
                "checks": {"ssh_reachable": True, "workspace_ready": True},
            }
        )

        self.assertEqual(payload["status"], "unknown")

    def test_register_worker_rejects_sensitive_extra_top_level_fields(self):
        with self.assertRaisesRegex(AgentWorkerRegistryError, "sensitive top-level field"):
            self.service.register_worker(
                {
                    "worker_id": "codex-01",
                    "hostname": "worker.local",
                    "agent_types": ["codex"],
                    "oauth_token": "SHOULD_NOT_BE_STORED",
                }
            )


class AgentWorkerRegistryRouterPolicyTest(unittest.TestCase):
    def test_worker_registry_api_key_fails_closed_when_unconfigured_or_wrong(self):
        with patch.dict(os.environ, {"HEIMDALL_WORKER_REGISTRY_API_KEY": ""}, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                require_worker_registry_api_key(None)
            self.assertEqual(ctx.exception.status_code, 503)

        with patch.dict(os.environ, {"HEIMDALL_WORKER_REGISTRY_API_KEY": "correct-key"}, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                require_worker_registry_api_key("wrong-key")
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertIsNone(require_worker_registry_api_key("correct-key"))

    def test_worker_registry_request_models_forbid_extra_fields(self):
        with self.assertRaises(ValidationError):
            AgentWorkerRegisterRequest(
                worker_id="codex-01",
                hostname="worker.local",
                agent_types=["codex"],
                **{"oauth_token": "SHOULD_NOT_BE_STORED"},
            )

        with self.assertRaises(ValidationError):
            AgentWorkerStatusUpdateRequest(status="ready", **{"oauth_token": "SHOULD_NOT_BE_STORED"})

        with self.assertRaises(ValidationError):
            AgentWorkerHeartbeatRequest(status="ready", **{"oauth_token": "SHOULD_NOT_BE_STORED"})

    def test_status_patch_payload_preserves_explicit_null_for_task_clear(self):
        payload = AgentWorkerStatusUpdateRequest(current_task_id=None)

        self.assertEqual(payload.model_dump(exclude_unset=True), {"current_task_id": None})

    def test_heartbeat_payload_preserves_explicit_null_for_task_clear(self):
        payload = AgentWorkerHeartbeatRequest(current_task_id=None)

        self.assertEqual(payload.model_dump(exclude_unset=True), {"current_task_id": None})


class AgentTaskLifecycleTest(unittest.TestCase):
    def test_agent_task_status_normalization_and_safe_transitions(self):
        self.assertEqual(normalize_agent_task_status("Needs Review"), "needs_review")
        self.assertTrue(can_transition_agent_task("queued", "running"))
        self.assertTrue(can_transition_agent_task("running", "needs_review"))
        self.assertTrue(can_transition_agent_task("needs_review", "succeeded"))
        self.assertTrue(can_transition_agent_task("running", "failed"))
        self.assertFalse(can_transition_agent_task("succeeded", "running"))
        self.assertFalse(can_transition_agent_task("failed", "running"))
        self.assertIn("succeeded", AGENT_TASK_TERMINAL_STATES)
        self.assertIn("cancelled", AGENT_TASK_TERMINAL_STATES)


if __name__ == "__main__":
    unittest.main()
