"""Agent task evidence contract for logs, artifacts, and verification reports.

This module intentionally stores typed evidence metadata only. It does not execute
worker commands, capture credentials, or store raw secret-bearing logs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
import re
from typing import Any

from sqlalchemy import func, select

from app.domains.workers.service import _contains_sensitive_marker
from app.domains.workers.task_queue import AgentTaskQueueService
from app.shared.platform_db import create_platform_engine, create_session_factory
from app.shared.platform_models import (
    AgentTask,
    AgentTaskArtifact,
    AgentTaskEvent,
    AgentTaskVerificationReport,
)

TASK_EVENT_SCHEMA_VERSION = "heimdall.agent_task_event.v1"
TASK_ARTIFACT_SCHEMA_VERSION = "heimdall.agent_task_artifact.v1"
VERIFICATION_REPORT_SCHEMA_VERSION = "heimdall.agent_task_verification_report.v1"
SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
SHA256_PATTERN = re.compile(r"^[A-Fa-f0-9]{64}$")
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
COMMAND_LABEL_FORBIDDEN_CHARS = re.compile(r"[\\/;&|$`<>\n\r]")
COMMAND_LABEL_EXECUTABLE_PREFIXES = {
    "alembic",
    "ansible",
    "ansible-playbook",
    "bash",
    "cargo",
    "curl",
    "docker",
    "git",
    "go",
    "kubectl",
    "make",
    "node",
    "npm",
    "npx",
    "pnpm",
    "poetry",
    "pytest",
    "python",
    "python3",
    "scp",
    "sh",
    "ssh",
    "terraform",
    "tox",
    "uv",
    "yarn",
}
SUPPORTED_EVENT_SEVERITIES = ("debug", "info", "warning", "error")
SUPPORTED_ARTIFACT_TYPES = (
    "verification_report",
    "log",
    "diff",
    "test_output",
    "build_output",
    "static_scan",
    "other",
)
SUPPORTED_REPORT_STATUSES = ("pass", "fail", "blocked")
SUPPORTED_CHECK_STATUSES = ("pass", "fail", "warning", "skipped", "blocked")
EVIDENCE_RETENTION_POLICY = {
    "scope": "task_run_evidence",
    "storage": "worker_run_root",
    "artifacts_inside_repo": False,
    "secrets_allowed": False,
    "delete_requires_operator_policy": True,
}
COMMAND_LABEL_FIELD_NAME = "command_label"


class AgentTaskEvidenceError(RuntimeError):
    """Raised when task evidence payloads are unsafe or invalid."""


class AgentTaskEvidenceService:
    """Persist typed evidence linked to an AgentTask."""

    def __init__(self, database_url: str | None = None) -> None:
        self._engine = create_platform_engine(database_url)
        self._session_factory = create_session_factory(self._engine)

    def append_task_event(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AgentTaskEvidenceError("task event payload must be an object.")
        self._reject_forbidden_metadata_deep(payload, "task event payload")
        normalized_task_id = self._normalize_id(task_id, "task_id")
        event_type = self._required_text(payload.get("event_type"), "event_type", max_length=64)
        severity = self._normalize_choice(
            payload.get("severity", "info"),
            "severity",
            SUPPORTED_EVENT_SEVERITIES,
        )
        source = self._optional_text(payload.get("source"), "source", max_length=64) or "worker"
        message = self._required_text(payload.get("message"), "message", max_length=4096)
        metadata = self._sanitize_metadata(payload.get("metadata"), "metadata")
        now = self._now_iso()

        with self._session_factory.begin() as session:
            self._get_task_or_raise(session, normalized_task_id)
            current_sequence = session.scalar(
                select(func.max(AgentTaskEvent.sequence)).where(
                    AgentTaskEvent.task_id == normalized_task_id
                )
            ) or 0
            record = AgentTaskEvent(
                task_id=normalized_task_id,
                sequence=int(current_sequence) + 1,
                event_type=event_type,
                severity=severity,
                source=source,
                message=message,
                metadata_json=metadata,
                created_at=now,
            )
            session.add(record)
            session.flush()
            return self._serialize_event(record)

    def list_task_events(self, task_id: str) -> list[dict[str, Any]]:
        normalized_task_id = self._normalize_id(task_id, "task_id")
        with self._session_factory() as session:
            self._get_task_or_raise(session, normalized_task_id)
            rows = session.execute(
                select(AgentTaskEvent)
                .where(AgentTaskEvent.task_id == normalized_task_id)
                .order_by(AgentTaskEvent.sequence.asc())
            ).scalars().all()
        return [self._serialize_event(row) for row in rows]

    def register_task_artifact(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AgentTaskEvidenceError("task artifact payload must be an object.")
        self._reject_forbidden_metadata_deep(
            {key: value for key, value in payload.items() if key != "sha256"},
            "task artifact payload",
        )
        normalized_task_id = self._normalize_id(task_id, "task_id")
        artifact_id = self._normalize_id(payload.get("artifact_id"), "artifact_id")
        artifact_type = self._normalize_choice(
            payload.get("artifact_type", "other"),
            "artifact_type",
            SUPPORTED_ARTIFACT_TYPES,
        )
        relative_path = self._normalize_relative_path(payload.get("relative_path"))
        display_name = self._optional_text(payload.get("display_name"), "display_name", max_length=255)
        media_type = self._optional_text(payload.get("media_type"), "media_type", max_length=128)
        size_bytes = self._normalize_optional_non_negative_int(payload.get("size_bytes"), "size_bytes")
        sha256 = self._normalize_optional_sha256(payload.get("sha256"))
        metadata = self._sanitize_metadata(payload.get("metadata"), "metadata")
        now = self._now_iso()

        with self._session_factory.begin() as session:
            task = self._get_task_or_raise(session, normalized_task_id)
            if self._get_task_artifact(session, normalized_task_id, artifact_id) is not None:
                raise AgentTaskEvidenceError(f"agent task artifact already exists: {artifact_id}")
            layout = self._task_layout(task)
            artifact_path = self._join_under_artifacts(layout, relative_path)
            record = AgentTaskArtifact(
                artifact_id=artifact_id,
                task_id=normalized_task_id,
                artifact_type=artifact_type,
                relative_path=relative_path,
                path=artifact_path,
                display_name=display_name,
                media_type=media_type,
                size_bytes=size_bytes,
                sha256=sha256,
                metadata_json=metadata,
                created_at=now,
            )
            session.add(record)
            session.flush()
            return self._serialize_artifact(record)

    def list_task_artifacts(self, task_id: str) -> list[dict[str, Any]]:
        normalized_task_id = self._normalize_id(task_id, "task_id")
        with self._session_factory() as session:
            self._get_task_or_raise(session, normalized_task_id)
            rows = session.execute(
                select(AgentTaskArtifact)
                .where(AgentTaskArtifact.task_id == normalized_task_id)
                .order_by(AgentTaskArtifact.created_at.asc(), AgentTaskArtifact.artifact_id.asc())
            ).scalars().all()
        return [self._serialize_artifact(row) for row in rows]

    def submit_verification_report(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AgentTaskEvidenceError("verification report payload must be an object.")
        self._reject_forbidden_metadata_deep(
            {key: value for key, value in payload.items() if key != "checks"},
            "verification report payload",
        )
        normalized_task_id = self._normalize_id(task_id, "task_id")
        report_id = self._normalize_id(payload.get("report_id"), "report_id")
        status = self._normalize_choice(payload.get("status"), "status", SUPPORTED_REPORT_STATUSES)
        summary = self._required_text(payload.get("summary"), "summary", max_length=2048)
        checks = self._normalize_checks(payload.get("checks"))
        explicit_artifact_ids = self._normalize_artifact_ids(payload.get("artifact_ids"))
        check_artifact_ids = [check["artifact_id"] for check in checks if check.get("artifact_id")]
        artifact_ids = sorted(set(explicit_artifact_ids + check_artifact_ids))
        metadata = self._sanitize_metadata(payload.get("metadata"), "metadata")
        now = self._now_iso()

        with self._session_factory.begin() as session:
            self._get_task_or_raise(session, normalized_task_id)
            if self._get_task_verification_report(session, normalized_task_id, report_id) is not None:
                raise AgentTaskEvidenceError(
                    f"agent task verification report already exists: {report_id}"
                )
            self._require_task_artifacts(session, normalized_task_id, artifact_ids)
            record = AgentTaskVerificationReport(
                report_id=report_id,
                task_id=normalized_task_id,
                status=status,
                summary=summary,
                checks_json=checks,
                artifact_ids=artifact_ids,
                metadata_json=metadata,
                created_at=now,
            )
            session.add(record)
            session.flush()
            return self._serialize_report(record)

    def list_verification_reports(self, task_id: str) -> list[dict[str, Any]]:
        normalized_task_id = self._normalize_id(task_id, "task_id")
        with self._session_factory() as session:
            self._get_task_or_raise(session, normalized_task_id)
            rows = session.execute(
                select(AgentTaskVerificationReport)
                .where(AgentTaskVerificationReport.task_id == normalized_task_id)
                .order_by(
                    AgentTaskVerificationReport.created_at.asc(),
                    AgentTaskVerificationReport.report_id.asc(),
                )
            ).scalars().all()
        return [self._serialize_report(row) for row in rows]

    @staticmethod
    def _get_task_or_raise(session: Any, task_id: str) -> AgentTask:
        task = session.get(AgentTask, task_id)
        if task is None:
            raise AgentTaskEvidenceError(f"agent task not found: {task_id}")
        return task

    @staticmethod
    def _get_task_artifact(session: Any, task_id: str, artifact_id: str) -> AgentTaskArtifact | None:
        return session.scalar(
            select(AgentTaskArtifact).where(
                AgentTaskArtifact.task_id == task_id,
                AgentTaskArtifact.artifact_id == artifact_id,
            )
        )

    @staticmethod
    def _get_task_verification_report(
        session: Any,
        task_id: str,
        report_id: str,
    ) -> AgentTaskVerificationReport | None:
        return session.scalar(
            select(AgentTaskVerificationReport).where(
                AgentTaskVerificationReport.task_id == task_id,
                AgentTaskVerificationReport.report_id == report_id,
            )
        )

    @classmethod
    def _task_layout(cls, task: AgentTask) -> dict[str, Any]:
        contract = dict(task.workspace_action_contract_json or {})
        layout = contract.get("layout")
        if not isinstance(layout, dict) or not layout.get("artifacts_path"):
            raise AgentTaskEvidenceError(
                "workspace action contract is required before artifact registration."
            )
        return layout

    @classmethod
    def _join_under_artifacts(cls, layout: dict[str, Any], relative_path: str) -> str:
        artifacts_root = cls._required_text(
            layout.get("artifacts_path"),
            "artifacts_path",
            max_length=1024,
            reject_sensitive=False,
        )
        worktree_path = cls._optional_text(
            layout.get("worktree_path"),
            "worktree_path",
            max_length=1024,
            reject_sensitive=False,
        )
        run_root = cls._required_text(
            layout.get("run_root"),
            "run_root",
            max_length=1024,
            reject_sensitive=False,
        )
        expected_artifacts_root = str(PurePosixPath(run_root) / "artifacts")
        if artifacts_root != expected_artifacts_root:
            raise AgentTaskEvidenceError("artifacts_path must be the task run_root/artifacts path.")
        artifact_path = str(PurePosixPath(artifacts_root) / relative_path)
        if artifact_path != artifacts_root and not artifact_path.startswith(f"{artifacts_root}/"):
            raise AgentTaskEvidenceError("relative_path must remain under the task artifacts path.")
        if worktree_path and (artifact_path == worktree_path or artifact_path.startswith(f"{worktree_path}/")):
            raise AgentTaskEvidenceError("artifacts must not be stored inside the worktree path.")
        return artifact_path

    @classmethod
    def _normalize_checks(cls, value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise AgentTaskEvidenceError("checks must be a list of objects.")
        if len(value) > 64:
            raise AgentTaskEvidenceError("checks must contain 64 items or fewer.")
        checks: list[dict[str, Any]] = []
        for raw_check in value:
            if not isinstance(raw_check, dict):
                raise AgentTaskEvidenceError("each verification check must be an object.")
            cls._reject_forbidden_metadata_deep(
                raw_check,
                "verification check",
                command_label_allowed=True,
            )
            check = {
                "name": cls._required_text(raw_check.get("name"), "check.name", max_length=128),
                "status": cls._normalize_choice(
                    raw_check.get("status"),
                    "check.status",
                    SUPPORTED_CHECK_STATUSES,
                ),
            }
            command_label = cls._optional_command_label(raw_check.get("command_label"))
            if command_label is not None:
                check["command_label"] = command_label
            artifact_id = raw_check.get("artifact_id")
            if artifact_id is not None:
                check["artifact_id"] = cls._normalize_id(artifact_id, "check.artifact_id")
            summary = cls._optional_text(raw_check.get("summary"), "check.summary", max_length=1024)
            if summary is not None:
                check["summary"] = summary
            metadata = cls._sanitize_metadata(raw_check.get("metadata"), "check.metadata")
            if metadata:
                check["metadata"] = metadata
            checks.append(check)
        return checks

    @classmethod
    def _normalize_artifact_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            raise AgentTaskEvidenceError("artifact_ids must be a list of strings.")
        return [cls._normalize_id(item, "artifact_ids") for item in value if str(item or "").strip()]

    @staticmethod
    def _require_task_artifacts(session: Any, task_id: str, artifact_ids: list[str]) -> None:
        for artifact_id in artifact_ids:
            artifact = AgentTaskEvidenceService._get_task_artifact(session, task_id, artifact_id)
            if artifact is None:
                raise AgentTaskEvidenceError(f"agent task artifact not found: {artifact_id}")

    @classmethod
    def _normalize_relative_path(cls, value: Any) -> str:
        text = cls._required_text(value, "relative_path", max_length=512)
        path = PurePosixPath(text)
        if path.is_absolute():
            raise AgentTaskEvidenceError("relative_path must be relative.")
        raw_parts = text.split("/")
        if any(part in {"", ".", ".."} for part in raw_parts):
            raise AgentTaskEvidenceError("relative_path must not contain empty, dot, or dot-dot parts.")
        return text

    @classmethod
    def _normalize_id(cls, value: Any, field_name: str) -> str:
        text = cls._required_text(value, field_name, max_length=64)
        if text in {".", ".."} or SAFE_ID_PATTERN.fullmatch(text) is None:
            raise AgentTaskEvidenceError(
                f"{field_name} may only contain letters, numbers, dot, underscore, colon, or hyphen."
            )
        return text

    @classmethod
    def _normalize_choice(cls, value: Any, field_name: str, choices: tuple[str, ...]) -> str:
        normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if normalized not in choices:
            raise AgentTaskEvidenceError(f"{field_name} must be one of: {', '.join(choices)}.")
        return normalized

    @classmethod
    def _normalize_optional_sha256(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = cls._required_text(value, "sha256", max_length=64, reject_sensitive=False)
        if SHA256_PATTERN.fullmatch(text) is None:
            raise AgentTaskEvidenceError("sha256 must be a 64-character hexadecimal digest.")
        return text.lower()

    @staticmethod
    def _normalize_optional_non_negative_int(value: Any, field_name: str) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise AgentTaskEvidenceError(f"{field_name} must be a non-negative integer.")
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise AgentTaskEvidenceError(f"{field_name} must be a non-negative integer.") from exc
        if normalized < 0:
            raise AgentTaskEvidenceError(f"{field_name} must be a non-negative integer.")
        return normalized

    @classmethod
    def _sanitize_metadata(cls, value: Any, field_name: str) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise AgentTaskEvidenceError(f"{field_name} must be an object.")
        return cls._sanitize_metadata_dict(value, field_name)

    @classmethod
    def _sanitize_metadata_dict(cls, value: dict[str, Any], field_name: str) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = cls._required_text(raw_key, f"{field_name}.key", max_length=128)
            cls._reject_forbidden_metadata_field(key, field_name)
            sanitized[key] = cls._sanitize_metadata_value(raw_value, f"{field_name}.{key}")
        return sanitized

    @classmethod
    def _sanitize_metadata_value(cls, value: Any, field_name: str) -> Any:
        if isinstance(value, str):
            return cls._required_text(value, field_name, max_length=2048)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            if len(value) > 64:
                raise AgentTaskEvidenceError(f"{field_name} must contain 64 items or fewer.")
            return [cls._sanitize_metadata_value(item, field_name) for item in value]
        if isinstance(value, dict):
            return cls._sanitize_metadata_dict(value, field_name)
        raise AgentTaskEvidenceError(f"{field_name} must be a scalar, object, or list.")

    @classmethod
    def _reject_forbidden_metadata_deep(
        cls,
        value: Any,
        location: str,
        *,
        command_label_allowed: bool = False,
    ) -> None:
        if isinstance(value, dict):
            for raw_key, raw_value in value.items():
                key = str(raw_key or "").strip()
                if key == COMMAND_LABEL_FIELD_NAME:
                    if not command_label_allowed:
                        raise AgentTaskEvidenceError(
                            f"command_label is accepted only as a direct verification check label, not in {location}."
                        )
                    cls._optional_command_label(raw_value)
                    continue
                cls._reject_forbidden_metadata_field(key, location)
                cls._reject_forbidden_metadata_deep(raw_value, f"{location}.{key}")
        elif isinstance(value, list):
            for item in value:
                cls._reject_forbidden_metadata_deep(item, location)
        elif isinstance(value, str):
            cls._reject_sensitive_text(value, location)

    @staticmethod
    def _reject_forbidden_metadata_field(field: str, location: str) -> None:
        normalized = field.strip().lower().replace("-", "_").replace(" ", "_")
        if AgentTaskQueueService._is_raw_execution_field(field):
            raise AgentTaskEvidenceError(f"raw execution field is not accepted in {location}: {field}")
        if _contains_sensitive_marker(field):
            raise AgentTaskEvidenceError(f"sensitive field is not accepted in {location}: {field}")

    @classmethod
    def _required_text(
        cls,
        value: Any,
        field_name: str,
        *,
        max_length: int | None = None,
        reject_sensitive: bool = True,
    ) -> str:
        text = str(value or "").strip()
        if not text:
            raise AgentTaskEvidenceError(f"{field_name} is required.")
        if max_length is not None and len(text) > max_length:
            raise AgentTaskEvidenceError(f"{field_name} must be {max_length} characters or fewer.")
        if reject_sensitive:
            cls._reject_sensitive_text(text, field_name)
        return text

    @classmethod
    def _reject_sensitive_text(cls, text: str, field_name: str) -> None:
        if _contains_sensitive_marker(text):
            raise AgentTaskEvidenceError(f"{field_name} contains sensitive material.")
        cls._reject_raw_command_text(text, field_name)
        for pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(text):
                raise AgentTaskEvidenceError(f"{field_name} contains sensitive material.")
        for candidate in BARE_SECRET_LIKE_VALUE_PATTERN.findall(text):
            has_alpha = any(char.isalpha() for char in candidate)
            has_digit = any(char.isdigit() for char in candidate)
            if has_alpha and has_digit:
                raise AgentTaskEvidenceError(f"{field_name} contains sensitive material.")
        for candidate in SECRET_LIKE_VALUE_PATTERN.findall(text):
            has_alpha = any(char.isalpha() for char in candidate)
            has_digit = any(char.isdigit() for char in candidate)
            has_symbol = any(not char.isalnum() for char in candidate)
            if has_alpha and has_digit and has_symbol:
                raise AgentTaskEvidenceError(f"{field_name} contains sensitive material.")

    @staticmethod
    def _reject_raw_command_text(text: str, field_name: str) -> None:
        for pattern in RAW_COMMAND_VALUE_PATTERNS:
            if pattern.search(text):
                raise AgentTaskEvidenceError(f"{field_name} contains raw execution material.")

    @classmethod
    def _optional_command_label(cls, value: Any) -> str | None:
        label = cls._optional_text(value, "check.command_label", max_length=255)
        if label is None:
            return None
        if COMMAND_LABEL_FORBIDDEN_CHARS.search(label):
            raise AgentTaskEvidenceError("check.command_label contains raw execution material.")
        normalized_tokens = [
            token.strip("()[]{}:,").lower()
            for token in label.split()
            if token.strip("()[]{}:, ")
        ]
        if not normalized_tokens:
            return None
        if normalized_tokens[0] in COMMAND_LABEL_EXECUTABLE_PREFIXES:
            raise AgentTaskEvidenceError("check.command_label contains raw execution material.")
        for token in normalized_tokens:
            if token.startswith("-") or token.endswith((".py", ".sh")):
                raise AgentTaskEvidenceError("check.command_label contains raw execution material.")
        return label

    @classmethod
    def _optional_text(
        cls,
        value: Any,
        field_name: str,
        *,
        max_length: int | None = None,
        reject_sensitive: bool = True,
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
    def _serialize_event(cls, record: AgentTaskEvent) -> dict[str, Any]:
        return {
            "schema_version": TASK_EVENT_SCHEMA_VERSION,
            "task_id": record.task_id,
            "sequence": record.sequence,
            "event_type": record.event_type,
            "severity": record.severity,
            "source": record.source,
            "message": record.message,
            "metadata": dict(record.metadata_json or {}),
            "created_at": record.created_at,
        }

    @classmethod
    def _serialize_artifact(cls, record: AgentTaskArtifact) -> dict[str, Any]:
        return {
            "schema_version": TASK_ARTIFACT_SCHEMA_VERSION,
            "artifact_id": record.artifact_id,
            "task_id": record.task_id,
            "artifact_type": record.artifact_type,
            "relative_path": record.relative_path,
            "path": record.path,
            "display_name": record.display_name,
            "media_type": record.media_type,
            "size_bytes": record.size_bytes,
            "sha256": record.sha256,
            "metadata": dict(record.metadata_json or {}),
            "retention_policy": dict(EVIDENCE_RETENTION_POLICY),
            "created_at": record.created_at,
        }

    @classmethod
    def _serialize_report(cls, record: AgentTaskVerificationReport) -> dict[str, Any]:
        artifact_ids = list(record.artifact_ids or [])
        status = record.status
        return {
            "schema_version": VERIFICATION_REPORT_SCHEMA_VERSION,
            "report_id": record.report_id,
            "task_id": record.task_id,
            "status": status,
            "summary": record.summary,
            "checks": list(record.checks_json or []),
            "artifact_ids": artifact_ids,
            "metadata": dict(record.metadata_json or {}),
            "review_handoff": {
                "ready_for_hermes_review": status in SUPPORTED_REPORT_STATUSES,
                "contains_raw_logs": False,
                "artifact_count": len(artifact_ids),
                "secrets_allowed": False,
                "retention_scope": EVIDENCE_RETENTION_POLICY["scope"],
            },
            "created_at": record.created_at,
        }

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
