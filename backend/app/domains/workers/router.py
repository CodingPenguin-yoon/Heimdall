"""Agent worker registry API router."""

from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.domains.workers.service import AgentWorkerRegistryError, AgentWorkerRegistryService

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
