from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import Settings, _load_dotenv_file


def make_settings(
    tmp_path,
    *,
    database_url: str | None = None,
    volume_root_host: Path | None = None,
    volume_root_container: Path | None = None,
) -> Settings:
    return Settings(
        runtime_dir=tmp_path / "runtime",
        database_url=database_url or f"sqlite:///{tmp_path / 'heimdall.db'}",
        public_base_url="http://127.0.0.1:8000",
        preview_host="127.0.0.1",
        preview_port_start=18000,
        preview_port_end=18010,
        github_api_token=None,
        github_webhook_secret=None,
        gitlab_base_url=None,
        gitlab_api_token=None,
        gitlab_webhook_secret=None,
        volume_root_host=volume_root_host,
        volume_root_container=volume_root_container,
    )


def test_dotenv_file_loads_provider_credentials(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "GITHUB_API_TOKEN=github-local-token",
                "GITHUB_WEBHOOK_SECRET='github-local-secret'",
                'GITLAB_BASE_URL="https://gitlab.example.test"',
                "GITLAB_API_TOKEN=gitlab-local-token",
                "GITLAB_SYSTEM_HOOK_SECRET=gitlab-local-secret",
            ]
        ),
        encoding="utf-8",
    )

    for key in (
        "GITHUB_API_TOKEN",
        "GITHUB_WEBHOOK_SECRET",
        "GITLAB_BASE_URL",
        "GITLAB_API_TOKEN",
        "GITLAB_SYSTEM_HOOK_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)

    _load_dotenv_file(env_path)

    assert os.environ["GITHUB_API_TOKEN"] == "github-local-token"
    assert os.environ["GITHUB_WEBHOOK_SECRET"] == "github-local-secret"
    assert os.environ["GITLAB_BASE_URL"] == "https://gitlab.example.test"
    assert os.environ["GITLAB_API_TOKEN"] == "gitlab-local-token"
    assert os.environ["GITLAB_SYSTEM_HOOK_SECRET"] == "gitlab-local-secret"


def test_dotenv_file_does_not_override_process_environment(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("GITHUB_API_TOKEN=file-token", encoding="utf-8")
    monkeypatch.setenv("GITHUB_API_TOKEN", "process-token")

    _load_dotenv_file(env_path)

    assert os.environ["GITHUB_API_TOKEN"] == "process-token"


def test_settings_exposes_provider_credentials(tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{tmp_path / 'heimdall.db'}")
    monkeypatch.setenv("HEIMDALL_GITHUB_API_TOKEN", "github-token")
    monkeypatch.setenv("HEIMDALL_GITHUB_WEBHOOK_SECRET", "github-secret")
    monkeypatch.setenv("HEIMDALL_GITLAB_BASE_URL", "https://gitlab.example.test")
    monkeypatch.setenv("HEIMDALL_GITLAB_API_TOKEN", "gitlab-token")
    monkeypatch.setenv("HEIMDALL_GITLAB_WEBHOOK_SECRET", "gitlab-secret")

    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()

    assert settings.github_api_token == "github-token"
    assert settings.github_webhook_secret == "github-secret"
    assert settings.gitlab_base_url == "https://gitlab.example.test"
    assert settings.gitlab_api_token == "gitlab-token"
    assert settings.gitlab_webhook_secret == "gitlab-secret"


def test_settings_exposes_optional_preview_health_host(tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{tmp_path / 'heimdall.db'}")
    monkeypatch.setenv("HEIMDALL_PREVIEW_HOST", "127.0.0.1")
    monkeypatch.setenv("HEIMDALL_PREVIEW_HEALTH_HOST", "host.docker.internal")

    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()

    assert settings.preview_host == "127.0.0.1"
    assert settings.preview_health_host == "host.docker.internal"


@pytest.mark.parametrize(
    ("database_url", "backend"),
    [
        ("sqlite:////tmp/heimdall.db", "sqlite"),
        ("postgresql://heimdall:secret@postgres:5432/heimdall", "postgresql"),
        ("postgres://heimdall:secret@postgres:5432/heimdall", "postgresql"),
    ],
)
def test_database_url_supported_backends(tmp_path, database_url, backend):
    settings = make_settings(tmp_path, database_url=database_url)

    assert settings.database_backend == backend


def test_postgres_database_url_does_not_expose_database_path(tmp_path):
    settings = make_settings(
        tmp_path,
        database_url="postgresql://heimdall:secret@postgres:5432/heimdall",
    )

    assert settings.is_postgres_database is True
    with pytest.raises(ValueError, match="sqlite"):
        settings.database_path


def test_unsupported_database_url_is_rejected(tmp_path):
    settings = make_settings(tmp_path, database_url="mysql://heimdall:secret@db/heimdall")

    with pytest.raises(ValueError, match="HEIMDALL_DATABASE_URL"):
        settings.ensure_runtime_dirs()


def test_ensure_runtime_dirs_creates_sqlite_database_parent(tmp_path):
    database_path = tmp_path / "state" / "nested" / "heimdall.db"
    settings = make_settings(tmp_path, database_url=f"sqlite:///{database_path}")

    settings.ensure_runtime_dirs()

    assert database_path.parent.is_dir()


def test_ensure_runtime_dirs_accepts_postgres_without_database_path(tmp_path):
    settings = make_settings(
        tmp_path,
        database_url="postgresql://heimdall:secret@postgres:5432/heimdall",
    )

    settings.ensure_runtime_dirs()

    assert settings.runtime_dir.is_dir()
    assert settings.logs_dir.is_dir()
    assert settings.workspaces_dir.is_dir()
    assert settings.state_dir.is_dir()


def test_get_settings_accepts_postgres_url_without_database_path(tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", "postgresql://heimdall:secret@postgres:5432/heimdall")

    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()

    assert settings.is_postgres_database is True
    assert settings.state_dir.is_dir()


def test_project_database_settings_default_without_startup_admin_url(tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{tmp_path / 'heimdall.db'}")
    monkeypatch.setenv("HEIMDALL_PROJECT_DATABASE_ADMIN_URL", "")

    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()

    assert settings.project_database_admin_url is None
    assert settings.project_database_app_host == "project-postgres"
    assert settings.project_database_app_port == 5432
    assert settings.project_database_network == "heimdall-project-db"
    with pytest.raises(ValueError, match="HEIMDALL_PROJECT_DATABASE_ADMIN_URL"):
        settings.require_project_database_settings()


def test_project_database_settings_require_only_when_used(tmp_path):
    settings = make_settings(tmp_path)

    settings.ensure_runtime_dirs()
    with pytest.raises(ValueError, match="HEIMDALL_PROJECT_DATABASE_ADMIN_URL"):
        settings.require_project_database_settings()


def test_project_database_settings_parse_and_require(tmp_path, monkeypatch):
    from app.config import get_settings

    admin_url = "postgres://admin:secret@project-postgres:5432/postgres"
    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{tmp_path / 'heimdall.db'}")
    monkeypatch.setenv("HEIMDALL_PROJECT_DATABASE_ADMIN_URL", admin_url)
    monkeypatch.setenv("HEIMDALL_PROJECT_DATABASE_APP_HOST", "app-db")
    monkeypatch.setenv("HEIMDALL_PROJECT_DATABASE_APP_PORT", "15432")
    monkeypatch.setenv("HEIMDALL_PROJECT_DATABASE_NETWORK", "app-db-net")

    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()

    assert settings.require_project_database_settings() == (admin_url, "app-db", 15432, "app-db-net")


def test_project_database_settings_reject_reserved_control_network(tmp_path):
    settings = make_settings(
        tmp_path,
        database_url=f"sqlite:///{tmp_path / 'heimdall.db'}",
    )
    settings = Settings(
        **{
            **settings.__dict__,
            "project_database_admin_url": "postgres://admin:secret@project-postgres:5432/postgres",
            "project_database_network": "heimdall-control",
        }
    )

    with pytest.raises(ValueError, match="heimdall-control"):
        settings.require_project_database_settings()


def test_volume_roots_are_optional_when_unset(tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{tmp_path / 'heimdall.db'}")
    monkeypatch.setenv("HEIMDALL_VOLUME_ROOT_HOST", "")
    monkeypatch.setenv("HEIMDALL_VOLUME_ROOT_CONTAINER", "")

    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()

    assert settings.volume_root_host is None
    assert settings.volume_root_container is None


def test_volume_roots_are_parsed_without_startup_validation(tmp_path, monkeypatch):
    from app.config import get_settings

    host_root = tmp_path / "host-root"
    container_root = tmp_path / "container-root"
    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{tmp_path / 'heimdall.db'}")
    monkeypatch.setenv("HEIMDALL_VOLUME_ROOT_HOST", str(host_root))
    monkeypatch.setenv("HEIMDALL_VOLUME_ROOT_CONTAINER", str(container_root))

    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()

    assert settings.volume_root_host == host_root
    assert settings.volume_root_container == container_root


def test_require_volume_roots_rejects_missing_roots(tmp_path):
    settings = make_settings(tmp_path)

    with pytest.raises(ValueError, match="required"):
        settings.require_volume_roots()


def test_require_volume_roots_rejects_one_sided_roots(tmp_path):
    host_root = tmp_path / "host-root"
    host_root.mkdir()
    settings = make_settings(tmp_path, volume_root_host=host_root)

    with pytest.raises(ValueError, match="required"):
        settings.require_volume_roots()


def test_require_volume_roots_rejects_relative_roots(tmp_path):
    container_root = tmp_path / "container-root"
    container_root.mkdir()
    settings = make_settings(
        tmp_path,
        volume_root_host=Path("relative-root"),
        volume_root_container=container_root,
    )

    with pytest.raises(ValueError, match="absolute"):
        settings.require_volume_roots()


def test_require_volume_roots_rejects_nonexistent_roots(tmp_path):
    container_root = tmp_path / "container-root"
    container_root.mkdir()
    settings = make_settings(
        tmp_path,
        volume_root_host=tmp_path / "missing-root",
        volume_root_container=container_root,
    )

    with pytest.raises(ValueError, match="exist"):
        settings.require_volume_roots()


def test_require_volume_roots_rejects_symlink_roots(tmp_path):
    target_root = tmp_path / "target-root"
    target_root.mkdir()
    symlink_root = tmp_path / "symlink-root"
    try:
        symlink_root.symlink_to(target_root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    container_root = tmp_path / "container-root"
    container_root.mkdir()
    settings = make_settings(
        tmp_path,
        volume_root_host=symlink_root,
        volume_root_container=container_root,
    )

    with pytest.raises(ValueError, match="symlink"):
        settings.require_volume_roots()


def test_require_volume_roots_accepts_valid_directories(tmp_path):
    host_root = tmp_path / "host-root"
    container_root = tmp_path / "container-root"
    host_root.mkdir()
    container_root.mkdir()
    settings = make_settings(
        tmp_path,
        volume_root_host=host_root,
        volume_root_container=container_root,
    )

    assert settings.require_volume_roots() == (host_root, container_root)
