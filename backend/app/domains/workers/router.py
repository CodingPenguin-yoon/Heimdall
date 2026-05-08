"""Agent worker registry API router."""

from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.domains.workers.service import AgentWorkerRegistryError, AgentWorkerRegistryService
from app.domains.workers.task_evidence import AgentTaskEvidenceError, AgentTaskEvidenceService
from app.domains.workers.task_queue import AgentTaskQueueError, AgentTaskQueueService

def require_worker_registry_api_key(
    x_heimdall_worker_registry_key: str | None = Header(default=None),
) -> None:
    """Fail-closed guard for mutable worker registry routes."""
    expected_key = os.getenv("HEIMDALL_WORKER_REGISTRY_API_KEY", "").strip()
    if not expected_key:
        raise HTTPException(
            status_code=503,
            detail="worker registry API key is not configured",
        )
    if not x_heimdall_worker_registry_key or not secrets.compare_digest(
        x_heimdall_worker_registry_key,
        expected_key,
    ):
        raise HTTPException(status_code=403, detail="invalid worker registry API key")


router = APIRouter(dependencies=[Depends(require_worker_registry_api_key)])
agent_worker_registry_service = AgentWorkerRegistryService()
agent_task_queue_service = AgentTaskQueueService()
agent_task_evidence_service = AgentTaskEvidenceService()


class AgentWorkerRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worker_id: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=255)
    hostname: str = Field(min_length=1, max_length=255)
    host_ip: str | None = Field(default=None, max_length=64)
    ssh_user: str | None = Field(default=None, max_length=255)
    agent_types: list[str] = Field(default_factory=lambda: ["codex"])
    agent_auth_status: dict[str, str] = Field(default_factory=dict)
    status: str = Field(default="unknown", max_length=32)
    labels: dict[str, Any] = Field(default_factory=dict)
    current_task_id: str | None = Field(default=None, max_length=64)
    last_checked_at: str | None = Field(default=None, max_length=128)


class AgentWorkerStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = Field(default=None, max_length=32)
    agent_auth_status: dict[str, str] | None = None
    current_task_id: str | None = Field(default=None, max_length=64)
    last_checked_at: str | None = Field(default=None, max_length=128)


class AgentWorkerHeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = Field(default=None, max_length=32)
    agent_auth_status: dict[str, str] | None = None
    current_task_id: str | None = Field(default=None, max_length=64)
    observed_at: str | None = Field(default=None, max_length=128)


class AgentWorkerResponse(BaseModel):
    worker_id: str
    display_name: str | None = None
    hostname: str
    host_ip: str | None = None
    ssh_user: str | None = None
    agent_types: list[str] = Field(default_factory=list)
    agent_auth_status: dict[str, str] = Field(default_factory=dict)
    status: str
    labels: dict[str, Any] = Field(default_factory=dict)
    current_task_id: str | None = None
    last_checked_at: str
    is_stale: bool
    created_at: str
    updated_at: str


class AgentWorkersListResponse(BaseModel):
    workers: list[AgentWorkerResponse] = Field(default_factory=list)
    total: int


class AgentTaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    agent_type: str = Field(default="codex", max_length=32)
    repo_url: str = Field(min_length=1, max_length=2048)
    target_ref: str = Field(min_length=1, max_length=255)
    required_capabilities: list[str] = Field(default_factory=list)
    labels: dict[str, Any] = Field(default_factory=dict)
    workspace_action: str = Field(default="prepare_worktree", max_length=64)
    default_branch: str | None = Field(default=None, max_length=255)
    repo_slug: str | None = Field(default=None, max_length=255)
    checkout_branch: str | None = Field(default=None, max_length=255)
    workspace_root: str | None = Field(default=None, max_length=512)
    dirty_tree_policy: str | None = Field(default=None, max_length=64)


class AgentTaskTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=1024)


class AgentTaskResponse(BaseModel):
    schema_version: str
    task_id: str
    title: str
    agent_type: str
    status: str
    assigned_worker_id: str | None = None
    repo_url: str
    target_ref: str
    workspace_action_request: dict[str, Any] = Field(default_factory=dict)
    workspace_action_contract: dict[str, Any] = Field(default_factory=dict)
    labels: dict[str, Any] = Field(default_factory=dict)
    required_capabilities: list[str] = Field(default_factory=list)
    allocation_status: str
    needs_review_reason: str | None = None
    cancellation_reason: str | None = None
    failure_reason: str | None = None
    execution_boundary: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None


class AgentTasksListResponse(BaseModel):
    tasks: list[AgentTaskResponse] = Field(default_factory=list)
    total: int


class AgentTaskEventCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(min_length=1, max_length=64)
    severity: str = Field(default="info", max_length=16)
    source: str = Field(default="worker", max_length=64)
    message: str = Field(min_length=1, max_length=4096)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTaskEventResponse(BaseModel):
    schema_version: str
    task_id: str
    sequence: int
    event_type: str
    severity: str
    source: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class AgentTaskEventsListResponse(BaseModel):
    events: list[AgentTaskEventResponse] = Field(default_factory=list)
    total: int


class AgentTaskArtifactCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(min_length=1, max_length=64)
    artifact_type: str = Field(default="other", max_length=32)
    relative_path: str = Field(min_length=1, max_length=512)
    display_name: str | None = Field(default=None, max_length=255)
    media_type: str | None = Field(default=None, max_length=128)
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTaskArtifactResponse(BaseModel):
    schema_version: str
    artifact_id: str
    task_id: str
    artifact_type: str
    relative_path: str
    path: str
    display_name: str | None = None
    media_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    retention_policy: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class AgentTaskArtifactsListResponse(BaseModel):
    artifacts: list[AgentTaskArtifactResponse] = Field(default_factory=list)
    total: int


class AgentTaskVerificationReportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(min_length=1, max_length=64)
    status: str = Field(min_length=1, max_length=32)
    summary: str = Field(min_length=1, max_length=2048)
    checks: list[dict[str, Any]] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTaskVerificationReportResponse(BaseModel):
    schema_version: str
    report_id: str
    task_id: str
    status: str
    summary: str
    checks: list[dict[str, Any]] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    review_handoff: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class AgentTaskVerificationReportsListResponse(BaseModel):
    reports: list[AgentTaskVerificationReportResponse] = Field(default_factory=list)
    total: int


@router.get("/workers", response_model=AgentWorkersListResponse)
def list_workers(
    agent_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> AgentWorkersListResponse:
    try:
        workers = agent_worker_registry_service.list_workers(agent_type=agent_type, status=status)
    except AgentWorkerRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AgentWorkersListResponse(workers=workers, total=len(workers))


@router.get("/agent-tasks", response_model=AgentTasksListResponse)
def list_agent_tasks(
    status: str | None = Query(default=None),
) -> AgentTasksListResponse:
    try:
        tasks = agent_task_queue_service.list_tasks(status=status)
    except AgentTaskQueueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AgentTasksListResponse(tasks=tasks, total=len(tasks))


@router.post("/agent-tasks", response_model=AgentTaskResponse, status_code=201)
def create_agent_task(payload: AgentTaskCreateRequest) -> AgentTaskResponse:
    try:
        return AgentTaskResponse(**agent_task_queue_service.create_task(payload.model_dump()))
    except AgentTaskQueueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/agent-tasks/{task_id}", response_model=AgentTaskResponse)
def get_agent_task(task_id: str) -> AgentTaskResponse:
    try:
        task = agent_task_queue_service.get_task(task_id)
    except AgentTaskQueueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=404, detail=f"agent task not found: {task_id}")
    return AgentTaskResponse(**task)


@router.post("/agent-tasks/{task_id}/assign", response_model=AgentTaskResponse)
def assign_agent_task(task_id: str) -> AgentTaskResponse:
    try:
        return AgentTaskResponse(**agent_task_queue_service.assign_task(task_id))
    except AgentTaskQueueError as exc:
        status_code = 404 if str(exc).startswith("agent task not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.patch("/agent-tasks/{task_id}/status", response_model=AgentTaskResponse)
def transition_agent_task(
    task_id: str,
    payload: AgentTaskTransitionRequest,
) -> AgentTaskResponse:
    try:
        return AgentTaskResponse(
            **agent_task_queue_service.transition_task(
                task_id,
                payload.model_dump(exclude_unset=True),
            )
        )
    except AgentTaskQueueError as exc:
        status_code = 404 if str(exc).startswith("agent task not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/agent-tasks/{task_id}/events", response_model=AgentTaskEventsListResponse)
def list_agent_task_events(task_id: str) -> AgentTaskEventsListResponse:
    try:
        events = agent_task_evidence_service.list_task_events(task_id)
    except AgentTaskEvidenceError as exc:
        status_code = 404 if str(exc).startswith("agent task not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return AgentTaskEventsListResponse(events=events, total=len(events))


@router.post(
    "/agent-tasks/{task_id}/events",
    response_model=AgentTaskEventResponse,
    status_code=201,
)
def append_agent_task_event(
    task_id: str,
    payload: AgentTaskEventCreateRequest,
) -> AgentTaskEventResponse:
    try:
        return AgentTaskEventResponse(
            **agent_task_evidence_service.append_task_event(
                task_id,
                payload.model_dump(),
            )
        )
    except AgentTaskEvidenceError as exc:
        status_code = 404 if str(exc).startswith("agent task not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/agent-tasks/{task_id}/artifacts", response_model=AgentTaskArtifactsListResponse)
def list_agent_task_artifacts(task_id: str) -> AgentTaskArtifactsListResponse:
    try:
        artifacts = agent_task_evidence_service.list_task_artifacts(task_id)
    except AgentTaskEvidenceError as exc:
        status_code = 404 if str(exc).startswith("agent task not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return AgentTaskArtifactsListResponse(artifacts=artifacts, total=len(artifacts))


@router.post(
    "/agent-tasks/{task_id}/artifacts",
    response_model=AgentTaskArtifactResponse,
    status_code=201,
)
def register_agent_task_artifact(
    task_id: str,
    payload: AgentTaskArtifactCreateRequest,
) -> AgentTaskArtifactResponse:
    try:
        return AgentTaskArtifactResponse(
            **agent_task_evidence_service.register_task_artifact(
                task_id,
                payload.model_dump(exclude_unset=True),
            )
        )
    except AgentTaskEvidenceError as exc:
        status_code = 404 if str(exc).startswith("agent task not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get(
    "/agent-tasks/{task_id}/verification-reports",
    response_model=AgentTaskVerificationReportsListResponse,
)
def list_agent_task_verification_reports(
    task_id: str,
) -> AgentTaskVerificationReportsListResponse:
    try:
        reports = agent_task_evidence_service.list_verification_reports(task_id)
    except AgentTaskEvidenceError as exc:
        status_code = 404 if str(exc).startswith("agent task not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return AgentTaskVerificationReportsListResponse(reports=reports, total=len(reports))


@router.post(
    "/agent-tasks/{task_id}/verification-reports",
    response_model=AgentTaskVerificationReportResponse,
    status_code=201,
)
def submit_agent_task_verification_report(
    task_id: str,
    payload: AgentTaskVerificationReportCreateRequest,
) -> AgentTaskVerificationReportResponse:
    try:
        return AgentTaskVerificationReportResponse(
            **agent_task_evidence_service.submit_verification_report(
                task_id,
                payload.model_dump(),
            )
        )
    except AgentTaskEvidenceError as exc:
        status_code = 404 if str(exc).startswith("agent task not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/workers/register", response_model=AgentWorkerResponse, status_code=201)
def register_worker(payload: AgentWorkerRegisterRequest) -> AgentWorkerResponse:
    try:
        return AgentWorkerResponse(
            **agent_worker_registry_service.register_worker(payload.model_dump())
        )
    except AgentWorkerRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workers/{worker_id}", response_model=AgentWorkerResponse)
def get_worker(worker_id: str) -> AgentWorkerResponse:
    try:
        worker = agent_worker_registry_service.get_worker(worker_id)
    except AgentWorkerRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if worker is None:
        raise HTTPException(status_code=404, detail=f"worker not found: {worker_id}")
    return AgentWorkerResponse(**worker)


@router.patch("/workers/{worker_id}/status", response_model=AgentWorkerResponse)
def update_worker_status(
    worker_id: str,
    payload: AgentWorkerStatusUpdateRequest,
) -> AgentWorkerResponse:
    try:
        return AgentWorkerResponse(
            **agent_worker_registry_service.update_worker_status(
                worker_id,
                payload.model_dump(exclude_unset=True),
            )
        )
    except AgentWorkerRegistryError as exc:
        status_code = 404 if str(exc).startswith("worker not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/workers/{worker_id}/heartbeat", response_model=AgentWorkerResponse)
def record_worker_heartbeat(
    worker_id: str,
    payload: AgentWorkerHeartbeatRequest,
) -> AgentWorkerResponse:
    try:
        return AgentWorkerResponse(
            **agent_worker_registry_service.record_worker_heartbeat(
                worker_id,
                payload.model_dump(exclude_unset=True),
            )
        )
    except AgentWorkerRegistryError as exc:
        status_code = 404 if str(exc).startswith("worker not found") else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
