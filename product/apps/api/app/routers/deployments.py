from fastapi import APIRouter, status

from ..schemas import (
    DeploymentLogsRead,
    DeploymentRead,
    DeploymentRequest,
    DeploymentResult,
    ReleaseRead,
    RollbackRequest,
    RollbackResponse,
)
from ..services import deployments

router = APIRouter(tags=["deployments"])


@router.post("/api/projects/{project_id}/deployments", response_model=DeploymentResult, status_code=status.HTTP_201_CREATED)
def create_deployment(project_id: str, payload: DeploymentRequest) -> DeploymentResult:
    return deployments.create_manual_deployment(project_id, payload)


@router.get("/api/deployments/{deployment_id}", response_model=DeploymentRead)
def get_deployment(deployment_id: str) -> DeploymentRead:
    return deployments.get_deployment(deployment_id)


@router.get("/api/projects/{project_id}/deployments", response_model=list[DeploymentRead])
def list_project_deployments(project_id: str) -> list[DeploymentRead]:
    return deployments.list_project_deployments(project_id)


@router.get("/api/deployments/{deployment_id}/logs", response_model=DeploymentLogsRead)
def get_deployment_logs(deployment_id: str) -> DeploymentLogsRead:
    return deployments.get_deployment_logs(deployment_id)


@router.get("/api/projects/{project_id}/releases", response_model=list[ReleaseRead])
def list_releases(project_id: str) -> list[ReleaseRead]:
    return deployments.list_releases(project_id)


@router.post("/api/projects/{project_id}/rollback", response_model=RollbackResponse, status_code=status.HTTP_409_CONFLICT)
def rollback_project(project_id: str, payload: RollbackRequest) -> RollbackResponse:
    return deployments.rollback_release(project_id, payload.release_id)
