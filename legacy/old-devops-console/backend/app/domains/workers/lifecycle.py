"""Agent task lifecycle policy for Heimdall workers."""

from __future__ import annotations

AGENT_TASK_STATUSES = (
    "queued",
    "running",
    "needs_review",
    "failed",
    "succeeded",
    "cancelled",
)

AGENT_TASK_TERMINAL_STATES = frozenset({"failed", "succeeded", "cancelled"})

_ALLOWED_TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"needs_review", "failed", "succeeded", "cancelled"},
    "needs_review": {"running", "failed", "succeeded", "cancelled"},
    "failed": set(),
    "succeeded": set(),
    "cancelled": set(),
}


def normalize_agent_task_status(value: str | None) -> str:
    """Normalize a human/API supplied agent-task status."""
    normalized = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if normalized not in AGENT_TASK_STATUSES:
        raise ValueError(f"unsupported agent task status: {value}")
    return normalized


def can_transition_agent_task(current_status: str | None, next_status: str | None) -> bool:
    """Return whether an agent task can move between lifecycle states."""
    try:
        current = normalize_agent_task_status(current_status)
        target = normalize_agent_task_status(next_status)
    except ValueError:
        return False
    return target in _ALLOWED_TRANSITIONS[current]
