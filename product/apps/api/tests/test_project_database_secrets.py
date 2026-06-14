from __future__ import annotations

import os
import stat

import pytest

from app.config import Settings
from app.services import project_database_secrets


def make_settings(tmp_path) -> Settings:
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
    )


def test_secret_store_roundtrips_under_runtime_secrets_with_restrictive_mode(tmp_path):
    settings = make_settings(tmp_path)
    ref = "project-databases/project_123/password"
    value = project_database_secrets.generate_password()

    project_database_secrets.write_secret(settings, ref, value)

    path = project_database_secrets.resolve_secret_path(settings, ref)
    assert path.read_text(encoding="utf-8") == value
    assert project_database_secrets.read_secret(settings, ref) == value
    assert settings.secrets_dir in path.parents
    if os.name != "nt":
        assert stat.S_IMODE(settings.secrets_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "ref",
    [
        "",
        "/absolute/password",
        "../password",
        "project-databases/../password",
        "project-databases//password",
        "project-databases\\project\\password",
    ],
)
def test_secret_store_rejects_unsafe_refs(tmp_path, ref):
    settings = make_settings(tmp_path)

    with pytest.raises(project_database_secrets.SecretRefError):
        project_database_secrets.write_secret(settings, ref, "secret")


def test_secret_store_rejects_symlink_escape(tmp_path):
    settings = make_settings(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    settings.secrets_dir.mkdir(parents=True)
    (settings.secrets_dir / "project-databases").symlink_to(outside, target_is_directory=True)

    with pytest.raises(project_database_secrets.SecretRefError):
        project_database_secrets.write_secret(settings, "project-databases/project_123/password", "secret")

    assert not (outside / "project_123").exists()
    assert not (outside / "project_123" / "password").exists()


def test_delete_secret_deletes_only_safe_file_and_is_missing_idempotent(tmp_path):
    settings = make_settings(tmp_path)
    ref = "project-databases/project_123/password"
    value = "generated-password"
    project_database_secrets.write_secret(settings, ref, value)
    path = project_database_secrets.resolve_secret_path(settings, ref)
    parent = path.parent

    project_database_secrets.delete_secret(settings, ref)
    project_database_secrets.delete_secret(settings, ref)

    assert not path.exists()
    assert parent.is_dir()


def test_delete_secret_rejects_symlink_escape_and_leaves_outside_file(tmp_path):
    settings = make_settings(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = outside / "password"
    outside_file.write_text("outside-secret", encoding="utf-8")
    settings.secrets_dir.mkdir(parents=True)
    (settings.secrets_dir / "project-databases").mkdir()
    (settings.secrets_dir / "project-databases" / "password").symlink_to(outside_file)

    with pytest.raises(project_database_secrets.SecretRefError):
        project_database_secrets.delete_secret(settings, "project-databases/password")

    assert outside_file.read_text(encoding="utf-8") == "outside-secret"
