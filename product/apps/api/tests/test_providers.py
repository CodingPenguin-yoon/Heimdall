import httpx

from .test_projects import project_payload


def refresh_settings():
    from app.config import get_settings

    get_settings.cache_clear()


def test_provider_status_is_sanitized_without_secrets(client):
    response = client.get("/api/providers/status")

    assert response.status_code == 200
    body = response.json()
    assert body["public_base_url"] == "http://127.0.0.1:8000"
    assert body["public_base_url_usable"] is False
    assert body["webhook_urls"]["github"].endswith("/api/webhooks/github")
    assert body["providers"]["github"]["token_configured"] is False
    assert body["providers"]["github"]["webhook_secret_configured"] is False
    assert body["providers"]["gitlab"]["base_url_configured"] is False
    assert "api_token" not in body
    assert "webhook_secret" not in body


def test_validate_github_repo_uses_configured_api_host(client, monkeypatch):
    monkeypatch.setenv("HEIMDALL_GITHUB_API_TOKEN", "configured-token")
    monkeypatch.setenv("HEIMDALL_GITHUB_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("HEIMDALL_PUBLIC_BASE_URL", "https://heimdall.example.test")
    refresh_settings()

    def fake_get(url, headers, timeout):
        assert url == "https://api.github.com/repos/example/preview-api"
        assert headers["Authorization"].startswith("Bearer ")
        assert timeout == 10.0
        return httpx.Response(
            200,
            json={
                "id": 12345,
                "full_name": "example/preview-api",
                "default_branch": "trunk",
                "private": True,
            },
        )

    monkeypatch.setattr("app.services.providers.httpx.get", fake_get)

    response = client.post(
        "/api/providers/validate-repo",
        json={"provider": "github", "repo_url": "https://github.com/example/preview-api.git"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "github"
    assert body["normalized_repo"] == "github.com/example/preview-api"
    assert body["provider_project_id"] == "12345"
    assert body["full_name"] == "example/preview-api"
    assert body["default_branch"] == "trunk"
    assert body["private"] is True
    assert body["access_valid"] is True
    assert body["can_register_webhook"] is True


def test_validate_gitlab_repo_rejects_mismatched_host(client, monkeypatch):
    monkeypatch.setenv("HEIMDALL_GITLAB_BASE_URL", "https://gitlab.example.test")
    monkeypatch.setenv("HEIMDALL_GITLAB_API_TOKEN", "configured-token")
    refresh_settings()

    response = client.post(
        "/api/providers/validate-repo",
        json={"provider": "gitlab", "repo_url": "https://evil.example.test/group/repo.git"},
    )

    assert response.status_code == 422
    assert "host must match" in response.json()["detail"]


def test_validate_gitlab_repo_supports_nested_group_path(client, monkeypatch):
    monkeypatch.setenv("HEIMDALL_GITLAB_BASE_URL", "https://gitlab.example.test")
    monkeypatch.setenv("HEIMDALL_GITLAB_API_TOKEN", "configured-token")
    monkeypatch.setenv("HEIMDALL_GITLAB_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("HEIMDALL_PUBLIC_BASE_URL", "https://heimdall.example.test")
    refresh_settings()

    def fake_get(url, headers, timeout):
        assert url == "https://gitlab.example.test/api/v4/projects/team%2Fservices%2Fpreview-api"
        assert "PRIVATE-TOKEN" in headers
        return httpx.Response(
            200,
            json={
                "id": 678,
                "path_with_namespace": "team/services/preview-api",
                "default_branch": "main",
                "visibility": "private",
            },
        )

    monkeypatch.setattr("app.services.providers.httpx.get", fake_get)

    response = client.post(
        "/api/providers/validate-repo",
        json={"repo_url": "https://gitlab.example.test/team/services/preview-api.git"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "gitlab"
    assert body["normalized_repo"] == "gitlab.example.test/team/services/preview-api"
    assert body["provider_project_id"] == "678"
    assert body["private"] is True
    assert body["can_register_webhook"] is True


def test_register_github_webhook_reuses_existing_hook(client, monkeypatch):
    monkeypatch.setenv("HEIMDALL_GITHUB_API_TOKEN", "configured-token")
    monkeypatch.setenv("HEIMDALL_GITHUB_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("HEIMDALL_PUBLIC_BASE_URL", "https://heimdall.example.test")
    refresh_settings()
    project = client.post("/api/projects", json=project_payload()).json()

    def fake_get(url, headers, timeout):
        assert url == "https://api.github.com/repos/example/preview-api/hooks"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 9001,
                    "active": True,
                    "events": ["push"],
                    "config": {"url": "https://heimdall.example.test/api/webhooks/github"},
                }
            ],
        )

    def fake_post(url, headers, json, timeout):
        raise AssertionError("existing hook should be reused")

    monkeypatch.setattr("app.services.providers.httpx.get", fake_get)
    monkeypatch.setattr("app.services.providers.httpx.post", fake_post)

    response = client.post(f"/api/projects/{project['id']}/webhook-registration")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "already_registered"
    assert body["provider_webhook_id"] == "9001"
    assert body["webhook_url"] == "https://heimdall.example.test/api/webhooks/github"

    project_response = client.get(f"/api/projects/{project['id']}")
    assert project_response.json()["webhook_registration"]["status"] == "already_registered"


def test_register_webhook_rejects_local_public_base_url(client, monkeypatch):
    monkeypatch.setenv("HEIMDALL_GITHUB_API_TOKEN", "configured-token")
    monkeypatch.setenv("HEIMDALL_GITHUB_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("HEIMDALL_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    refresh_settings()
    project = client.post("/api/projects", json=project_payload()).json()

    response = client.post(f"/api/projects/{project['id']}/webhook-registration")

    assert response.status_code == 422
    assert "HTTPS" in response.json()["detail"]
