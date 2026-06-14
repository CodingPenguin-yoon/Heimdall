from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SQLITE_DATABASE_PREFIX = "sqlite:///"
POSTGRES_DATABASE_PREFIXES = ("postgresql://", "postgres://")


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
    project_database_admin_url: str | None = None
    project_database_app_host: str = "project-postgres"
    project_database_app_port: int = 5432
    project_database_network: str = "heimdall-project-db"
    volume_root_host: Path | None = None
    volume_root_container: Path | None = None
    preview_health_host: str | None = None

    @property
    def database_backend(self) -> str:
        if self.database_url.startswith(SQLITE_DATABASE_PREFIX):
            return "sqlite"
        if self.database_url.startswith(POSTGRES_DATABASE_PREFIXES):
            return "postgresql"
        raise ValueError("HEIMDALL_DATABASE_URL must use sqlite:///, postgresql://, or postgres://")

    @property
    def is_sqlite_database(self) -> bool:
        return self.database_backend == "sqlite"

    @property
    def is_postgres_database(self) -> bool:
        return self.database_backend == "postgresql"

    @property
    def database_path(self) -> Path:
        if not self.is_sqlite_database:
            raise ValueError("database_path is available only for sqlite:/// database URLs")
        raw_path = self.database_url[len(SQLITE_DATABASE_PREFIX) :]
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

    @property
    def secrets_dir(self) -> Path:
        return self.runtime_dir / "secrets"

    def ensure_runtime_dirs(self) -> None:
        for path in (self.runtime_dir, self.logs_dir, self.workspaces_dir, self.state_dir):
            path.mkdir(parents=True, exist_ok=True)
        if self.is_sqlite_database:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def require_volume_roots(self) -> tuple[Path, Path]:
        if self.volume_root_host is None or self.volume_root_container is None:
            raise ValueError(
                "HEIMDALL_VOLUME_ROOT_HOST and HEIMDALL_VOLUME_ROOT_CONTAINER are required when volumes are configured."
            )

        for env_name, path in (
            ("HEIMDALL_VOLUME_ROOT_HOST", self.volume_root_host),
            ("HEIMDALL_VOLUME_ROOT_CONTAINER", self.volume_root_container),
        ):
            if not path.is_absolute():
                raise ValueError(f"{env_name} must be an absolute path.")
            if path.is_symlink():
                raise ValueError(f"{env_name} must not be a symlink.")
            if not path.exists():
                raise ValueError(f"{env_name} must exist.")
            if not path.is_dir():
                raise ValueError(f"{env_name} must be a directory.")

        return self.volume_root_host, self.volume_root_container

    def require_project_database_settings(self) -> tuple[str, str, int, str]:
        admin_url = (self.project_database_admin_url or "").strip()
        app_host = self.project_database_app_host.strip()
        network = self.project_database_network.strip()
        missing = []
        if not admin_url:
            missing.append("HEIMDALL_PROJECT_DATABASE_ADMIN_URL")
        if not app_host:
            missing.append("HEIMDALL_PROJECT_DATABASE_APP_HOST")
        if not network:
            missing.append("HEIMDALL_PROJECT_DATABASE_NETWORK")
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"{joined} must be configured when managed project databases are enabled.")
        if not admin_url.startswith(POSTGRES_DATABASE_PREFIXES):
            raise ValueError("HEIMDALL_PROJECT_DATABASE_ADMIN_URL must use postgresql:// or postgres://")
        if self.project_database_app_port < 1 or self.project_database_app_port > 65535:
            raise ValueError("HEIMDALL_PROJECT_DATABASE_APP_PORT must be between 1 and 65535.")
        if network == "heimdall-control":
            raise ValueError("HEIMDALL_PROJECT_DATABASE_NETWORK cannot use reserved Docker network 'heimdall-control'.")
        return admin_url, app_host, self.project_database_app_port, network


def _env_path(name: str) -> Path | None:
    value = os.getenv(name)
    return Path(value) if value else None


def _env_optional(name: str) -> str | None:
    value = os.getenv(name)
    return value if value else None


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
        project_database_admin_url=_env_optional("HEIMDALL_PROJECT_DATABASE_ADMIN_URL"),
        project_database_app_host=os.getenv("HEIMDALL_PROJECT_DATABASE_APP_HOST", "project-postgres"),
        project_database_app_port=int(os.getenv("HEIMDALL_PROJECT_DATABASE_APP_PORT", "5432") or "5432"),
        project_database_network=os.getenv("HEIMDALL_PROJECT_DATABASE_NETWORK", "heimdall-project-db"),
        volume_root_host=_env_path("HEIMDALL_VOLUME_ROOT_HOST"),
        volume_root_container=_env_path("HEIMDALL_VOLUME_ROOT_CONTAINER"),
        preview_health_host=_env_optional("HEIMDALL_PREVIEW_HEALTH_HOST"),
    )
    settings.ensure_runtime_dirs()
    return settings
