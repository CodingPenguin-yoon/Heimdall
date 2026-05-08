"""Agent task queue contract for Heimdall workers.

This module intentionally does not execute shell, git, or agent commands. It
persists typed task intent and worker assignment state so Hermes can drive worker
execution through explicit lifecycle transitions.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy import select, update

from app.domains.workers.lifecycle import (
    AGENT_TASK_TERMINAL_STATES,
    can_transition_agent_task,
    normalize_agent_task_status,
)
from app.domains.workers.service import (
    AgentWorkerRegistryService,
    SUPPORTED_AGENT_TYPES,
    _contains_sensitive_marker,
)
from app.domains.workers.workspace_contract import (
    WorkerWorkspaceContractError,
    WorkerWorkspaceContractService,
)
from app.shared.platform_db import create_platform_engine, create_session_factory
from app.shared.platform_models import AgentTask, AgentWorker

AGENT_TASK_QUEUE_SCHEMA_VERSION = "heimdall.agent_task.v1"
TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
RAW_EXECUTION_FIELDS = frozenset(
    {
        "args",
        "argv",
        "cmd",
        "command",
        "commands",
        "commandline",
        "command_string",
        "commandoverride",
        "exec",
        "raw_command",
        "raw_shell",
        "raw_shell_command",
        "rawshell",
        "rawshellcommand",
        "runcommand",
        "script",
        "script_body",
        "scriptbody",
        "shell",
        "shell_command",
        "shellscript",
        "subprocess",
    }
)
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"https?://[^\s/@]+:[^\s/@]+@"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b"),
    re.compile(r"\bya29\.[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"\bssh-(?:rsa|ed25519)\s+[A-Za-z0-9+/=]{32,}"),
)
SECRET_LIKE_VALUE_PATTERN = re.compile(r"(?<![A-Za-z0-9_.+=-])[A-Za-z0-9_.+=-]{40,}(?![A-Za-z0-9_.+=-])")
BARE_SECRET_LIKE_VALUE_PATTERN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{40,}(?![A-Za-z0-9])")
RAW_COMMAND_VALUE_PATTERNS = (
    re.compile(r"(?i)(?:^|\s)(?:[/\w.-]*/)?(?:python|python3)\s+(?:-m|-c|[^\s]+\.py\b)[^\n]*"),
    re.compile(r"(?i)(?:^|\s)(?:[/\w.-]*/)?(?:pytest|make|go|cargo|yarn|npx|pnpm|npm|poetry|uv|tox|node|bash|sh|git|ssh|scp|curl|docker|kubectl|terraform|ansible-playbook|alembic)\s+[^\n]+"),
)
EXECUTION_BOUNDARY = {
    "raw_shell_allowed": False,
    "stores_credentials": False,
    "direct_vm_provisioning": False,
    "cross_project_mutation": False,
}


class AgentTaskQueueError(RuntimeError):
    """Raised when agent task queue payloads or transitions are invalid."""


class AgentTaskQueueService:
    """Persist and expose a minimal typed queue for Hermes-owned agent tasks."""

    def __init__(self, database_url: str | None = None) -> None:
        self._engine = create_platform_engine(database_url)
        self._session_factory = create_session_factory(self._engine)

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AgentTaskQueueError("agent task payload must be an object.")
        self._reject_forbidden_payload_fields(payload)
        task_id = self._normalize_task_id(payload.get("task_id"))
        title = self._required_text(
            payload.get("title"),
            "title",
            max_length=255,
            reject_sensitive=True,
        )
        agent_type = self._normalize_agent_type(payload.get("agent_type", "codex"))
        requested_status = self._normalize_status(payload.get("status", "queued"))
        if requested_status != "queued":
            raise AgentTaskQueueError("new agent tasks must start in queued status.")

        workspace_action_request = self._build_workspace_action_request(task_id, payload)
        labels = self._sanitize_labels(payload.get("labels"))
        required_capabilities = self._normalize_required_capabilities(
            payload.get("required_capabilities")
        )
        now = self._now_iso()
        with self._session_factory.begin() as session:
            if session.get(AgentTask, task_id) is not None:
                raise AgentTaskQueueError(f"agent task already exists: {task_id}")
            record = AgentTask(
                task_id=task_id,
                title=title,
                agent_type=agent_type,
                status="queued",
                assigned_worker_id=None,
                repo_url=workspace_action_request["repo_url"],
                target_ref=workspace_action_request["target_ref"],
                workspace_action_request_json=workspace_action_request,
                workspace_action_contract_json={},
                labels_json=labels,
                required_capabilities=required_capabilities,
                allocation_status="queued",
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.flush()
            return self._serialize_task(record)

    def list_tasks(self, *, status: str | None = None) -> list[dict[str, Any]]:
        normalized_status = self._normalize_status(status) if status else None
        with self._session_factory() as session:
            rows = session.execute(
                select(AgentTask).order_by(AgentTask.created_at.desc(), AgentTask.task_id.asc())
            ).scalars().all()
        tasks = [self._serialize_task(row) for row in rows]
        if normalized_status:
            tasks = [task for task in tasks if task["status"] == normalized_status]
        return tasks

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        normalized_task_id = self._normalize_task_id(task_id)
        with self._session_factory() as session:
            record = session.get(AgentTask, normalized_task_id)
            if record is None:
                return None
            return self._serialize_task(record)

    def assign_task(self, task_id: str) -> dict[str, Any]:
        normalized_task_id = self._normalize_task_id(task_id)
        now = self._now_iso()
        with self._session_factory.begin() as session:
            record = session.get(AgentTask, normalized_task_id)
            if record is None:
                raise AgentTaskQueueError(f"agent task not found: {normalized_task_id}")
            if record.status in AGENT_TASK_TERMINAL_STATES:
                raise AgentTaskQueueError(
                    f"cannot transition agent task {normalized_task_id} from {record.status} to running."
                )
            if record.status == "running":
                return self._serialize_task(record)
            if not can_transition_agent_task(record.status, "running"):
                raise AgentTaskQueueError(
                    f"cannot transition agent task {normalized_task_id} from {record.status} to running."
                )

            worker = self._select_worker_for_task(session, record)
            if worker is None:
                record.allocation_status = "no_ready_authenticated_worker"
                record.updated_at = now
                session.flush()
                return self._serialize_task(record)

            workspace_contract = self._build_workspace_action_contract(record, worker.worker_id)
            if not self._claim_worker_for_task(
                session,
                record,
                worker,
                workspace_contract,
                now=now,
            ):
                record.allocation_status = "worker_assignment_conflict"
                record.updated_at = now
                session.flush()
                return self._serialize_task(record)
            session.refresh(record)
            return self._serialize_task(record)

    def transition_task(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AgentTaskQueueError("agent task transition payload must be an object.")
        self._reject_forbidden_payload_fields(payload)
        target_status = self._normalize_status(payload.get("status"))
        if target_status == "running":
            return self.assign_task(task_id)

        normalized_task_id = self._normalize_task_id(task_id)
        reason = self._optional_text(
            payload.get("reason"),
            "reason",
            max_length=1024,
            reject_sensitive=True,
        )
        now = self._now_iso()
        with self._session_factory.begin() as session:
            record = session.get(AgentTask, normalized_task_id)
            if record is None:
                raise AgentTaskQueueError(f"agent task not found: {normalized_task_id}")
            if not can_transition_agent_task(record.status, target_status):
                raise AgentTaskQueueError(
                    f"cannot transition agent task {normalized_task_id} from {record.status} to {target_status}."
                )

            if target_status in {"needs_review", "failed", "succeeded", "cancelled"}:
                self._release_assigned_worker(session, record, now=now)
            if target_status == "needs_review":
                record.needs_review_reason = reason
                record.allocation_status = "released_for_review"
            elif target_status == "cancelled":
                record.cancellation_reason = reason
                record.allocation_status = "cancelled"
            elif target_status == "failed":
                record.failure_reason = reason
                record.allocation_status = "failed"
            elif target_status == "succeeded":
                record.allocation_status = "succeeded"

            if target_status in AGENT_TASK_TERMINAL_STATES:
                record.finished_at = now
            record.status = target_status
            record.updated_at = now
            session.flush()
            return self._serialize_task(record)

    @classmethod
    def _build_workspace_action_request(cls, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        action = cls._normalize_workspace_action(payload.get("workspace_action", "prepare_worktree"))
        repo_url = cls._normalize_repo_url(payload.get("repo_url"))
        target_ref = cls._required_text(
            payload.get("target_ref"),
            "target_ref",
            max_length=255,
            reject_sensitive=True,
        )
        request: dict[str, Any] = {
            "action": action,
            "repo_url": repo_url,
            "target_ref": target_ref,
            "dirty_tree_policy": cls._optional_text(
                payload.get("dirty_tree_policy"),
                "dirty_tree_policy",
                max_length=64,
                reject_sensitive=True,
            ) or "fail_if_dirty",
        }
        for field_name in ("default_branch", "repo_slug", "checkout_branch", "workspace_root"):
            value = cls._optional_text(
                payload.get(field_name),
                field_name,
                max_length=512,
                reject_sensitive=True,
            )
            if value is not None:
                request[field_name] = value

        cls._validate_workspace_action_request(task_id, request)
        return request

    @staticmethod
    def _validate_workspace_action_request(task_id: str, request: dict[str, Any]) -> None:
        validation_payload = {
            **request,
            "worker_id": "contract-worker",
            "task_id": task_id,
        }
        try:
            WorkerWorkspaceContractService.build_repo_action_contract(validation_payload)
        except WorkerWorkspaceContractError as exc:
            raise AgentTaskQueueError(str(exc)) from exc

    @staticmethod
    def _build_workspace_action_contract(record: AgentTask, worker_id: str) -> dict[str, Any]:
        request = dict(record.workspace_action_request_json or {})
        request["worker_id"] = worker_id
        request["task_id"] = record.task_id
        try:
            contract = WorkerWorkspaceContractService.build_repo_action_contract(request)
        except WorkerWorkspaceContractError as exc:
            raise AgentTaskQueueError(str(exc)) from exc
        contract["worker_id"] = worker_id
        contract["task_id"] = record.task_id
        return contract

    @staticmethod
    def _claim_worker_for_task(
        session: Any,
        record: AgentTask,
        worker: AgentWorker,
        workspace_contract: dict[str, Any],
        *,
        now: str,
    ) -> bool:
        worker_claim = session.execute(
            update(AgentWorker)
            .where(
                AgentWorker.worker_id == worker.worker_id,
                AgentWorker.status == "ready",
                AgentWorker.current_task_id.is_(None),
            )
            .values(
                status="busy",
                current_task_id=record.task_id,
                last_checked_at=now,
                updated_at=now,
            )
        )
        if worker_claim.rowcount != 1:
            return False

        task_claim = session.execute(
            update(AgentTask)
            .where(
                AgentTask.task_id == record.task_id,
                AgentTask.status == record.status,
                AgentTask.assigned_worker_id.is_(None),
            )
            .values(
                status="running",
                assigned_worker_id=worker.worker_id,
                workspace_action_contract_json=workspace_contract,
                allocation_status="assigned",
                started_at=record.started_at or now,
                updated_at=now,
            )
        )
        if task_claim.rowcount != 1:
            raise AgentTaskQueueError(
                f"agent task assignment conflict for {record.task_id}; retry assignment."
            )
        session.flush()
        return True

    def _select_worker_for_task(self, session: Any, record: AgentTask) -> AgentWorker | None:
        rows = session.execute(
            select(AgentWorker).order_by(AgentWorker.worker_id.asc())
        ).scalars().all()
        for worker in rows:
            if not self._worker_matches_task(worker, record):
                continue
            return worker
        return None

    @classmethod
    def _worker_matches_task(cls, worker: AgentWorker, record: AgentTask) -> bool:
        agent_types = list(worker.agent_types or [])
        if record.agent_type not in agent_types:
            return False
        if worker.status != "ready":
            return False
        if worker.current_task_id:
            return False
        auth_status = dict(worker.agent_auth_status or {}).get(record.agent_type, "unknown")
        if auth_status != "authenticated":
            return False
        if AgentWorkerRegistryService.is_worker_stale(worker.last_checked_at):
            return False
        required = set(record.required_capabilities or [])
        if not required:
            return True
        return required.issubset(cls._worker_capabilities(worker))

    @staticmethod
    def _worker_capabilities(worker: AgentWorker) -> set[str]:
        labels = dict(worker.labels_json or {})
        values: set[str] = set()
        for key in ("capability", "capabilities"):
            raw_value = labels.get(key)
            if isinstance(raw_value, str):
                values.add(raw_value)
            elif isinstance(raw_value, list):
                values.update(str(item) for item in raw_value if str(item or "").strip())
        return values

    @staticmethod
    def _release_assigned_worker(session: Any, record: AgentTask, *, now: str) -> None:
        assigned_worker_id = record.assigned_worker_id
        if not assigned_worker_id:
            return
        worker = session.get(AgentWorker, assigned_worker_id)
        if worker is not None and worker.current_task_id == record.task_id:
            worker.current_task_id = None
            if worker.status == "busy":
                worker.status = "ready"
            worker.last_checked_at = now
            worker.updated_at = now
        record.assigned_worker_id = None

    @classmethod
    def _normalize_task_id(cls, value: Any) -> str:
        task_id = cls._required_text(
            value,
            "task_id",
            max_length=64,
            reject_sensitive=True,
        )
        if task_id in {".", ".."}:
            raise AgentTaskQueueError("task_id must not be dot or dot-dot.")
        if TASK_ID_PATTERN.fullmatch(task_id) is None:
            raise AgentTaskQueueError(
                "task_id may only contain letters, numbers, dot, underscore, colon, or hyphen."
            )
        return task_id

    @staticmethod
    def _normalize_status(value: Any) -> str:
        try:
            return normalize_agent_task_status(value)
        except ValueError as exc:
            raise AgentTaskQueueError(str(exc)) from exc

    @staticmethod
    def _normalize_agent_type(value: Any) -> str:
        normalized = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
        if normalized not in SUPPORTED_AGENT_TYPES:
            raise AgentTaskQueueError(f"unsupported agent type: {value}")
        return normalized

    @staticmethod
    def _normalize_workspace_action(value: Any) -> str:
        action = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if action != "prepare_worktree":
            raise AgentTaskQueueError("agent task MVP supports prepare_worktree workspace action only.")
        return action

    @classmethod
    def _normalize_repo_url(cls, value: Any) -> str:
        repo_url = cls._required_text(
            value,
            "repo_url",
            max_length=2048,
            reject_sensitive=True,
        )
        if "?" in repo_url or "#" in repo_url:
            raise AgentTaskQueueError("repo_url must not contain query or fragment components.")
        return repo_url

    @classmethod
    def _normalize_required_capabilities(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            raise AgentTaskQueueError("required_capabilities must be a list of strings.")
        normalized = sorted(
            {
                cls._required_text(
                    item,
                    "required_capabilities",
                    max_length=64,
                    reject_sensitive=True,
                )
                for item in value
                if str(item or "").strip()
            }
        )
        return normalized

    @classmethod
    def _sanitize_labels(cls, raw_labels: Any) -> dict[str, Any]:
        if raw_labels is None:
            return {}
        if not isinstance(raw_labels, dict):
            raise AgentTaskQueueError("labels must be an object.")
        sanitized: dict[str, Any] = {}
        for raw_key, raw_value in raw_labels.items():
            key = str(raw_key or "").strip()
            if not key:
                continue
            cls._reject_forbidden_metadata_field(key, "labels")
            if len(key) > 128:
                raise AgentTaskQueueError("label keys must be 128 characters or fewer.")
            sanitized[key] = cls._sanitize_label_value(raw_value, f"labels.{key}")
        return sanitized

    @classmethod
    def _sanitize_label_value(cls, value: Any, field_name: str) -> Any:
        if isinstance(value, str):
            if len(value) > 512:
                raise AgentTaskQueueError(f"{field_name} must be 512 characters or fewer.")
            cls._reject_sensitive_text(value, field_name)
            return value
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            if len(value) > 32:
                raise AgentTaskQueueError(f"{field_name} must contain 32 items or fewer.")
            return [cls._sanitize_label_value(item, field_name) for item in value]
        raise AgentTaskQueueError(f"{field_name} must be a scalar or list of scalars.")

    @classmethod
    def _reject_forbidden_payload_fields(cls, payload: dict[str, Any]) -> None:
        for raw_field in payload:
            field = str(raw_field or "").strip()
            cls._reject_forbidden_metadata_field(field, "top-level")

    @classmethod
    def _reject_forbidden_metadata_field(cls, field: str, location: str) -> None:
        if cls._is_raw_execution_field(field):
            raise AgentTaskQueueError(f"raw execution field is not accepted in {location}: {field}")
        if _contains_sensitive_marker(field):
            raise AgentTaskQueueError(f"sensitive field is not accepted in {location}: {field}")

    @staticmethod
    def _is_raw_execution_field(field: str) -> bool:
        camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", field)
        lowered = camel_split.lower()
        normalized = lowered.replace("-", "_").replace(" ", "_")
        compact = re.sub(r"[^a-z0-9]", "", lowered)
        tokens = {token for token in re.split(r"[^a-z0-9]+", lowered) if token}
        raw_tokens = {"args", "argv", "cmd", "command", "exec", "rawshell", "script", "shell", "subprocess"}
        raw_compacts = {re.sub(r"[^a-z0-9]", "", name) for name in RAW_EXECUTION_FIELDS}
        return (
            normalized in RAW_EXECUTION_FIELDS
            or compact in raw_compacts
            or bool(tokens & raw_tokens)
        )

    @classmethod
    def _required_text(
        cls,
        value: Any,
        field_name: str,
        *,
        max_length: int | None = None,
        reject_sensitive: bool = False,
    ) -> str:
        text = str(value or "").strip()
        if not text:
            raise AgentTaskQueueError(f"{field_name} is required.")
        if max_length is not None and len(text) > max_length:
            raise AgentTaskQueueError(f"{field_name} must be {max_length} characters or fewer.")
        if reject_sensitive:
            cls._reject_sensitive_text(text, field_name)
        return text

    @classmethod
    def _reject_sensitive_text(cls, text: str, field_name: str) -> None:
        if _contains_sensitive_marker(text):
            raise AgentTaskQueueError(f"{field_name} contains sensitive material.")
        cls._reject_raw_command_text(text, field_name)
        for pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(text):
                raise AgentTaskQueueError(f"{field_name} contains sensitive material.")
        for candidate in BARE_SECRET_LIKE_VALUE_PATTERN.findall(text):
            has_alpha = any(char.isalpha() for char in candidate)
            has_digit = any(char.isdigit() for char in candidate)
            if has_alpha and has_digit:
                raise AgentTaskQueueError(f"{field_name} contains sensitive material.")
        for candidate in SECRET_LIKE_VALUE_PATTERN.findall(text):
            has_alpha = any(char.isalpha() for char in candidate)
            has_digit = any(char.isdigit() for char in candidate)
            has_symbol = any(not char.isalnum() for char in candidate)
            if has_alpha and has_digit and has_symbol:
                raise AgentTaskQueueError(f"{field_name} contains sensitive material.")

    @staticmethod
    def _reject_raw_command_text(text: str, field_name: str) -> None:
        for pattern in RAW_COMMAND_VALUE_PATTERNS:
            if pattern.search(text):
                raise AgentTaskQueueError(f"{field_name} contains raw execution material.")

    @classmethod
    def _optional_text(
        cls,
        value: Any,
        field_name: str,
        *,
        max_length: int | None = None,
        reject_sensitive: bool = False,
    ) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        return cls._required_text(
            text,
            field_name,
            max_length=max_length,
            reject_sensitive=reject_sensitive,
        )

    @classmethod
    def _serialize_task(cls, record: AgentTask) -> dict[str, Any]:
        return {
            "schema_version": AGENT_TASK_QUEUE_SCHEMA_VERSION,
            "task_id": record.task_id,
            "title": record.title,
            "agent_type": record.agent_type,
            "status": record.status,
            "assigned_worker_id": record.assigned_worker_id,
            "repo_url": record.repo_url,
            "target_ref": record.target_ref,
            "workspace_action_request": dict(record.workspace_action_request_json or {}),
            "workspace_action_contract": dict(record.workspace_action_contract_json or {}),
            "labels": dict(record.labels_json or {}),
            "required_capabilities": list(record.required_capabilities or []),
            "allocation_status": record.allocation_status,
            "needs_review_reason": record.needs_review_reason,
            "cancellation_reason": record.cancellation_reason,
            "failure_reason": record.failure_reason,
            "execution_boundary": dict(EXECUTION_BOUNDARY),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
        }

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
