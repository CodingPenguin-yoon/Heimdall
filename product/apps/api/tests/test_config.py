from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import Settings, _load_dotenv_file


def make_settings(
    tmp_path,
    *,
    volume_root_host: Path | None = None,
    volume_root_container: Path | None = None,
    child_runner_enabled: bool = False,
    child_root_host: Path | None = None,
    child_root_container: Path | None = None,
) -> Settings:
    return Settings(
        runtime_dir=tmp_path / "runtime",
        database_url=f"sqlite:///{tmp_path / 'heimdall.db'}",
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
        child_runner_enabled=child_runner_enabled,
        child_root_host=child_root_host,
        child_root_container=child_root_container,
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


def test_child_runner_settings_are_parsed_without_startup_validation(tmp_path, monkeypatch):
    from app.config import get_settings

    host_root = tmp_path / "child-host"
    container_root = tmp_path / "child-container"
    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{tmp_path / 'heimdall.db'}")
    monkeypatch.setenv("HEIMDALL_CHILD_RUNNER_ENABLED", "true")
    monkeypatch.setenv("HEIMDALL_CHILD_ROOT_HOST", str(host_root))
    monkeypatch.setenv("HEIMDALL_CHILD_ROOT_CONTAINER", str(container_root))

    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()

    assert settings.child_runner_enabled is True
    assert settings.child_root_host == host_root
    assert settings.child_root_container == container_root


def test_child_runner_defaults_to_disabled(tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{tmp_path / 'heimdall.db'}")
    monkeypatch.delenv("HEIMDALL_CHILD_RUNNER_ENABLED", raising=False)
    monkeypatch.delenv("HEIMDALL_CHILD_ROOT_HOST", raising=False)
    monkeypatch.delenv("HEIMDALL_CHILD_ROOT_CONTAINER", raising=False)

    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()

    assert settings.child_runner_enabled is False
    assert settings.child_root_host is None
    assert settings.child_root_container is None


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


def test_require_child_runner_rejects_disabled_gate(tmp_path):
    host_root = tmp_path / "child-host"
    container_root = tmp_path / "child-container"
    host_root.mkdir()
    container_root.mkdir()
    settings = make_settings(tmp_path, child_root_host=host_root, child_root_container=container_root)

    with pytest.raises(ValueError, match="HEIMDALL_CHILD_RUNNER_ENABLED"):
        settings.require_child_runner()


def test_require_child_runner_rejects_missing_roots(tmp_path):
    settings = make_settings(tmp_path, child_runner_enabled=True)

    with pytest.raises(ValueError, match="HEIMDALL_CHILD_ROOT_HOST"):
        settings.require_child_runner()


def test_require_child_runner_rejects_relative_roots(tmp_path):
    container_root = tmp_path / "child-container"
    container_root.mkdir()
    settings = make_settings(
        tmp_path,
        child_runner_enabled=True,
        child_root_host=Path("relative-root"),
        child_root_container=container_root,
    )

    with pytest.raises(ValueError, match="absolute"):
        settings.require_child_runner()


def test_require_child_runner_rejects_nonexistent_roots(tmp_path):
    container_root = tmp_path / "child-container"
    container_root.mkdir()
    settings = make_settings(
        tmp_path,
        child_runner_enabled=True,
        child_root_host=tmp_path / "missing-root",
        child_root_container=container_root,
    )

    with pytest.raises(ValueError, match="exist"):
        settings.require_child_runner()


def test_require_child_runner_rejects_symlink_roots(tmp_path):
    target_root = tmp_path / "target-root"
    target_root.mkdir()
    symlink_root = tmp_path / "symlink-root"
    try:
        symlink_root.symlink_to(target_root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    container_root = tmp_path / "child-container"
    container_root.mkdir()
    settings = make_settings(
        tmp_path,
        child_runner_enabled=True,
        child_root_host=symlink_root,
        child_root_container=container_root,
    )

    with pytest.raises(ValueError, match="symlink"):
        settings.require_child_runner()


def test_require_child_runner_accepts_valid_directories_and_derives_child_paths(tmp_path):
    host_root = tmp_path / "child-host"
    container_root = tmp_path / "child-container"
    host_root.mkdir()
    container_root.mkdir()
    settings = make_settings(
        tmp_path,
        child_runner_enabled=True,
        child_root_host=host_root,
        child_root_container=container_root,
    )

    assert settings.require_child_runner() == (host_root, container_root)
    paths = settings.child_runner_paths("project_abc123")
    assert paths.host_runtime == host_root / "project_abc123" / "runtime"
    assert paths.host_project_volumes == host_root / "project_abc123" / "project-volumes"
    assert paths.container_runtime == container_root / "project_abc123" / "runtime"
    assert paths.container_project_volumes == container_root / "project_abc123" / "project-volumes"
