from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _repo_root() -> Path:
    configured = os.getenv("HEIMDALL_REPO_ROOT")
    if configured:
        return Path(configured).resolve()

    path = Path(__file__).resolve()
    if len(path.parents) > 4:
        return path.parents[4]
    return Path.cwd().resolve()


def _clean_dotenv_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def _load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not _ENV_KEY_RE.match(key):
            continue
        os.environ.setdefault(key, _clean_dotenv_value(raw_value))


def _load_local_env() -> None:
    _load_dotenv_file(_repo_root() / ".env")


def _env_first(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


@dataclass(frozen=True)
class Settings:
    runtime_dir: Path
    database_url: str
    public_base_url: str
    preview_host: str
    preview_port_start: int
    preview_port_end: int
    github_api_token: str | None
    github_webhook_secret: str | None
    gitlab_base_url: str | None
    gitlab_api_token: str | None
    gitlab_webhook_secret: str | None

    @property
    def database_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("HEIMDALL_DATABASE_URL must use sqlite:///")
        raw_path = self.database_url[len(prefix) :]
        if raw_path.startswith("/"):
            return Path(raw_path)
        return (Path.cwd() / raw_path).resolve()

    @property
    def logs_dir(self) -> Path:
        return self.runtime_dir / "logs" / "deployments"

    @property
    def workspaces_dir(self) -> Path:
        return self.runtime_dir / "workspaces"

    @property
    def state_dir(self) -> Path:
        return self.runtime_dir / "state"

    def ensure_runtime_dirs(self) -> None:
        for path in (self.runtime_dir, self.logs_dir, self.workspaces_dir, self.state_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    _load_local_env()
    runtime_dir = Path(os.getenv("HEIMDALL_RUNTIME_DIR", str(_repo_root() / "product-runtime"))).resolve()
    database_url = os.getenv(
        "HEIMDALL_DATABASE_URL",
        f"sqlite:///{(runtime_dir / 'state' / 'heimdall.db').as_posix()}",
    )
    preview_port_start = int(os.getenv("HEIMDALL_PREVIEW_PORT_START", "18000"))
    preview_port_end = int(os.getenv("HEIMDALL_PREVIEW_PORT_END", "18999"))
    if preview_port_start > preview_port_end:
        raise ValueError("HEIMDALL_PREVIEW_PORT_START must be <= HEIMDALL_PREVIEW_PORT_END")
    settings = Settings(
        runtime_dir=runtime_dir,
        database_url=database_url,
        public_base_url=os.getenv("HEIMDALL_PUBLIC_BASE_URL", "http://127.0.0.1:8000"),
        preview_host=os.getenv("HEIMDALL_PREVIEW_HOST", "127.0.0.1"),
        preview_port_start=preview_port_start,
        preview_port_end=preview_port_end,
        github_api_token=_env_first("HEIMDALL_GITHUB_API_TOKEN", "GITHUB_API_TOKEN", "GITHUB_TOKEN"),
        github_webhook_secret=_env_first(
            "HEIMDALL_GITHUB_WEBHOOK_SECRET",
            "GITHUB_WEBHOOK_SECRET",
            "GITHUB_SECRET",
        ),
        gitlab_base_url=_env_first("HEIMDALL_GITLAB_BASE_URL", "GITLAB_BASE_URL"),
        gitlab_api_token=_env_first("HEIMDALL_GITLAB_API_TOKEN", "GITLAB_API_TOKEN", "GITLAB_TOKEN"),
        gitlab_webhook_secret=_env_first(
            "HEIMDALL_GITLAB_WEBHOOK_SECRET",
            "GITLAB_WEBHOOK_SECRET",
            "GITLAB_SYSTEM_HOOK_SECRET",
        ),
    )
    settings.ensure_runtime_dirs()
    return settings
