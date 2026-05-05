"""Worker registry service for Heimdall agent/devops execution."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy import select

from app.shared.platform_db import create_platform_engine, create_session_factory
from app.shared.platform_models import AgentWorker

SUPPORTED_AGENT_TYPES = ("claude", "codex", "opencode")
SUPPORTED_WORKER_STATUSES = ("unknown", "ready", "busy", "offline", "error")
SUPPORTED_AUTH_STATUSES = ("unknown", "authenticated", "expired", "needs_login", "not_applicable")
STALE_WORKER_THRESHOLD_SECONDS = 300
GJALLAR_WORKER_PROVISIONING_SCHEMA_VERSION = "gjallar.worker_provisioning_result.v1"
GJALLAR_OWNER_PROJECT = "Gjallar"
GJALLAR_BOOTSTRAP_STATUS_TO_WORKER_STATUS = {
    "pending": "unknown",
    "completed": "unknown",
    "unreachable": "offline",
    "failed": "error",
}
WORKER_ID_PATTERN = re.compile(r'^[A-Za-z0-9_.:-]+')
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


def _normalized_sensitive_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _contains_sensitive_marker(value: str) -> bool:
    normalized = _normalized_sensitive_text(value)
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


class AgentWorkerRegistryError(RuntimeError):
    """Raised when worker registry payloads are invalid."""

class AgentWorkerRegistryService:
    """Persist and expose Codex/Claude/OpenCode worker registry entries."""

    def __init__(self, database_url: str | None = None) -> None:
        self._engine = create_platform_engine(database_url)
        self._session_factory = create_session_factory(self._engine)

    @classmethod
    def build_registration_payload_from_gjallar_result(cls, result: dict[str, Any]) -> dict[str, Any]:
        """Translate a Gjallar worker provisioning result into a Heimdall register payload.

        This helper is the in-code contract boundary for Gjallar-owned VM/bootstrap
        output. It accepts only non-sensitive routing and health metadata that
        Heimdall can persist in the worker registry.
        """
        if not isinstance(result, dict):
            raise AgentWorkerRegistryError("Gjallar provisioning result must be an object.")
        for field_name in result:
            if _contains_sensitive_marker(str(field_name)):
                raise AgentWorkerRegistryError(
                    f"sensitive non-contract field is not accepted: {field_name}"
                )

        schema_version = cls._required_text(
            result.get("schema_version"),
            "schema_version",
            max_length=128,
            reject_sensitive=True,
        )
        if schema_version != GJALLAR_WORKER_PROVISIONING_SCHEMA_VERSION:
            raise AgentWorkerRegistryError(
                f"schema_version must be {GJALLAR_WORKER_PROVISIONING_SCHEMA_VERSION}."
            )

        owner_project = cls._required_text(
            result.get("owner_project"),
            "owner_project",
            max_length=64,
            reject_sensitive=True,
        )
        if owner_project != GJALLAR_OWNER_PROJECT:
            raise AgentWorkerRegistryError("owner_project must be Gjallar.")

        bootstrap_status = cls._normalize_bootstrap_status(result.get("bootstrap_status"))
        if "agent_types" not in result:
            raise AgentWorkerRegistryError("agent_types is required for Gjallar provisioning results.")
        agent_types = cls._normalize_agent_types(result.get("agent_types"))
        checks = cls._normalize_gjallar_checks(result.get("checks"))
        labels = cls._sanitize_mapping(result.get("labels"))
        labels["provisioning_owner"] = GJALLAR_OWNER_PROJECT
        provisioning_id = cls._optional_text(
            result.get("provisioning_id"),
            "provisioning_id",
            max_length=128,
            reject_sensitive=True,
        )
        if provisioning_id:
            labels["provisioning_id"] = provisioning_id
        labels["bootstrap_status"] = bootstrap_status

        payload: dict[str, Any] = {
            "worker_id": cls._normalize_worker_id(result.get("worker_id")),
            "display_name": cls._optional_text(
                result.get("display_name"),
                "display_name",
                max_length=255,
                reject_sensitive=True,
            ),
            "hostname": cls._required_text(
                result.get("hostname"),
                "hostname",
                max_length=255,
                reject_sensitive=True,
            ),
            "host_ip": cls._optional_text(
                result.get("host_ip"),
                "host_ip",
                max_length=64,
                reject_sensitive=True,
            ),
            "ssh_user": cls._optional_text(
                result.get("ssh_user"),
                "ssh_user",
                max_length=255,
                reject_sensitive=True,
            ),
            "agent_types": agent_types,
            "agent_auth_status": cls._normalize_auth_status(
                result.get("agent_auth_status"),
                agent_types,
            ),
            "status": cls._worker_status_from_gjallar_bootstrap(
                bootstrap_status,
                checks,
                agent_types,
            ),
            "labels": labels,
        }
        observed_at = cls._normalize_optional_timestamp(result.get("observed_at"), "observed_at")
        if observed_at is not None:
            payload["last_checked_at"] = observed_at
        return payload

    def register_worker(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._reject_sensitive_payload_fields(payload)
        worker_id = self._normalize_worker_id(payload.get('worker_id'))
        hostname = self._required_text(
            payload.get("hostname"),
            "hostname",
            max_length=255,
            reject_sensitive=True,
        )
        agent_types = self._normalize_agent_types(payload.get("agent_types"))
        status = self._normalize_worker_status(payload.get("status", "unknown"))
        auth_status = self._normalize_auth_status(payload.get("agent_auth_status"), agent_types)
        labels = self._sanitize_mapping(payload.get("labels"))
        now = self._now_iso()

        with self._session_factory.begin() as session:
            record = session.get(AgentWorker, worker_id)
            if record is None:
                record = AgentWorker(worker_id=worker_id, created_at=now)
                session.add(record)

            record.display_name = self._optional_text(
                payload.get("display_name"),
                "display_name",
                max_length=255,
                reject_sensitive=True,
            )
            record.hostname = hostname
            record.host_ip = self._optional_text(
                payload.get("host_ip"),
                "host_ip",
                max_length=64,
                reject_sensitive=True,
            )
            record.ssh_user = self._optional_text(
                payload.get("ssh_user"),
                "ssh_user",
                max_length=255,
                reject_sensitive=True,
            )
            record.agent_types = agent_types
            record.agent_auth_status = auth_status
            record.status = status
            record.labels_json = labels
            record.current_task_id = self._optional_text(
                payload.get("current_task_id"),
                "current_task_id",
                max_length=64,
                reject_sensitive=True,
            )
            record.last_checked_at = self._normalize_optional_timestamp(
                payload.get("last_checked_at"),
                "last_checked_at",
            ) or now
            record.updated_at = now
            session.flush()
            return self._serialize(record)

    def list_workers(self, *, agent_type: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        normalized_agent_type = None
        if agent_type is not None:
            normalized_agent_type = self._normalize_agent_type(agent_type)
        normalized_status = None
        if status is not None:
            normalized_status = self._normalize_worker_status(status)

        with self._session_factory() as session:
            rows = session.execute(
                select(AgentWorker).order_by(AgentWorker.worker_id.asc())
            ).scalars().all()

        workers = [self._serialize(row) for row in rows]
        if normalized_agent_type is not None:
            workers = [worker for worker in workers if normalized_agent_type in worker["agent_types"]]
        if normalized_status is not None:
            workers = [worker for worker in workers if worker["status"] == normalized_status]
        return workers

    def get_worker(self, worker_id: str) -> dict[str, Any] | None:
        normalized_worker_id = self._normalize_worker_id(worker_id)
        with self._session_factory() as session:
            record = session.get(AgentWorker, normalized_worker_id)
            if record is None:
                return None
            return self._serialize(record)

    def update_worker_status(self, worker_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._reject_sensitive_payload_fields(payload)
        normalized_worker_id = self._normalize_worker_id(worker_id)
        now = self._now_iso()
        with self._session_factory.begin() as session:
            record = session.get(AgentWorker, normalized_worker_id)
            if record is None:
                raise AgentWorkerRegistryError(f"worker not found: {normalized_worker_id}")

            if "status" in payload:
                record.status = self._normalize_worker_status(payload.get("status"))
            if "agent_auth_status" in payload:
                record.agent_auth_status = self._normalize_auth_status(
                    payload.get("agent_auth_status"),
                    list(record.agent_types or []),
                )
            if "current_task_id" in payload:
                record.current_task_id = self._optional_text(
                    payload.get("current_task_id"),
                    "current_task_id",
                    max_length=64,
                    reject_sensitive=True,
                )
            record.last_checked_at = self._normalize_optional_timestamp(
                payload.get("last_checked_at"),
                "last_checked_at",
            ) or now
            record.updated_at = now
            session.flush()
            return self._serialize(record)

    def record_worker_heartbeat(self, worker_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized_worker_id = self._normalize_worker_id(worker_id)
        payload = payload or {}
        self._reject_sensitive_payload_fields(payload)
        now = self._now_iso()
        observed_at = None
        if "observed_at" in payload:
            observed_at = self._normalize_optional_timestamp(
                payload.get("observed_at"),
                "observed_at",
            )
        heartbeat_at = observed_at or now

        with self._session_factory.begin() as session:
            record = session.get(AgentWorker, normalized_worker_id)
            if record is None:
                raise AgentWorkerRegistryError(f"worker not found: {normalized_worker_id}")

            if "status" in payload:
                record.status = self._normalize_worker_status(payload.get("status"))
            if "agent_auth_status" in payload:
                record.agent_auth_status = self._normalize_auth_status(
                    payload.get("agent_auth_status"),
                    list(record.agent_types or []),
                )
            if "current_task_id" in payload:
                record.current_task_id = self._optional_text(
                    payload.get("current_task_id"),
                    "current_task_id",
                    max_length=64,
                    reject_sensitive=True,
                )

            record.last_checked_at = heartbeat_at
            record.updated_at = now
            session.flush()
            return self._serialize(record)

    @classmethod
    def _normalize_worker_id(cls, value: Any) -> str:
        worker_id = cls._required_text(
            value,
            'worker_id',
            max_length=64,
            reject_sensitive=True,
        )
        if WORKER_ID_PATTERN.fullmatch(worker_id) is None:
            raise AgentWorkerRegistryError(
                'worker_id may only contain letters, numbers, dot, underscore, colon, or hyphen.'
            )
        return worker_id

    @classmethod
    def _normalize_agent_types(cls, raw_agent_types: Any) -> list[str]:
        if raw_agent_types is None:
            raw_agent_types = ["codex"]
        if isinstance(raw_agent_types, str):
            raw_agent_types = [raw_agent_types]
        if not isinstance(raw_agent_types, list):
            raise AgentWorkerRegistryError("agent_types must be a list of strings.")

        normalized = sorted(
            {
                cls._normalize_agent_type(agent_type)
                for agent_type in raw_agent_types
                if str(agent_type or "").strip()
            }
        )
        if not normalized:
            raise AgentWorkerRegistryError("agent_types must include at least one supported agent type.")
        return normalized

    @staticmethod
    def _normalize_agent_type(agent_type: Any) -> str:
        normalized = str(agent_type or "").strip().lower().replace(" ", "_").replace("-", "_")
        if normalized not in SUPPORTED_AGENT_TYPES:
            raise AgentWorkerRegistryError(f"unsupported agent type: {agent_type}")
        return normalized

    @staticmethod
    def _normalize_worker_status(status: Any) -> str:
        normalized = str(status or "unknown").strip().lower().replace(" ", "_").replace("-", "_")
        if normalized not in SUPPORTED_WORKER_STATUSES:
            raise AgentWorkerRegistryError(f"unsupported worker status: {status}")
        return normalized

    @staticmethod
    def _normalize_auth_status(raw_auth_status: Any, agent_types: list[str]) -> dict[str, str]:
        if raw_auth_status is None:
            raw_auth_status = {}
        if not isinstance(raw_auth_status, dict):
            raise AgentWorkerRegistryError("agent_auth_status must be an object keyed by agent type.")

        normalized: dict[str, str] = {}
        for agent_type in agent_types:
            status = str(raw_auth_status.get(agent_type, "unknown") or "unknown").strip().lower()
            status = status.replace(" ", "_").replace("-", "_")
            if status not in SUPPORTED_AUTH_STATUSES:
                raise AgentWorkerRegistryError(f"unsupported auth status for {agent_type}: {status}")
            normalized[agent_type] = status
        return normalized

    @staticmethod
    def _reject_sensitive_payload_fields(payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        for field_name in payload:
            if _contains_sensitive_marker(str(field_name)):
                raise AgentWorkerRegistryError(
                    f"sensitive top-level field is not accepted: {field_name}"
                )

    @staticmethod
    def _normalize_bootstrap_status(raw_status: Any) -> str:
        status = str(raw_status or "").strip().lower().replace(" ", "_").replace("-", "_")
        if status not in GJALLAR_BOOTSTRAP_STATUS_TO_WORKER_STATUS:
            raise AgentWorkerRegistryError(
                "bootstrap_status must be one of completed, pending, failed, or unreachable."
            )
        return status

    @staticmethod
    def _normalize_gjallar_checks(raw_checks: Any) -> dict[str, bool]:
        if raw_checks is None:
            return {}
        if not isinstance(raw_checks, dict):
            raise AgentWorkerRegistryError("checks must be an object of non-sensitive booleans.")
        checks: dict[str, bool] = {}
        for raw_key, value in raw_checks.items():
            key = str(raw_key or "").strip()
            if not key:
                continue
            if _contains_sensitive_marker(key):
                raise AgentWorkerRegistryError(f"checks.{key} contains sensitive material.")
            if not isinstance(value, bool):
                raise AgentWorkerRegistryError(f"checks.{key} must be a boolean.")
            checks[key] = value
        return checks

    @staticmethod
    def _worker_status_from_gjallar_bootstrap(
        bootstrap_status: str,
        checks: dict[str, bool],
        agent_types: list[str],
    ) -> str:
        if bootstrap_status != "completed":
            return GJALLAR_BOOTSTRAP_STATUS_TO_WORKER_STATUS[bootstrap_status]
        required_ready_checks = [
            checks.get("ssh_reachable"),
            checks.get("workspace_ready"),
            *(checks.get(f"{agent_type}_cli_available") for agent_type in agent_types),
        ]
        if all(value is True for value in required_ready_checks):
            return "ready"
        return "unknown"

    @staticmethod
    def _sanitize_mapping(raw_mapping: Any) -> dict[str, Any]:
        if raw_mapping is None:
            return {}
        if not isinstance(raw_mapping, dict):
            raise AgentWorkerRegistryError("labels must be an object.")

        sanitized: dict[str, Any] = {}
        for raw_key, value in raw_mapping.items():
            key = str(raw_key or "").strip()
            if not key:
                continue
            if len(key) > 128:
                raise AgentWorkerRegistryError("label keys must be 128 characters or fewer.")
            normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
            if any(part in normalized_key for part in SENSITIVE_KEY_PARTS):
                continue
            if isinstance(value, str):
                if len(value) > 512:
                    raise AgentWorkerRegistryError("label string values must be 512 characters or fewer.")
                AgentWorkerRegistryService._reject_sensitive_text(value, f"labels.{key}")
                sanitized[key] = value
            elif isinstance(value, (int, float, bool)) or value is None:
                sanitized[key] = value
        return sanitized

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
            raise AgentWorkerRegistryError(f"{field_name} is required.")
        if max_length is not None and len(text) > max_length:
            raise AgentWorkerRegistryError(f"{field_name} must be {max_length} characters or fewer.")
        if reject_sensitive:
            AgentWorkerRegistryService._reject_sensitive_text(text, field_name)
        return text

    @staticmethod
    def _optional_text(
        value: Any,
        field_name: str = "value",
        *,
        max_length: int | None = None,
        reject_sensitive: bool = False,
    ) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        if max_length is not None and len(text) > max_length:
            raise AgentWorkerRegistryError(f"{field_name} must be {max_length} characters or fewer.")
        if reject_sensitive:
            AgentWorkerRegistryService._reject_sensitive_text(text, field_name)
        return text

    @staticmethod
    def _reject_sensitive_text(value: str, field_name: str) -> None:
        if _contains_sensitive_marker(value):
            raise AgentWorkerRegistryError(f"{field_name} contains sensitive material.")

    @classmethod
    def _normalize_optional_timestamp(cls, value: Any, field_name: str) -> str | None:
        text = cls._optional_text(
            value,
            field_name,
            max_length=128,
            reject_sensitive=True,
        )
        if text is None:
            return None
        return cls._parse_timestamp_to_utc(text, field_name).isoformat()

    @staticmethod
    def _parse_timestamp_to_utc(value: str, field_name: str) -> datetime:
        try:
            text = value.strip()
            if text.endswith("Z"):
                text = f"{text[:-1]}+00:00"
            parsed = datetime.fromisoformat(text)
        except (AttributeError, TypeError, ValueError) as exc:
            raise AgentWorkerRegistryError(f"{field_name} must be an ISO timestamp.") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @classmethod
    def is_worker_stale(
        cls,
        last_checked_at: Any,
        *,
        threshold_seconds: int = STALE_WORKER_THRESHOLD_SECONDS,
    ) -> bool:
        try:
            checked_at = cls._parse_timestamp_to_utc(str(last_checked_at or ""), "last_checked_at")
        except AgentWorkerRegistryError:
            return True
        return (datetime.now(timezone.utc) - checked_at).total_seconds() > threshold_seconds

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _serialize(cls, record: AgentWorker) -> dict[str, Any]:
        return {
            "worker_id": record.worker_id,
            "display_name": record.display_name,
            "hostname": record.hostname,
            "host_ip": record.host_ip,
            "ssh_user": record.ssh_user,
            "agent_types": list(record.agent_types or []),
            "agent_auth_status": dict(record.agent_auth_status or {}),
            "status": record.status,
            "labels": dict(record.labels_json or {}),
            "current_task_id": record.current_task_id,
            "last_checked_at": record.last_checked_at,
            "is_stale": cls.is_worker_stale(record.last_checked_at),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
