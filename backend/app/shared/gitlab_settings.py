"""Minimal GitLab environment settings helper for upcoming integration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass(frozen=True)
class GitLabSettings:
    """Prepared-only GitLab connection settings loaded from environment."""

    base_url: str
    api_token: str
    verify_ssl: bool
    default_namespace_path: str
    system_hook_secret: str
    public_base_url: str

    @property
    def is_configured(self) -> bool:
        """Return whether the GitLab base URL is valid enough for runtime use."""
        return self.validation_error is None

    @property
    def validation_error(self) -> str | None:
        """Validate GitLab base URL shape without exposing sensitive values."""
        if not self.base_url:
            return "GITLAB_BASE_URL is not configured."

        parsed = urlparse(self.base_url)
        if not parsed.scheme or not parsed.netloc:
            return "GITLAB_BASE_URL must include scheme and host."

        if parsed.scheme not in {"http", "https"}:
            return "GITLAB_BASE_URL must use http or https."

        return None

    @property
    def can_sync(self) -> bool:
        """Return whether manual sync has enough configuration to run."""
        return self.is_configured and bool(self.api_token)


def get_gitlab_settings() -> GitLabSettings:
    """Load GitLab settings from environment without forcing runtime use yet."""
    return GitLabSettings(
        base_url=os.getenv("GITLAB_BASE_URL", "").strip().rstrip("/"),
        api_token=os.getenv("GITLAB_API_TOKEN", "").strip(),
        verify_ssl=_read_bool_env("GITLAB_VERIFY_SSL", True),
        default_namespace_path=os.getenv("GITLAB_DEFAULT_NAMESPACE_PATH", "heimdall").strip() or "heimdall",
        system_hook_secret=os.getenv("GITLAB_SYSTEM_HOOK_SECRET", "").strip(),
        public_base_url=os.getenv("PLATFORM_PUBLIC_BASE_URL", "").strip().rstrip("/"),
    )


__all__ = ["GitLabSettings", "get_gitlab_settings"]
