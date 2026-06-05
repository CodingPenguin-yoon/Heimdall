from __future__ import annotations

import unittest

from app.domains.workers.workspace_contract import (
    DEFAULT_WORKSPACE_ROOT,
    WorkerWorkspaceContractError,
    WorkerWorkspaceContractService,
)


class WorkerWorkspaceContractTest(unittest.TestCase):
    def test_workspace_layout_is_deterministic_and_keeps_artifacts_outside_repo(self):
        layout = WorkerWorkspaceContractService.build_workspace_layout(
            {
                "worker_id": "codex-01",
                "task_id": "task-123",
                "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
            }
        )

        self.assertEqual(layout["workspace_root"], DEFAULT_WORKSPACE_ROOT)
        self.assertEqual(layout["worker_root"], f"{DEFAULT_WORKSPACE_ROOT}/codex-01")
        self.assertEqual(
            layout["repo_cache_path"],
            f"{DEFAULT_WORKSPACE_ROOT}/codex-01/repos/Heimdall/cache.git",
        )
        self.assertEqual(
            layout["worktree_path"],
            f"{DEFAULT_WORKSPACE_ROOT}/codex-01/worktrees/task-123/Heimdall",
        )
        self.assertEqual(
            layout["verification_report_path"],
            f"{DEFAULT_WORKSPACE_ROOT}/codex-01/runs/task-123/artifacts/verification-report.json",
        )
        self.assertNotIn("/artifacts/", layout["worktree_path"])
        self.assertFalse(layout["verification_report_path"].startswith(layout["worktree_path"]))

    def test_prepare_worktree_action_uses_typed_steps_and_task_branch(self):
        contract = WorkerWorkspaceContractService.build_repo_action_contract(
            {
                "action": "prepare_worktree",
                "worker_id": "codex-01",
                "task_id": "task-456",
                "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                "target_ref": "main",
            }
        )

        self.assertEqual(contract["schema_version"], "heimdall.worker_repo_action.v1")
        self.assertEqual(contract["action"], "prepare_worktree")
        self.assertEqual(contract["checkout_branch"], "heimdall/task-456/Heimdall")
        self.assertEqual(contract["dirty_tree_policy"], "fail_if_dirty")
        self.assertEqual(
            contract["typed_steps"],
            [
                "repo.ensure_cache",
                "repo.fetch",
                "worktree.create_or_reuse_branch",
                "worktree.require_clean_before_reuse",
            ],
        )
        self.assertFalse(contract["execution_boundary"]["raw_shell_allowed"])
        self.assertFalse(contract["execution_boundary"]["stores_credentials"])

    def test_reset_action_requires_clean_tree_guard_and_target_ref(self):
        with self.assertRaisesRegex(WorkerWorkspaceContractError, "target_ref is required"):
            WorkerWorkspaceContractService.build_repo_action_contract(
                {
                    "action": "reset",
                    "worker_id": "codex-01",
                    "task_id": "task-456",
                    "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                }
            )

        contract = WorkerWorkspaceContractService.build_repo_action_contract(
            {
                "action": "reset",
                "worker_id": "codex-01",
                "task_id": "task-456",
                "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                "target_ref": "origin/main",
                "checkout_branch": "heimdall/task-456/reset-check",
            }
        )

        self.assertEqual(contract["dirty_tree_policy"], "fail_if_dirty")
        self.assertIn("worktree.require_clean", contract["typed_steps"])
        self.assertIn(
            {"kind": "dirty_tree", "policy": "fail_if_dirty"},
            contract["preflight_checks"],
        )

    def test_status_action_is_read_only(self):
        contract = WorkerWorkspaceContractService.build_repo_action_contract(
            {
                "action": "status",
                "worker_id": "codex-01",
                "task_id": "task-789",
                "repo_url": "https://github.com/CodingPenguin-yoon/Heimdall.git",
            }
        )

        self.assertEqual(contract["dirty_tree_policy"], "read_only_status")
        self.assertEqual(contract["typed_steps"], ["worktree.status_read_only"])

    def test_contract_rejects_raw_shell_and_sensitive_fields(self):
        with self.assertRaisesRegex(WorkerWorkspaceContractError, "raw execution field"):
            WorkerWorkspaceContractService.build_repo_action_contract(
                {
                    "action": "status",
                    "worker_id": "codex-01",
                    "task_id": "task-789",
                    "repo_url": "https://github.com/CodingPenguin-yoon/Heimdall.git",
                    "raw_shell": "git status && env",
                }
            )

        with self.assertRaisesRegex(WorkerWorkspaceContractError, "sensitive top-level field"):
            WorkerWorkspaceContractService.build_workspace_layout(
                {
                    "worker_id": "codex-01",
                    "task_id": "task-789",
                    "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                    "oauth_token": "SHOULD_NOT_BE_STORED",
                }
            )

        with self.assertRaisesRegex(WorkerWorkspaceContractError, "inline credentials|sensitive"):
            WorkerWorkspaceContractService.build_repo_action_contract(
                {
                    "action": "clone",
                    "worker_id": "codex-01",
                    "task_id": "task-789",
                    "repo_url": "https://" + "user" + "@example.com/org/repo.git",
                }
            )

    def test_branch_and_workspace_inputs_reject_unsafe_values(self):
        with self.assertRaisesRegex(WorkerWorkspaceContractError, "checkout_branch is not a safe git ref"):
            WorkerWorkspaceContractService.build_repo_action_contract(
                {
                    "action": "prepare_worktree",
                    "worker_id": "codex-01",
                    "task_id": "task-456",
                    "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                    "target_ref": "main",
                    "checkout_branch": "../main",
                }
            )

        with self.assertRaisesRegex(WorkerWorkspaceContractError, "workspace_root must be an absolute"):
            WorkerWorkspaceContractService.build_workspace_layout(
                {
                    "worker_id": "codex-01",
                    "task_id": "task-456",
                    "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                    "workspace_root": "relative/workspaces",
                }
            )


    def test_worker_and_task_identifiers_reject_dot_segments(self):
        for field_name, value in (("worker_id", ".."), ("worker_id", "."), ("task_id", ".."), ("task_id", ".")):
            with self.subTest(field_name=field_name, value=value):
                payload = {
                    "worker_id": "codex-01",
                    "task_id": "task-456",
                    "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                }
                payload[field_name] = value
                with self.assertRaisesRegex(WorkerWorkspaceContractError, f"{field_name} must not be dot"):
                    WorkerWorkspaceContractService.build_workspace_layout(payload)

    def test_credentialed_ssh_repo_urls_are_rejected(self):
        for index, repo_url in enumerate((
            "ssh://" + "user" + ":" + "pass" + "@example.com/org/repo.git",
            "git+ssh://" + "user" + ":" + "pass" + "@example.com/org/repo.git",
        )):
            with self.subTest(index=index):
                with self.assertRaisesRegex(WorkerWorkspaceContractError, "inline credentials|sensitive"):
                    WorkerWorkspaceContractService.build_repo_action_contract(
                        {
                            "action": "clone",
                            "worker_id": "codex-01",
                            "task_id": "task-789",
                            "repo_url": repo_url,
                        }
                    )
                with self.assertRaisesRegex(WorkerWorkspaceContractError, "inline credentials|sensitive"):
                    WorkerWorkspaceContractService.build_workspace_layout(
                        {
                            "worker_id": "codex-01",
                            "task_id": "task-789",
                            "repo_url": repo_url,
                            "repo_slug": "repo",
                        }
                    )

    def test_prepare_worktree_rejects_read_only_dirty_policy(self):
        with self.assertRaisesRegex(WorkerWorkspaceContractError, "prepare_worktree requires"):
            WorkerWorkspaceContractService.build_repo_action_contract(
                {
                    "action": "prepare_worktree",
                    "worker_id": "codex-01",
                    "task_id": "task-456",
                    "repo_url": "git@github.com:CodingPenguin-yoon/Heimdall.git",
                    "target_ref": "main",
                    "dirty_tree_policy": "read_only_status",
                }
            )

    def test_raw_shell_alias_fields_are_rejected_fail_closed(self):
        for field_name in ("shell_command", "raw_shell_command", "commands", "command_string"):
            with self.subTest(field_name=field_name):
                payload = {
                    "action": "status",
                    "worker_id": "codex-01",
                    "task_id": "task-789",
                    "repo_url": "https://github.com/CodingPenguin-yoon/Heimdall.git",
                    field_name: "git status",
                }
                with self.assertRaisesRegex(WorkerWorkspaceContractError, "raw execution field"):
                    WorkerWorkspaceContractService.build_repo_action_contract(payload)



if __name__ == "__main__":
    unittest.main()
