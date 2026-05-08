from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.domains.workers.service import AgentWorkerRegistryService
from app.domains.workers.task_evidence import AgentTaskEvidenceError, AgentTaskEvidenceService
from app.domains.workers.task_queue import AgentTaskQueueService
from app.shared.platform_db import create_platform_engine
from app.shared.platform_models import Base


class AgentTaskEvidenceContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "platform_state.db"
        self.database_url = f"sqlite+pysqlite:///{db_path}"
        engine = create_platform_engine(self.database_url)
        Base.metadata.create_all(engine)
        self.worker_service = AgentWorkerRegistryService(database_url=self.database_url)
        self.queue = AgentTaskQueueService(database_url=self.database_url)
        self.evidence = AgentTaskEvidenceService(database_url=self.database_url)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _register_worker(self, worker_id: str = "codex-01") -> dict:
        return self.worker_service.register_worker(
            {
                "worker_id": worker_id,
                "hostname": f"{worker_id}.local",
                "agent_types": ["codex"],
                "agent_auth_status": {"codex": "authenticated"},
                "status": "ready",
                "labels": {"capability": "repo-test-build"},
            }
        )

    def _create_running_task(self, task_id: str = "task-evidence-001", worker_id: str = "codex-01") -> dict:
        self._register_worker(worker_id)
        self.queue.create_task(
            {
                "task_id": task_id,
                "title": "Run evidence contract tests",
                "agent_type": "codex",
                "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                "target_ref": "main",
                "required_capabilities": ["repo-test-build"],
            }
        )
        return self.queue.assign_task(task_id)

    def test_evidence_contract_persists_events_artifacts_and_verification_reports(self):
        running = self._create_running_task()
        layout = running["workspace_action_contract"]["layout"]

        event = self.evidence.append_task_event(
            "task-evidence-001",
            {
                "event_type": "worker.started",
                "severity": "info",
                "source": "worker",
                "message": "Worker accepted typed task intent",
                "metadata": {"phase": "checkout"},
            },
        )
        self.assertEqual(event["schema_version"], "heimdall.agent_task_event.v1")
        self.assertEqual(event["task_id"], "task-evidence-001")
        self.assertEqual(event["event_type"], "worker.started")
        self.assertEqual(event["sequence"], 1)

        artifact = self.evidence.register_task_artifact(
            "task-evidence-001",
            {
                "artifact_id": "verification-report-json",
                "artifact_type": "verification_report",
                "relative_path": "verification-report.json",
                "media_type": "application/json",
                "size_bytes": 321,
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "metadata": {"producer": "worker-verifier"},
            },
        )
        self.assertEqual(artifact["schema_version"], "heimdall.agent_task_artifact.v1")
        self.assertEqual(
            artifact["path"],
            f"{layout['artifacts_path']}/verification-report.json",
        )
        self.assertFalse(artifact["path"].startswith(layout["worktree_path"]))
        self.assertEqual(artifact["relative_path"], "verification-report.json")

        report = self.evidence.submit_verification_report(
            "task-evidence-001",
            {
                "report_id": "verification-report-001",
                "status": "pass",
                "summary": "Selected backend checks passed",
                "checks": [
                    {
                        "name": "backend-selected-unittest",
                        "status": "pass",
                        "command_label": "backend selected unittest",
                        "artifact_id": "verification-report-json",
                        "summary": "focused worker/task/evidence checks passed",
                    }
                ],
                "metadata": {"review_gate": "ready"},
            },
        )
        self.assertEqual(report["schema_version"], "heimdall.agent_task_verification_report.v1")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["artifact_ids"], ["verification-report-json"])
        self.assertTrue(report["review_handoff"]["ready_for_hermes_review"])
        self.assertFalse(report["review_handoff"]["contains_raw_logs"])

        self.assertEqual(len(self.evidence.list_task_events("task-evidence-001")), 1)
        self.assertEqual(len(self.evidence.list_task_artifacts("task-evidence-001")), 1)
        self.assertEqual(len(self.evidence.list_verification_reports("task-evidence-001")), 1)

    def test_evidence_contract_rejects_raw_execution_and_sensitive_metadata(self):
        self._create_running_task()
        raw_key = "run" + "_" + "command"
        with self.assertRaisesRegex(AgentTaskEvidenceError, "raw execution field"):
            self.evidence.append_task_event(
                "task-evidence-001",
                {
                    "event_type": "worker.output",
                    "message": "unsafe metadata",
                    "metadata": {raw_key: "pytest"},
                },
            )

        with self.assertRaisesRegex(AgentTaskEvidenceError, "relative_path"):
            self.evidence.register_task_artifact(
                "task-evidence-001",
                {
                    "artifact_id": "bad-artifact-path",
                    "artifact_type": "verification_report",
                    "relative_path": "../verification-report.json",
                },
            )

        secret_marker = "api" + "_" + "key"
        with self.assertRaisesRegex(AgentTaskEvidenceError, "sensitive"):
            self.evidence.submit_verification_report(
                "task-evidence-001",
                {
                    "report_id": "bad-sensitive-report",
                    "status": "fail",
                    "summary": f"{secret_marker} was present",
                    "checks": [],
                },
            )

        with self.assertRaisesRegex(AgentTaskEvidenceError, "raw execution field"):
            self.evidence.submit_verification_report(
                "task-evidence-001",
                {
                    "report_id": "bad-raw-command-report",
                    "status": "pass",
                    "summary": "contains raw command key",
                    "checks": [{"name": "unit", "status": "pass", "command": "pytest"}],
                },
            )

        token_like_value = "gh" + "p_" + ("A" * 36)
        with self.assertRaisesRegex(AgentTaskEvidenceError, "sensitive"):
            self.evidence.append_task_event(
                "task-evidence-001",
                {
                    "event_type": "worker.output",
                    "message": token_like_value,
                    "metadata": {},
                },
            )

        bare_token_like_value = ("A" * 20) + ("1" * 20)
        with self.assertRaisesRegex(AgentTaskEvidenceError, "sensitive"):
            self.evidence.append_task_event(
                "task-evidence-001",
                {
                    "event_type": "worker.output",
                    "message": bare_token_like_value,
                    "metadata": {},
                },
            )

        provider_key_like_value = "AI" + "za" + ("A" * 35)
        with self.assertRaisesRegex(AgentTaskEvidenceError, "sensitive"):
            self.evidence.append_task_event(
                "task-evidence-001",
                {
                    "event_type": "worker.output",
                    "message": "provider check",
                    "metadata": {"nested": {"value": provider_key_like_value}},
                },
            )

        provider_command_label = "sk" + "-" + ("A" * 24)
        with self.assertRaisesRegex(AgentTaskEvidenceError, "sensitive"):
            self.evidence.submit_verification_report(
                "task-evidence-001",
                {
                    "report_id": "bad-provider-label",
                    "status": "fail",
                    "summary": "check label rejected",
                    "checks": [
                        {
                            "name": "provider-label",
                            "status": "fail",
                            "command_label": provider_command_label,
                        }
                    ],
                },
            )

        for symbol_wrapped_value in (
            "_" + ("A" * 20) + ("1" * 20),
            ("A" * 20) + ("1" * 20) + "=",
        ):
            with self.assertRaisesRegex(AgentTaskEvidenceError, "sensitive"):
                self.evidence.append_task_event(
                    "task-evidence-001",
                    {
                        "event_type": "worker.output",
                        "message": symbol_wrapped_value,
                        "metadata": {},
                    },
                )

        for raw_label in (
            "python -m unittest tests.test_agent_task_evidence_contract",
            "python tests/foo.py",
            "python -c print(1)",
            "/usr/bin/python -m unittest",
            "make test",
            "pytest",
        ):
            with self.assertRaisesRegex(AgentTaskEvidenceError, "raw execution"):
                self.evidence.submit_verification_report(
                    "task-evidence-001",
                    {
                        "report_id": f"bad-raw-command-label-{len(raw_label)}",
                        "status": "fail",
                        "summary": "raw execution label rejected",
                        "checks": [
                            {
                                "name": "raw-command-label",
                                "status": "fail",
                                "command_label": raw_label,
                            }
                        ],
                    },
                )

        for raw_text in ("make test", "python tests/foo.py"):
            with self.assertRaisesRegex(AgentTaskEvidenceError, "raw execution"):
                self.evidence.append_task_event(
                    "task-evidence-001",
                    {
                        "event_type": "worker.output",
                        "message": raw_text,
                        "metadata": {},
                    },
                )

        with self.assertRaisesRegex(AgentTaskEvidenceError, "command_label"):
            self.evidence.append_task_event(
                "task-evidence-001",
                {
                    "event_type": "worker.output",
                    "message": "metadata command label bypass rejected",
                    "metadata": {"command_label": "pytest"},
                },
            )

        with self.assertRaisesRegex(AgentTaskEvidenceError, "command_label"):
            self.evidence.register_task_artifact(
                "task-evidence-001",
                {
                    "artifact_id": "bad-command-label-metadata",
                    "artifact_type": "log",
                    "relative_path": "bad-command-label-metadata.txt",
                    "metadata": {"command_label": "pytest"},
                },
            )

        with self.assertRaisesRegex(AgentTaskEvidenceError, "command_label"):
            self.evidence.submit_verification_report(
                "task-evidence-001",
                {
                    "report_id": "bad-check-metadata-command-label",
                    "status": "fail",
                    "summary": "nested check metadata label rejected",
                    "checks": [
                        {
                            "name": "nested-metadata-label",
                            "status": "fail",
                            "command_label": "backend selected unittest",
                            "metadata": {"command_label": "pytest"},
                        }
                    ],
                },
            )

    def test_artifact_and_report_ids_are_task_scoped(self):
        self._create_running_task("task-evidence-001", worker_id="codex-01")
        self._create_running_task("task-evidence-002", worker_id="codex-02")

        for task_id in ("task-evidence-001", "task-evidence-002"):
            self.evidence.register_task_artifact(
                task_id,
                {
                    "artifact_id": "verification-report-json",
                    "artifact_type": "verification_report",
                    "relative_path": "verification-report.json",
                },
            )
            self.evidence.submit_verification_report(
                task_id,
                {
                    "report_id": "verification-report-001",
                    "status": "pass",
                    "summary": "task scoped verification report accepted",
                    "artifact_ids": ["verification-report-json"],
                },
            )

        self.assertEqual(len(self.evidence.list_task_artifacts("task-evidence-001")), 1)
        self.assertEqual(len(self.evidence.list_task_artifacts("task-evidence-002")), 1)
        self.assertEqual(len(self.evidence.list_verification_reports("task-evidence-001")), 1)
        self.assertEqual(len(self.evidence.list_verification_reports("task-evidence-002")), 1)

    def test_artifact_registration_requires_assigned_workspace_contract(self):
        self.queue.create_task(
            {
                "task_id": "task-evidence-queued",
                "title": "Queued only",
                "agent_type": "codex",
                "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                "target_ref": "main",
            }
        )

        with self.assertRaisesRegex(AgentTaskEvidenceError, "workspace action contract"):
            self.evidence.register_task_artifact(
                "task-evidence-queued",
                {
                    "artifact_id": "queued-artifact",
                    "artifact_type": "verification_report",
                    "relative_path": "verification-report.json",
                },
            )

    def test_artifact_relative_path_rejects_dot_and_empty_segments_before_normalization(self):
        self._create_running_task()

        for index, bad_path in enumerate(("./x.txt", "dir/./x.txt", "dir//x.txt"), start=1):
            with self.subTest(index=index):
                with self.assertRaisesRegex(AgentTaskEvidenceError, "relative_path"):
                    self.evidence.register_task_artifact(
                        "task-evidence-001",
                        {
                            "artifact_id": f"bad-relative-path-{index}",
                            "artifact_type": "log",
                            "relative_path": bad_path,
                        },
                    )


if __name__ == "__main__":
    unittest.main()
