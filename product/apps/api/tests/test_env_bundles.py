from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from app.config import Settings, get_settings
from app.db import connect
from app.services import env_bundles, project_database_secrets

from .test_projects import multi_service_payload, project_payload


def make_settings(tmp_path: Path) -> Settings:
    settings = Settings(
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
    settings.ensure_runtime_dirs()
    return settings


def create_project(client):
    response = client.post("/api/projects", json=project_payload())
    assert response.status_code == 201, response.text
    project = response.json()
    return project, project["services"][0]["id"]


def test_parse_env_bundle_accepts_normal_dotenv_syntax_without_returning_values():
    parsed = env_bundles.parse_env_bundle_content(
        "\n# comment\nexport PLAIN=value\nQUOTED=\"quoted value\"\nSINGLE='quoted=value'\nEMPTY=\n"
    )

    assert parsed.key_names == ["PLAIN", "QUOTED", "SINGLE", "EMPTY"]
    assert len(parsed.checksum_sha256) == 64
    assert "export " not in parsed.normalized_content
    assert "PLAIN=value\n" in parsed.normalized_content


@pytest.mark.parametrize(
    "content",
    [
        "BAD-NAME=value\n",
        "NO_EQUALS\n",
        "DUPLICATE=one\nDUPLICATE=two\n",
        "HAS_NUL=value\x00\n",
        "MULTILINE='one\ntwo'\n",
    ],
)
def test_parse_env_bundle_rejects_invalid_content(content):
    with pytest.raises(env_bundles.EnvBundleError):
        env_bundles.parse_env_bundle_content(content)


def test_parse_env_bundle_rejects_large_files():
    with pytest.raises(env_bundles.EnvBundleError):
        env_bundles.parse_env_bundle_content(f"KEY={'x' * (64 * 1024)}\n")


def test_store_env_bundle_files_under_runtime_secrets_with_restrictive_mode(tmp_path):
    settings = make_settings(tmp_path)

    parsed = env_bundles.store_env_bundle_file(
        settings,
        project_id="project_123",
        service_id="service_456",
        bundle_id="envbundle_abc",
        content="API_TOKEN=super-secret\nMODE=prod\n",
    )

    current_ref = env_bundles.current_env_bundle_ref("project_123", "service_456")
    version_ref = env_bundles.version_env_bundle_ref("project_123", "service_456", "envbundle_abc")
    current_path = env_bundles.resolve_env_bundle_path(settings, current_ref)
    version_path = env_bundles.resolve_env_bundle_path(settings, version_ref)
    assert current_path.read_text(encoding="utf-8") == "API_TOKEN=super-secret\nMODE=prod\n"
    assert version_path.read_text(encoding="utf-8") == current_path.read_text(encoding="utf-8")
    assert settings.secrets_dir in current_path.parents
    assert settings.secrets_dir / "env-bundles" in current_path.parents
    assert parsed.key_names == ["API_TOKEN", "MODE"]
    if os.name != "nt":
        assert stat.S_IMODE((settings.secrets_dir / "env-bundles").stat().st_mode) == 0o700
        assert stat.S_IMODE(current_path.stat().st_mode) == 0o600


def test_store_env_bundle_rejects_path_traversal(tmp_path):
    settings = make_settings(tmp_path)

    with pytest.raises(project_database_secrets.SecretRefError):
        env_bundles.store_env_bundle_file(
            settings,
            project_id="../project",
            service_id="service_456",
            bundle_id="envbundle_abc",
            content="KEY=value\n",
        )


def test_store_env_bundle_rejects_symlink_escape(tmp_path):
    settings = make_settings(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    settings.secrets_dir.mkdir(parents=True)
    (settings.secrets_dir / "env-bundles").symlink_to(outside, target_is_directory=True)

    with pytest.raises(project_database_secrets.SecretRefError):
        env_bundles.store_env_bundle_file(
            settings,
            project_id="project_123",
            service_id="service_456",
            bundle_id="envbundle_abc",
            content="KEY=value\n",
        )

    assert not (outside / "projects").exists()


def test_env_bundle_upload_read_replace_delete_api_stores_only_metadata(client):
    project, service_id = create_project(client)
    secret_value = "super-secret-token"

    upload_response = client.post(
        f"/api/projects/{project['id']}/services/{service_id}/env-bundle",
        json={"content": f"API_TOKEN={secret_value}\nMODE=prod\n"},
    )

    assert upload_response.status_code == 201, upload_response.text
    body = upload_response.json()
    assert body["configured"] is True
    assert body["project_id"] == project["id"]
    assert body["service_id"] == service_id
    assert body["key_names"] == ["API_TOKEN", "MODE"]
    assert secret_value not in json.dumps(body)

    read_response = client.get(f"/api/projects/{project['id']}/services/{service_id}/env-bundle")
    assert read_response.status_code == 200
    assert read_response.json() == body
    assert secret_value not in json.dumps(read_response.json())

    settings = get_settings()
    current_path = env_bundles.resolve_env_bundle_path(
        settings,
        env_bundles.current_env_bundle_ref(project["id"], service_id),
    )
    assert current_path.read_text(encoding="utf-8") == f"API_TOKEN={secret_value}\nMODE=prod\n"
    with connect(settings) as connection:
        row = connection.execute(
            "SELECT * FROM project_service_env_bundles WHERE project_id = ? AND service_id = ?",
            (project["id"], service_id),
        ).fetchone()
    row_text = json.dumps(dict(row), sort_keys=True)
    assert secret_value not in row_text
    assert "API_TOKEN" in row_text

    replace_response = client.post(
        f"/api/projects/{project['id']}/services/{service_id}/env-bundle",
        json={"content": "OTHER=value\n"},
    )
    assert replace_response.status_code == 201, replace_response.text
    assert replace_response.json()["key_names"] == ["OTHER"]
    assert current_path.read_text(encoding="utf-8") == "OTHER=value\n"

    delete_response = client.delete(f"/api/projects/{project['id']}/services/{service_id}/env-bundle")
    assert delete_response.status_code == 204
    assert not current_path.exists()
    empty_response = client.get(f"/api/projects/{project['id']}/services/{service_id}/env-bundle")
    assert empty_response.status_code == 200
    assert empty_response.json()["configured"] is False
    assert empty_response.json()["key_names"] == []


def test_env_bundle_api_accepts_multipart_file_upload(client):
    project, service_id = create_project(client)
    secret_value = "multipart-secret"

    response = client.post(
        f"/api/projects/{project['id']}/services/{service_id}/env-bundle",
        files={"file": ("gjallar.env", f"API_TOKEN={secret_value}\nMODE=prod\n", "text/plain")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["configured"] is True
    assert body["key_names"] == ["API_TOKEN", "MODE"]
    assert secret_value not in json.dumps(body)

    current_path = env_bundles.resolve_env_bundle_path(
        get_settings(),
        env_bundles.current_env_bundle_ref(project["id"], service_id),
    )
    assert current_path.read_text(encoding="utf-8") == f"API_TOKEN={secret_value}\nMODE=prod\n"


def test_env_bundle_api_rejects_duplicate_keys_without_echoing_values(client):
    project, service_id = create_project(client)
    secret_value = "do-not-echo"

    response = client.post(
        f"/api/projects/{project['id']}/services/{service_id}/env-bundle",
        json={"content": f"DUP={secret_value}\nDUP=other\n"},
    )

    assert response.status_code == 422
    assert "Duplicate env bundle key 'DUP'" in response.json()["detail"]
    assert secret_value not in response.text


def test_env_bundle_api_requires_service_to_belong_to_project(client):
    project, _ = create_project(client)

    response = client.post(
        f"/api/projects/{project['id']}/services/service_missing/env-bundle",
        json={"content": "KEY=value\n"},
    )

    assert response.status_code == 404
    current_ref = env_bundles.current_env_bundle_ref(project["id"], "service_missing")
    assert not env_bundles.resolve_env_bundle_path(get_settings(), current_ref).exists()


def test_env_bundle_metadata_row_is_removed_when_service_is_deleted(client):
    create_response = client.post("/api/projects", json=multi_service_payload())
    assert create_response.status_code == 201, create_response.text
    project = create_response.json()
    backend = next(service for service in project["services"] if service["name"] == "backend")
    frontend_payload = next(service for service in multi_service_payload()["services"] if service["name"] == "frontend")

    upload_response = client.post(
        f"/api/projects/{project['id']}/services/{backend['id']}/env-bundle",
        json={"content": "API_TOKEN=service-delete-secret\n"},
    )
    assert upload_response.status_code == 201, upload_response.text

    patch_response = client.patch(f"/api/projects/{project['id']}", json={"services": [frontend_payload]})

    assert patch_response.status_code == 200, patch_response.text
    with connect(get_settings()) as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM project_service_env_bundles WHERE service_id = ?",
            (backend["id"],),
        ).fetchone()["count"]
    assert count == 0
