from __future__ import annotations

import sqlite3
import uuid
import hashlib
import hmac
import json

from fastapi import HTTPException, Request

from ..config import get_settings
from ..db import connect, row_to_dict
from ..models import ACTIVE_DEPLOYMENT_STATUSES, DeploymentStatus, TriggerType, WebhookEventStatus
from ..schemas import DeploymentRead, WebhookEventRead, WebhookResponse
from ..validation import branch_from_ref, normalize_repo_url
from .deployments import _serialize_deployment
from .projects import utc_now


def _serialize_webhook_event(row: sqlite3.Row) -> WebhookEventRead:
    data = row_to_dict(row)
    assert data is not None
    return WebhookEventRead(**data)


def _existing_event(connection: sqlite3.Connection, provider: str, delivery_id: str | None) -> sqlite3.Row | None:
    if not delivery_id:
        return None
    return connection.execute(
        "SELECT * FROM webhook_events WHERE provider = ? AND delivery_id = ?",
        (provider, delivery_id),
    ).fetchone()


def _find_project_by_repo(connection: sqlite3.Connection, provider: str, repo_url: str | None) -> sqlite3.Row | None:
    if not repo_url:
        return None
    normalized = normalize_repo_url(repo_url)
    for row in connection.execute("SELECT * FROM projects WHERE provider = ?", (provider,)).fetchall():
        project = row_to_dict(row)
        assert project is not None
        if normalize_repo_url(str(project["repo_url"])) == normalized:
            return row
    return None


def _active_deployment_exists(connection: sqlite3.Connection, project_id: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM deployments
        WHERE project_id = ? AND status IN (?, ?, ?, ?, ?)
        LIMIT 1
        """,
        (project_id, *ACTIVE_DEPLOYMENT_STATUSES),
    ).fetchone()
    return row is not None


def _insert_event(
    connection: sqlite3.Connection,
    *,
    provider: str,
    event_type: str | None,
    delivery_id: str | None,
    project_id: str | None,
    branch: str | None,
    commit_sha: str | None,
    status: str,
    error_message: str | None = None,
    deployment_id: str | None = None,
) -> sqlite3.Row:
    event_id = f"hook_{uuid.uuid4().hex[:12]}"
    received_at = utc_now()
    connection.execute(
        """
        INSERT INTO webhook_events (
            id, provider, event_type, delivery_id, project_id, branch, commit_sha,
            status, received_at, deployment_id, error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            provider,
            event_type,
            delivery_id,
            project_id,
            branch,
            commit_sha,
            status,
            received_at,
            deployment_id,
            error_message,
        ),
    )
    row = connection.execute("SELECT * FROM webhook_events WHERE id = ?", (event_id,)).fetchone()
    assert row is not None
    return row


def _extract_github(payload: dict, request: Request) -> tuple[str | None, str | None, str | None, str | None]:
    event_type = request.headers.get("X-GitHub-Event")
    delivery_id = request.headers.get("X-GitHub-Delivery")
    repo_url = payload.get("repository", {}).get("clone_url") or payload.get("repository", {}).get("html_url")
    branch = branch_from_ref(payload.get("ref"))
    commit_sha = payload.get("after")
    return event_type, delivery_id, repo_url, branch or commit_sha and branch_from_ref(payload.get("ref"))


def _extract_gitlab(payload: dict, request: Request) -> tuple[str | None, str | None, str | None, str | None]:
    event_type = request.headers.get("X-Gitlab-Event")
    delivery_id = request.headers.get("X-Gitlab-Event-UUID") or request.headers.get("X-Request-Id")
    project = payload.get("project", {})
    repo_url = project.get("git_http_url") or project.get("web_url")
    branch = branch_from_ref(payload.get("ref"))
    commit_sha = payload.get("checkout_sha") or payload.get("after")
    return event_type, delivery_id, repo_url, branch or commit_sha and branch_from_ref(payload.get("ref"))


def _create_queued_deployment(
    connection: sqlite3.Connection,
    *,
    project_id: str,
    trigger_type: str,
    requested_ref: str | None,
    requested_commit_sha: str | None,
) -> sqlite3.Row:
    deployment_id = f"deploy_{uuid.uuid4().hex[:12]}"
    created_at = utc_now()
    connection.execute(
        """
        INSERT INTO deployments (
            id, project_id, trigger_type, requested_ref, requested_commit_sha, resolved_commit_sha,
            image_tag, previous_release_id, target_release_id, status, status_message, is_dry_run,
            started_at, finished_at, duration_ms, log_path, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            deployment_id,
            project_id,
            trigger_type,
            requested_ref,
            requested_commit_sha,
            None,
            None,
            None,
            None,
            DeploymentStatus.QUEUED.value,
            "Webhook accepted. Deployment execution is intentionally not run inline.",
            1,
            None,
            None,
            None,
            None,
            created_at,
        ),
    )
    row = connection.execute("SELECT * FROM deployments WHERE id = ?", (deployment_id,)).fetchone()
    assert row is not None
    return row


def _handle_webhook(provider: str, payload: dict, request: Request) -> WebhookResponse:
    if provider == "github":
        event_type, delivery_id, repo_url, branch = _extract_github(payload, request)
        commit_sha = payload.get("after")
        trigger_type = TriggerType.GITHUB_WEBHOOK.value
    else:
        event_type, delivery_id, repo_url, branch = _extract_gitlab(payload, request)
        commit_sha = payload.get("checkout_sha") or payload.get("after")
        trigger_type = TriggerType.GITLAB_WEBHOOK.value

    with connect() as connection:
        existing = _existing_event(connection, provider, delivery_id)
        if existing is not None:
            deployment = None
            if existing["deployment_id"]:
                deployment_row = connection.execute(
                    "SELECT * FROM deployments WHERE id = ?",
                    (existing["deployment_id"],),
                ).fetchone()
                if deployment_row is not None:
                    deployment = _serialize_deployment(deployment_row)
            return WebhookResponse(status="duplicate", webhook_event=_serialize_webhook_event(existing), deployment=deployment)

        project_row = _find_project_by_repo(connection, provider, repo_url)
        if project_row is None:
            event_row = _insert_event(
                connection,
                provider=provider,
                event_type=event_type,
                delivery_id=delivery_id,
                project_id=None,
                branch=branch,
                commit_sha=commit_sha,
                status=WebhookEventStatus.UNKNOWN_PROJECT.value,
                error_message="No registered project matched the webhook repository URL.",
            )
            return WebhookResponse(status="ignored", webhook_event=_serialize_webhook_event(event_row))

        project = row_to_dict(project_row)
        assert project is not None
        if branch != project["tracked_branch"]:
            event_row = _insert_event(
                connection,
                provider=provider,
                event_type=event_type,
                delivery_id=delivery_id,
                project_id=project["id"],
                branch=branch,
                commit_sha=commit_sha,
                status=WebhookEventStatus.IGNORED.value,
                error_message=f"Branch '{branch}' does not match tracked branch '{project['tracked_branch']}'.",
            )
            return WebhookResponse(status="ignored", webhook_event=_serialize_webhook_event(event_row))

        if not int(project["auto_deploy_enabled"]):
            event_row = _insert_event(
                connection,
                provider=provider,
                event_type=event_type,
                delivery_id=delivery_id,
                project_id=project["id"],
                branch=branch,
                commit_sha=commit_sha,
                status=WebhookEventStatus.IGNORED.value,
                error_message="Auto deploy is disabled for this project.",
            )
            return WebhookResponse(status="ignored", webhook_event=_serialize_webhook_event(event_row))

        if _active_deployment_exists(connection, project["id"]):
            event_row = _insert_event(
                connection,
                provider=provider,
                event_type=event_type,
                delivery_id=delivery_id,
                project_id=project["id"],
                branch=branch,
                commit_sha=commit_sha,
                status=WebhookEventStatus.IGNORED.value,
                error_message="An active deployment already exists for this project.",
            )
            return WebhookResponse(status="ignored", webhook_event=_serialize_webhook_event(event_row))

        deployment_row = _create_queued_deployment(
            connection,
            project_id=project["id"],
            trigger_type=trigger_type,
            requested_ref=branch,
            requested_commit_sha=commit_sha,
        )
        event_row = _insert_event(
            connection,
            provider=provider,
            event_type=event_type,
            delivery_id=delivery_id,
            project_id=project["id"],
            branch=branch,
            commit_sha=commit_sha,
            status=WebhookEventStatus.ACCEPTED.value,
            deployment_id=deployment_row["id"],
        )
        return WebhookResponse(
            status="accepted",
            webhook_event=_serialize_webhook_event(event_row),
            deployment=_serialize_deployment(deployment_row),
        )


def _verify_github_signature(body: bytes, signature_header: str | None) -> None:
    secret = get_settings().github_webhook_secret
    if not secret:
        return
    if not signature_header:
        raise HTTPException(status_code=401, detail="Missing GitHub webhook signature.")
    prefix = "sha256="
    if not signature_header.startswith(prefix):
        raise HTTPException(status_code=403, detail="Invalid GitHub webhook signature.")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(f"{prefix}{expected}", signature_header):
        raise HTTPException(status_code=403, detail="Invalid GitHub webhook signature.")


def _verify_gitlab_token(token_header: str | None) -> None:
    secret = get_settings().gitlab_webhook_secret
    if not secret:
        return
    if not token_header:
        raise HTTPException(status_code=401, detail="Missing GitLab webhook token.")
    if not hmac.compare_digest(secret, token_header):
        raise HTTPException(status_code=403, detail="Invalid GitLab webhook token.")


async def handle_github_webhook(request: Request) -> WebhookResponse:
    body = await request.body()
    _verify_github_signature(body, request.headers.get("X-Hub-Signature-256"))
    try:
        payload = json.loads(body)
    except Exception as exc:  # pragma: no cover - FastAPI already guards invalid JSON
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc
    return _handle_webhook("github", payload, request)


async def handle_gitlab_webhook(request: Request) -> WebhookResponse:
    _verify_gitlab_token(request.headers.get("X-Gitlab-Token"))
    try:
        payload = await request.json()
    except Exception as exc:  # pragma: no cover - FastAPI already guards invalid JSON
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc
    return _handle_webhook("gitlab", payload, request)
