import hashlib
import hmac
import json

from .test_projects import project_payload


def test_webhook_records_event_and_queues_deployment(client):
    project_response = client.post("/api/projects", json=project_payload())
    project = project_response.json()

    payload = {
        "ref": "refs/heads/main",
        "after": "abc123abc123abc123abc123abc123abc123abcd",
        "repository": {
            "clone_url": project["repo_url"],
        },
    }
    response = client.post(
        "/api/webhooks/github",
        json=payload,
        headers={"X-GitHub-Event": "push", "X-GitHub-Delivery": "delivery-1"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "accepted"
    assert body["webhook_event"]["status"] == "accepted"
    assert body["deployment"]["status"] == "queued"
    assert body["deployment"]["is_dry_run"] is True


def test_webhook_ignores_non_tracked_branch(client):
    client.post("/api/projects", json=project_payload(tracked_branch="main"))
    payload = {
        "ref": "refs/heads/feature",
        "after": "abc123abc123abc123abc123abc123abc123abcd",
        "repository": {
            "clone_url": "https://github.com/example/preview-api.git",
        },
    }
    response = client.post(
        "/api/webhooks/github",
        json=payload,
        headers={"X-GitHub-Event": "push", "X-GitHub-Delivery": "delivery-2"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["webhook_event"]["status"] == "ignored"


def test_gitlab_webhook_records_event_and_queues_deployment(client):
    project_response = client.post(
        "/api/projects",
        json=project_payload(provider="gitlab", repo_url="https://gitlab.com/example/preview-api.git"),
    )
    project = project_response.json()

    payload = {
        "ref": "refs/heads/main",
        "checkout_sha": "def456def456def456def456def456def456def4",
        "project": {
            "git_http_url": project["repo_url"],
        },
    }
    response = client.post(
        "/api/webhooks/gitlab",
        json=payload,
        headers={"X-Gitlab-Event": "Push Hook", "X-Gitlab-Event-UUID": "gitlab-delivery-1"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "accepted"
    assert body["webhook_event"]["provider"] == "gitlab"
    assert body["webhook_event"]["status"] == "accepted"
    assert body["deployment"]["status"] == "queued"


def test_github_webhook_requires_valid_signature_when_secret_configured(client, monkeypatch):
    project_response = client.post("/api/projects", json=project_payload())
    project = project_response.json()
    monkeypatch.setenv("HEIMDALL_GITHUB_WEBHOOK_SECRET", "configured-secret")

    from app.config import get_settings
    from app.db import connect

    get_settings.cache_clear()
    payload = {
        "ref": "refs/heads/main",
        "after": "abc123abc123abc123abc123abc123abc123abcd",
        "repository": {"clone_url": project["repo_url"]},
    }

    missing_signature = client.post(
        "/api/webhooks/github",
        json=payload,
        headers={"X-GitHub-Event": "push", "X-GitHub-Delivery": "signed-delivery-1"},
    )
    assert missing_signature.status_code == 401

    with connect(get_settings()) as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM webhook_events").fetchone()
        assert row["count"] == 0

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(b"configured-secret", body, hashlib.sha256).hexdigest()
    signed_response = client.post(
        "/api/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "signed-delivery-2",
            "X-Hub-Signature-256": f"sha256={signature}",
        },
    )
    assert signed_response.status_code == 200, signed_response.text
    assert signed_response.json()["status"] == "accepted"


def test_gitlab_webhook_requires_token_when_secret_configured(client, monkeypatch):
    client.post(
        "/api/projects",
        json=project_payload(provider="gitlab", repo_url="https://gitlab.com/example/preview-api.git"),
    )
    monkeypatch.setenv("HEIMDALL_GITLAB_WEBHOOK_SECRET", "configured-secret")

    from app.config import get_settings
    from app.db import connect

    get_settings.cache_clear()
    payload = {
        "ref": "refs/heads/main",
        "checkout_sha": "def456def456def456def456def456def456def4",
        "project": {"git_http_url": "https://gitlab.com/example/preview-api.git"},
    }

    response = client.post(
        "/api/webhooks/gitlab",
        json=payload,
        headers={"X-Gitlab-Event": "Push Hook", "X-Gitlab-Event-UUID": "gitlab-token-delivery-1"},
    )

    assert response.status_code == 401
    with connect(get_settings()) as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM webhook_events").fetchone()
        assert row["count"] == 0


def test_webhook_project_matching_includes_provider(client):
    client.post(
        "/api/projects",
        json=project_payload(provider="gitlab", repo_url="https://github.com/example/preview-api.git"),
    )
    payload = {
        "ref": "refs/heads/main",
        "after": "abc123abc123abc123abc123abc123abc123abcd",
        "repository": {
            "clone_url": "https://github.com/example/preview-api.git",
        },
    }

    response = client.post(
        "/api/webhooks/github",
        json=payload,
        headers={"X-GitHub-Event": "push", "X-GitHub-Delivery": "delivery-provider-scope"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ignored"
    assert body["webhook_event"]["status"] == "unknown_project"
