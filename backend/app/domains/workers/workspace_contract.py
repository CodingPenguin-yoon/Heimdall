"""Worker workspace and repository execution contract.

This module intentionally does not execute git, shell, or agent commands. It
normalizes the typed metadata Heimdall will later hand to a worker-side executor
so policy can be tested before any execution adapter exists.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse


DEFAULT_WORKSPACE_ROOT = "/var/lib/heimdall/workers"
WORKSPACE_ROOT_ENV = "HEIMDALL_WORKER_WORKSPACE_ROOT"
SUPPORTED_REPO_ACTIONS = (
    "clone",
    "fetch",
    "prepare_worktree",
    "reset",
    "status",
)
SUPPORTED_DIRTY_TREE_POLICIES = (
    "fail_if_dirty",
    "read_only_status",
)
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
SAFE_REPO_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x1f\x7f]")

SENSITIVE_MARKERS = (
    "token",
    "secret",
    "password",
    "credential",
    "api key",
    "api_key",
    "apikey",
    "api-key",
    "authorization",
    "bearer",
    "private key",
    "private_key",
    "private-key",
    "ssh key",
    "ssh_key",
    "ssh-key",
    "auth file",
    "auth_file",
    "authfile",
    "auth-file",
)
SENSITIVE_KEY_PARTS = tuple(
    sorted({re.sub(r"[^a-z0-9]", "", marker.lower()) for marker in SENSITIVE_MARKERS})
)
RAW_EXECUTION_FIELD_NAMES = {
    "args",
    "argv",
    "cmd",
    "command",
    "commandline",
    "exec",
    "rawshell",
    "script",
    "shell",
    "subprocess",
}
RAW_EXECUTION_FIELD_PARTS = (
    "rawshell",
    "shell",
    "command",
    "cmd",
    "exec",
    "subprocess",
    "script",
    "argv",
    "args",
)


class WorkerWorkspaceContractError(RuntimeError):
    """Raised when workspace/repo execution contract metadata is unsafe."""


class WorkerWorkspaceContractService:
    """Build deterministic worker workspace and repo action contracts."""

    @classmethod
    def build_workspace_layout(cls, payload: dict[str, Any]) -> dict[str, str]:
        cls._reject_non_contract_fields(payload)
        worker_id = cls._normalize_identifier(payload.get("worker_id"), "worker_id")
        task_id = cls._normalize_identifier(payload.get("task_id"), "task_id")
        repo_url = None
        if payload.get("repo_url") is not None:
            repo_url = cls._normalize_repo_url(payload.get("repo_url"))
        repo_slug = cls._normalize_repo_slug(
            payload.get("repo_slug") or cls._repo_slug_from_url(repo_url)
        )
        root = cls._normalize_workspace_root(
            payload.get("workspace_root") or DEFAULT_WORKSPACE_ROOT
        )

        worker_root = cls._join_posix(root, worker_id)
        repo_root = cls._join_posix(worker_root, "repos", repo_slug)
        repo_cache_path = cls._join_posix(repo_root, "cache.git")
        worktree_path = cls._join_posix(worker_root, "worktrees", task_id, repo_slug)
        run_root = cls._join_posix(worker_root, "runs", task_id)
        logs_path = cls._join_posix(run_root, "logs")
        artifacts_path = cls._join_posix(run_root, "artifacts")

        return {
            "workspace_root_env": WORKSPACE_ROOT_ENV,
            "workspace_root": root,
            "worker_root": worker_root,
            "repo_root": repo_root,
            "repo_cache_path": repo_cache_path,
            "worktree_path": worktree_path,
            "run_root": run_root,
            "logs_path": logs_path,
            "worker_log_path": cls._join_posix(logs_path, "worker.log"),
            "verification_log_path": cls._join_posix(logs_path, "verification.log"),
            "artifacts_path": artifacts_path,
            "verification_report_path": cls._join_posix(
                artifacts_path,
                "verification-report.json",
            ),
        }

    @classmethod
    def build_repo_action_contract(cls, payload: dict[str, Any]) -> dict[str, Any]:
        cls._reject_non_contract_fields(payload)
        action = cls._normalize_action(payload.get("action"))
        repo_url = cls._normalize_repo_url(payload.get("repo_url"))
        layout = cls.build_workspace_layout(payload)
        default_branch = cls._normalize_git_ref(
            payload.get("default_branch") or "main",
            "default_branch",
        )
        target_ref = cls._normalize_optional_git_ref(payload.get("target_ref"), "target_ref")
        checkout_branch = cls._normalize_optional_git_ref(
            payload.get("checkout_branch"),
            "checkout_branch",
        ) or cls._default_task_branch(payload.get("task_id"), payload.get("repo_slug") or repo_url)
        dirty_tree_policy = cls._normalize_dirty_tree_policy(
            payload.get("dirty_tree_policy"),
            action=action,
        )

        if action in {"prepare_worktree", "reset"} and not target_ref:
            raise WorkerWorkspaceContractError(f"target_ref is required for {action} actions.")
        if action in {"prepare_worktree", "reset"} and dirty_tree_policy != "fail_if_dirty":
            raise WorkerWorkspaceContractError(
                f"{action} requires dirty_tree_policy=fail_if_dirty."
            )

        typed_steps = cls._typed_steps_for_action(action)
        return {
            "schema_version": "heimdall.worker_repo_action.v1",
            "action": action,
            "repo_url": repo_url,
            "default_branch": default_branch,
            "target_ref": target_ref,
            "checkout_branch": checkout_branch,
            "dirty_tree_policy": dirty_tree_policy,
            "layout": layout,
            "preflight_checks": cls._preflight_checks(action, dirty_tree_policy),
            "typed_steps": typed_steps,
            "execution_boundary": {
                "raw_shell_allowed": False,
                "stores_credentials": False,
                "destructive_without_clean_tree": False,
                "artifacts_inside_repo": False,
            },
        }

    @classmethod
    def _typed_steps_for_action(cls, action: str) -> list[str]:
        steps_by_action = {
            "clone": ["repo.ensure_cache"],
            "fetch": ["repo.require_cache", "repo.fetch"],
            "prepare_worktree": [
                "repo.ensure_cache",
                "repo.fetch",
                "worktree.create_or_reuse_branch",
                "worktree.require_clean_before_reuse",
            ],
            "reset": [
                "worktree.require_clean",
                "repo.fetch",
                "worktree.reset_to_ref",
            ],
            "status": ["worktree.status_read_only"],
        }
        return list(steps_by_action[action])

    @classmethod
    def _preflight_checks(cls, action: str, dirty_tree_policy: str) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = [
            {"kind": "repo_url_non_credentialed"},
            {"kind": "workspace_paths_outside_repo"},
            {"kind": "raw_shell_forbidden"},
        ]
        if action in {"prepare_worktree", "reset", "status"}:
            checks.append({"kind": "dirty_tree", "policy": dirty_tree_policy})
        return checks

    @classmethod
    def _default_task_branch(cls, task_id: Any, repo_slug_source: Any) -> str:
        task = cls._normalize_identifier(task_id, "task_id")
        slug = cls._normalize_repo_slug(cls._repo_slug_from_url(repo_slug_source))
        return f"heimdall/{task}/{slug}"

    @classmethod
    def _normalize_action(cls, value: Any) -> str:
        action = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if action not in SUPPORTED_REPO_ACTIONS:
            raise WorkerWorkspaceContractError(
                f"action must be one of: {', '.join(SUPPORTED_REPO_ACTIONS)}."
            )
        return action

    @classmethod
    def _normalize_dirty_tree_policy(cls, value: Any, *, action: str) -> str:
        if value is None:
            return "read_only_status" if action == "status" else "fail_if_dirty"
        policy = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if policy not in SUPPORTED_DIRTY_TREE_POLICIES:
            raise WorkerWorkspaceContractError(
                f"dirty_tree_policy must be one of: {', '.join(SUPPORTED_DIRTY_TREE_POLICIES)}."
            )
        return policy

    @classmethod
    def _normalize_workspace_root(cls, value: Any) -> str:
        root = cls._required_text(value, "workspace_root", max_length=512, reject_sensitive=True)
        if CONTROL_CHARACTER_PATTERN.search(root):
            raise WorkerWorkspaceContractError("workspace_root contains control characters.")
        path = PurePosixPath(root)
        if not path.is_absolute():
            raise WorkerWorkspaceContractError("workspace_root must be an absolute POSIX path.")
        if any(part in {"", ".", ".."} for part in path.parts[1:]):
            raise WorkerWorkspaceContractError("workspace_root must not contain empty, dot, or dot-dot parts.")
        return str(path)

    @classmethod
    def _normalize_repo_url(cls, value: Any) -> str:
        repo_url = cls._required_text(value, "repo_url", max_length=2048, reject_sensitive=True)
        if CONTROL_CHARACTER_PATTERN.search(repo_url):
            raise WorkerWorkspaceContractError("repo_url contains control characters.")
        parsed = urlparse(repo_url)
        if parsed.scheme and parsed.netloc:
            if parsed.password:
                raise WorkerWorkspaceContractError("repo_url must not include inline credentials.")
            if parsed.username == "oauth2":
                raise WorkerWorkspaceContractError("repo_url must not include OAuth credential users.")
            if parsed.scheme in {"http", "https"} and parsed.username:
                raise WorkerWorkspaceContractError("repo_url must not include inline credentials.")
        return repo_url

    @classmethod
    def _repo_slug_from_url(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise WorkerWorkspaceContractError("repo_url or repo_slug is required.")
        cls._reject_sensitive_text(text, "repo_url")
        candidate = text.rstrip("/").rsplit("/", 1)[-1]
        if ":" in candidate:
            candidate = candidate.rsplit(":", 1)[-1]
        if candidate.endswith(".git"):
            candidate = candidate[:-4]
        return candidate

    @classmethod
    def _normalize_repo_slug(cls, value: Any) -> str:
        slug = cls._required_text(value, "repo_slug", max_length=96, reject_sensitive=True)
        slug = re.sub(r"[^A-Za-z0-9_.:-]+", "-", slug).strip(".-_")
        if not slug or SAFE_REPO_SLUG_PATTERN.fullmatch(slug) is None:
            raise WorkerWorkspaceContractError(
                "repo_slug may only contain letters, numbers, dot, underscore, colon, or hyphen."
            )
        if slug in {".", ".."}:
            raise WorkerWorkspaceContractError("repo_slug must not be dot or dot-dot.")
        return slug

    @classmethod
    def _normalize_identifier(cls, value: Any, field_name: str) -> str:
        identifier = cls._required_text(value, field_name, max_length=64, reject_sensitive=True)
        if SAFE_IDENTIFIER_PATTERN.fullmatch(identifier) is None:
            raise WorkerWorkspaceContractError(
                f"{field_name} may only contain letters, numbers, dot, underscore, colon, or hyphen."
            )
        if identifier in {".", ".."}:
            raise WorkerWorkspaceContractError(f"{field_name} must not be dot or dot-dot.")
        return identifier

    @classmethod
    def _normalize_optional_git_ref(cls, value: Any, field_name: str) -> str | None:
        if value is None:
            return None
        text = str(value or "").strip()
        if not text:
            return None
        return cls._normalize_git_ref(text, field_name)

    @classmethod
    def _normalize_git_ref(cls, value: Any, field_name: str) -> str:
        ref = cls._required_text(value, field_name, max_length=255, reject_sensitive=True)
        if CONTROL_CHARACTER_PATTERN.search(ref):
            raise WorkerWorkspaceContractError(f"{field_name} contains control characters.")
        invalid = (
            ref.startswith("/")
            or ref.endswith("/")
            or ref.startswith("-")
            or ".." in ref
            or "//" in ref
            or "@{" in ref
            or "\\" in ref
            or ref.endswith(".lock")
            or any(part in {"", ".", ".."} for part in ref.split("/"))
        )
        if invalid or any(char.isspace() for char in ref):
            raise WorkerWorkspaceContractError(f"{field_name} is not a safe git ref name.")
        return ref

    @classmethod
    def _reject_non_contract_fields(cls, payload: Any) -> None:
        if not isinstance(payload, dict):
            raise WorkerWorkspaceContractError("workspace/repo contract payload must be an object.")
        for field_name in payload:
            normalized = re.sub(r"[^a-z0-9]", "", str(field_name).lower())
            if normalized in RAW_EXECUTION_FIELD_NAMES or any(
                part in normalized for part in RAW_EXECUTION_FIELD_PARTS
            ):
                raise WorkerWorkspaceContractError(
                    f"raw execution field is not accepted: {field_name}"
                )
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                raise WorkerWorkspaceContractError(
                    f"sensitive top-level field is not accepted: {field_name}"
                )

    @staticmethod
    def _required_text(
        value: Any,
        field_name: str,
        *,
        max_length: int | None = None,
        reject_sensitive: bool = False,
    ) -> str:
        text = str(value or "").strip()
        if not text:
            raise WorkerWorkspaceContractError(f"{field_name} is required.")
        if max_length is not None and len(text) > max_length:
            raise WorkerWorkspaceContractError(f"{field_name} must be {max_length} characters or fewer.")
        if reject_sensitive:
            WorkerWorkspaceContractService._reject_sensitive_text(text, field_name)
        return text

    @staticmethod
    def _reject_sensitive_text(value: str, field_name: str) -> None:
        normalized = re.sub(r"[^a-z0-9]", "", value.lower())
        if any(part in normalized for part in SENSITIVE_KEY_PARTS):
            raise WorkerWorkspaceContractError(f"{field_name} contains sensitive material.")

    @staticmethod
    def _join_posix(root: str, *parts: str) -> str:
        return str(PurePosixPath(root).joinpath(*parts))
