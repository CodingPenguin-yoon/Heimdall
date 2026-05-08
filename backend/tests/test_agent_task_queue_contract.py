from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.domains.workers.service import AgentWorkerRegistryService
from app.domains.workers.task_queue import AgentTaskQueueError, AgentTaskQueueService
from app.shared.platform_db import create_platform_engine
from app.shared.platform_models import AgentTask, AgentWorker, Base


class AgentTaskQueueContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "platform_state.db"
        self.database_url = f"sqlite+pysqlite:///{db_path}"
        engine = create_platform_engine(self.database_url)
        Base.metadata.create_all(engine)
        self.worker_service = AgentWorkerRegistryService(database_url=self.database_url)
        self.queue = AgentTaskQueueService(database_url=self.database_url)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _register_worker(
        self,
        worker_id: str,
        *,
        status: str = "ready",
        auth_status: str = "authenticated",
        current_task_id: str | None = None,
        capability: str = "repo-test-build",
    ) -> dict:
        return self.worker_service.register_worker(
            {
                "worker_id": worker_id,
                "hostname": f"{worker_id}.local",
                "agent_types": ["codex"],
                "agent_auth_status": {"codex": auth_status},
                "status": status,
                "current_task_id": current_task_id,
                "labels": {"capability": capability},
            }
        )

    def test_create_task_contract_starts_queued_and_keeps_execution_boundary_typed(self):
        task = self.queue.create_task(
            {
                "task_id": "task-queue-001",
                "title": "Run focused backend tests",
                "agent_type": "codex",
                "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                "target_ref": "main",
                "required_capabilities": ["repo-test-build"],
                "labels": {"project": "Heimdall", "component": "agent-task-queue"},
            }
        )

        self.assertEqual(task["schema_version"], "heimdall.agent_task.v1")
        self.assertEqual(task["status"], "queued")
        self.assertIsNone(task["assigned_worker_id"])
        self.assertEqual(task["required_capabilities"], ["repo-test-build"])
        self.assertEqual(task["workspace_action_request"]["action"], "prepare_worktree")
        self.assertEqual(task["workspace_action_request"]["target_ref"], "main")
        self.assertFalse(task["execution_boundary"]["raw_shell_allowed"])
        self.assertFalse(task["execution_boundary"]["stores_credentials"])
        self.assertEqual(task["labels"], {"project": "Heimdall", "component": "agent-task-queue"})

    def test_create_task_rejects_raw_execution_and_credentialed_repo_url(self):
        with self.assertRaisesRegex(AgentTaskQueueError, "raw execution field"):
            self.queue.create_task(
                {
                    "task_id": "task-queue-raw",
                    "title": "Run a command",
                    "agent_type": "codex",
                    "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                    "target_ref": "main",
                    "raw_shell": "git status",
                }
            )

        credentialed_url = "https://" + "user" + ":" + "pass" + "@example.com/org/repo.git"
        with self.assertRaisesRegex(AgentTaskQueueError, "inline credentials|sensitive"):
            self.queue.create_task(
                {
                    "task_id": "task-queue-cred-url",
                    "title": "Run focused backend tests",
                    "agent_type": "codex",
                    "repo_url": credentialed_url,
                    "target_ref": "main",
                }
            )

        unsafe_repo_urls = (
            (
                "task-queue-unsafe-repo-query",
                "https://github.com/CodingPenguin-yoon/Heimdall.git?ref=main&code="
                + ("gh" + "p_" + ("A" * 36)),
            ),
            (
                "task-queue-unsafe-repo-fragment",
                "https://github.com/CodingPenguin-yoon/Heimdall.git#"
                + ("sk-" + ("a" * 20)),
            ),
        )
        for task_id, unsafe_repo_url in unsafe_repo_urls:
            with self.subTest(unsafe_repo_url=unsafe_repo_url):
                with self.assertRaisesRegex(AgentTaskQueueError, "repo_url|sensitive"):
                    self.queue.create_task(
                        {
                            "task_id": task_id,
                            "title": "Run focused backend tests",
                            "agent_type": "codex",
                            "repo_url": unsafe_repo_url,
                            "target_ref": "main",
                        }
                    )

    def test_create_task_rejects_sensitive_and_raw_label_metadata(self):
        base_payload = {
            "task_id": "task-queue-label-guard",
            "title": "Reject unsafe labels",
            "agent_type": "codex",
            "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
            "target_ref": "main",
        }
        sensitive_label = "api" + "_" + "key_hint"
        with self.assertRaisesRegex(AgentTaskQueueError, "sensitive field"):
            self.queue.create_task({**base_payload, "labels": {sensitive_label: "redacted"}})
        for raw_label in (
            "script",
            "shell_script",
            "run_command",
            "command_override",
            "shellScript",
            "runCommand",
            "commandOverride",
            "scriptBody",
            "rawShellCommand",
            "shellscript",
            "runcommand",
            "commandoverride",
        ):
            with self.subTest(raw_label=raw_label):
                with self.assertRaisesRegex(AgentTaskQueueError, "raw execution field"):
                    self.queue.create_task({**base_payload, "labels": {raw_label: "typed intent only"}})

    def test_create_task_rejects_secret_like_and_raw_text_values(self):
        base_payload = {
            "task_id": "task-queue-value-guard",
            "title": "Safe operator task",
            "agent_type": "codex",
            "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
            "target_ref": "main",
        }
        provider_credential = "gh" + "p_" + ("A" * 36)
        bearer_credential = "Bearer " + ("A" * 24)
        openai_style_credential = "sk-" + ("a" * 20)
        unsafe_payloads = (
            {**base_payload, "task_id": "task-queue-value-guard-title-secret", "title": f"Investigate {provider_credential}"},
            {**base_payload, "task_id": "task-queue-value-guard-title-raw", "title": "Run git status --short before review"},
            {**base_payload, "task_id": "task-queue-value-guard-label-raw", "labels": {"note": "run npm test -- --watch"}},
            {**base_payload, "task_id": "task-queue-value-guard-cap-secret", "required_capabilities": [openai_style_credential]},
        )
        for payload in unsafe_payloads:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(AgentTaskQueueError, "sensitive|raw execution"):
                    self.queue.create_task(payload)

        self.queue.create_task(base_payload)
        with self.assertRaisesRegex(AgentTaskQueueError, "sensitive"):
            self.queue.transition_task(
                "task-queue-value-guard",
                {"status": "cancelled", "reason": f"blocked by {bearer_credential}"},
            )

    def test_invalid_status_is_reported_as_queue_error(self):
        with self.assertRaisesRegex(AgentTaskQueueError, "unsupported agent task status"):
            self.queue.create_task(
                {
                    "task_id": "task-queue-bad-status",
                    "title": "Bad status",
                    "agent_type": "codex",
                    "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                    "target_ref": "main",
                    "status": "executing",
                }
            )
        with self.assertRaisesRegex(AgentTaskQueueError, "unsupported agent task status"):
            self.queue.list_tasks(status="executing")

    def test_allocate_task_chooses_ready_authenticated_idle_worker_and_marks_it_busy(self):
        self._register_worker("codex-02", auth_status="expired")
        self._register_worker("codex-01")
        self.queue.create_task(
            {
                "task_id": "task-queue-002",
                "title": "Run focused backend tests",
                "agent_type": "codex",
                "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                "target_ref": "main",
                "required_capabilities": ["repo-test-build"],
            }
        )

        assigned = self.queue.assign_task("task-queue-002")
        worker = self.worker_service.get_worker("codex-01")

        self.assertEqual(assigned["status"], "running")
        self.assertEqual(assigned["assigned_worker_id"], "codex-01")
        self.assertEqual(assigned["workspace_action_contract"]["worker_id"], "codex-01")
        self.assertEqual(assigned["workspace_action_contract"]["task_id"], "task-queue-002")
        self.assertEqual(worker["status"], "busy")
        self.assertEqual(worker["current_task_id"], "task-queue-002")

    def test_claim_worker_for_task_uses_compare_and_set_guard(self):
        self._register_worker("codex-01")
        self.queue.create_task(
            {
                "task_id": "task-queue-cas",
                "title": "Run focused backend tests",
                "agent_type": "codex",
                "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                "target_ref": "main",
            }
        )

        with self.queue._session_factory.begin() as competing_session:
            competing_worker = competing_session.get(AgentWorker, "codex-01")
            competing_worker.status = "busy"
            competing_worker.current_task_id = "other-running-task"

        with self.queue._session_factory.begin() as session:
            task = session.get(AgentTask, "task-queue-cas")
            stale_worker = AgentWorker(
                worker_id="codex-01",
                hostname="codex-01.local",
                agent_types=["codex"],
                agent_auth_status={"codex": "authenticated"},
                status="ready",
                labels_json={"capability": "repo-test-build"},
                current_task_id=None,
                last_checked_at=self.queue._now_iso(),
                created_at=self.queue._now_iso(),
                updated_at=self.queue._now_iso(),
            )
            workspace_contract = self.queue._build_workspace_action_contract(task, "codex-01")

            claimed = self.queue._claim_worker_for_task(
                session,
                task,
                stale_worker,
                workspace_contract,
                now=self.queue._now_iso(),
            )

        task = self.queue.get_task("task-queue-cas")
        worker = self.worker_service.get_worker("codex-01")
        self.assertFalse(claimed)
        self.assertEqual(task["status"], "queued")
        self.assertIsNone(task["assigned_worker_id"])
        self.assertEqual(worker["status"], "busy")
        self.assertEqual(worker["current_task_id"], "other-running-task")

    def test_no_available_worker_leaves_task_queued_with_allocation_reason(self):
        self._register_worker("codex-01", status="offline")
        self.queue.create_task(
            {
                "task_id": "task-queue-003",
                "title": "Run focused backend tests",
                "agent_type": "codex",
                "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                "target_ref": "main",
            }
        )

        task = self.queue.assign_task("task-queue-003")

        self.assertEqual(task["status"], "queued")
        self.assertIsNone(task["assigned_worker_id"])
        self.assertEqual(task["allocation_status"], "no_ready_authenticated_worker")

    def test_needs_review_releases_worker_and_terminal_tasks_do_not_restart(self):
        self._register_worker("codex-01")
        self.queue.create_task(
            {
                "task_id": "task-queue-004",
                "title": "Prepare review diff",
                "agent_type": "codex",
                "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                "target_ref": "main",
            }
        )
        running = self.queue.assign_task("task-queue-004")
        self.assertEqual(running["status"], "running")

        review = self.queue.transition_task(
            "task-queue-004",
            {"status": "needs_review", "reason": "diff ready for Hermes review"},
        )
        worker = self.worker_service.get_worker("codex-01")

        self.assertEqual(review["status"], "needs_review")
        self.assertEqual(review["needs_review_reason"], "diff ready for Hermes review")
        self.assertEqual(worker["status"], "ready")
        self.assertIsNone(worker["current_task_id"])

        terminal = self.queue.transition_task("task-queue-004", {"status": "succeeded"})
        self.assertEqual(terminal["status"], "succeeded")
        with self.assertRaisesRegex(AgentTaskQueueError, "cannot transition"):
            self.queue.transition_task("task-queue-004", {"status": "running"})

    def test_terminal_transition_after_review_does_not_release_reassigned_worker(self):
        self._register_worker("codex-01")
        for task_id in ("task-queue-old", "task-queue-new"):
            self.queue.create_task(
                {
                    "task_id": task_id,
                    "title": f"Task {task_id}",
                    "agent_type": "codex",
                    "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                    "target_ref": "main",
                }
            )

        self.queue.assign_task("task-queue-old")
        review = self.queue.transition_task("task-queue-old", {"status": "needs_review"})
        self.assertIsNone(review["assigned_worker_id"])

        new_running = self.queue.assign_task("task-queue-new")
        self.assertEqual(new_running["assigned_worker_id"], "codex-01")

        terminal = self.queue.transition_task("task-queue-old", {"status": "succeeded"})
        worker = self.worker_service.get_worker("codex-01")

        self.assertEqual(terminal["status"], "succeeded")
        self.assertEqual(worker["status"], "busy")
        self.assertEqual(worker["current_task_id"], "task-queue-new")

    def test_cancelling_running_task_releases_worker(self):
        self._register_worker("codex-01")
        self.queue.create_task(
            {
                "task_id": "task-queue-005",
                "title": "Cancelable task",
                "agent_type": "codex",
                "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                "target_ref": "main",
            }
        )
        self.queue.assign_task("task-queue-005")

        cancelled = self.queue.transition_task(
            "task-queue-005",
            {"status": "cancelled", "reason": "operator cancelled before execution"},
        )
        worker = self.worker_service.get_worker("codex-01")

        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["cancellation_reason"], "operator cancelled before execution")
        self.assertEqual(worker["status"], "ready")
        self.assertIsNone(worker["current_task_id"])


if __name__ == "__main__":
    unittest.main()
