"""DevOps MVP typed API skeleton router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.domains.devops.schemas import (
    CiCdActionPreviewResponse,
    CiCdRunCreateRequest,
    CiCdRunResponse,
    CiCdRunsListResponse,
    DatabaseCheckRecordRequest,
    DatabaseStatusCreateRequest,
    DatabaseStatusResponse,
    DatabaseStatusesListResponse,
    DeploymentTargetReferenceCreateRequest,
    DeploymentTargetReferenceResponse,
    DeploymentTargetsListResponse,
    DevOpsDashboardResponse,
    DevOpsServiceCreateRequest,
    DevOpsServiceResponse,
    DevOpsServicesListResponse,
    ServiceEnvironmentCreateRequest,
    ServiceEnvironmentResponse,
    ServiceEnvironmentsListResponse,
    ServiceSummaryResponse,
)
from app.domains.devops.service import DevOpsCatalogError, DevOpsCatalogService


router = APIRouter()
devops_catalog_service = DevOpsCatalogService()


@router.get("/devops/services", response_model=DevOpsServicesListResponse)
async def list_services() -> DevOpsServicesListResponse:
    services = devops_catalog_service.list_services()
    return DevOpsServicesListResponse(services=services, total=len(services))


@router.post("/devops/services", response_model=DevOpsServiceResponse, status_code=201)
async def create_service(payload: DevOpsServiceCreateRequest) -> DevOpsServiceResponse:
    return devops_catalog_service.create_service(payload)


@router.get("/devops/services/{service_id}/summary", response_model=ServiceSummaryResponse)
async def get_service_summary(service_id: str) -> ServiceSummaryResponse:
    try:
        return devops_catalog_service.build_service_summary(service_id)
    except DevOpsCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/devops/environments", response_model=ServiceEnvironmentsListResponse)
async def list_environments(
    service_id: str | None = None,
    environment: str | None = None,
) -> ServiceEnvironmentsListResponse:
    environments = devops_catalog_service.list_environments(
        service_id=service_id,
        environment=environment,
    )
    return ServiceEnvironmentsListResponse(
        environments=environments,
        total=len(environments),
    )


@router.post(
    "/devops/services/{service_id}/environments",
    response_model=ServiceEnvironmentResponse,
    status_code=201,
)
async def create_environment(
    service_id: str,
    payload: ServiceEnvironmentCreateRequest,
) -> ServiceEnvironmentResponse:
    if payload.service_id != service_id:
        raise HTTPException(status_code=400, detail="service_id path and payload mismatch")
    try:
        return devops_catalog_service.create_environment(payload)
    except DevOpsCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/devops/deployment-targets", response_model=DeploymentTargetsListResponse)
async def list_deployment_targets(
    environment_id: str | None = None,
) -> DeploymentTargetsListResponse:
    targets = devops_catalog_service.list_deployment_targets(environment_id=environment_id)
    return DeploymentTargetsListResponse(deployment_targets=targets, total=len(targets))


@router.post(
    "/devops/environments/{environment_id}/deployment-targets",
    response_model=DeploymentTargetReferenceResponse,
    status_code=201,
)
async def create_deployment_target(
    environment_id: str,
    payload: DeploymentTargetReferenceCreateRequest,
) -> DeploymentTargetReferenceResponse:
    if payload.environment_id != environment_id:
        raise HTTPException(status_code=400, detail="environment_id path and payload mismatch")
    try:
        return devops_catalog_service.create_deployment_target(payload)
    except DevOpsCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/devops/ci-runs", response_model=CiCdRunsListResponse)
async def list_ci_runs(
    service_id: str | None = None,
    environment_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> CiCdRunsListResponse:
    runs = devops_catalog_service.list_ci_runs(
        service_id=service_id,
        environment_id=environment_id,
        status=status,
        limit=limit,
    )
    return CiCdRunsListResponse(ci_runs=runs, total=len(runs))


@router.post("/devops/ci-runs", response_model=CiCdRunResponse, status_code=201)
async def create_ci_run(payload: CiCdRunCreateRequest) -> CiCdRunResponse:
    try:
        return devops_catalog_service.create_ci_run(payload)
    except DevOpsCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/devops/ci-runs/{run_id}/actions/{action}:preview",
    response_model=CiCdActionPreviewResponse,
)
async def preview_ci_run_action(run_id: str, action: str) -> CiCdActionPreviewResponse:
    try:
        return devops_catalog_service.preview_ci_run_action(run_id, action)
    except DevOpsCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/devops/db-status", response_model=DatabaseStatusesListResponse)
async def list_db_status(
    environment_id: str | None = None,
) -> DatabaseStatusesListResponse:
    statuses = devops_catalog_service.list_db_statuses(environment_id=environment_id)
    return DatabaseStatusesListResponse(db_statuses=statuses, total=len(statuses))


@router.post(
    "/devops/environments/{environment_id}/db-status",
    response_model=DatabaseStatusResponse,
    status_code=201,
)
async def create_db_status(
    environment_id: str,
    payload: DatabaseStatusCreateRequest,
) -> DatabaseStatusResponse:
    if payload.environment_id != environment_id:
        raise HTTPException(status_code=400, detail="environment_id path and payload mismatch")
    try:
        return devops_catalog_service.create_db_status(payload)
    except DevOpsCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/devops/db-status/{db_status_id}/checks:record",
    response_model=DatabaseStatusResponse,
)
async def record_db_status_check(
    db_status_id: str,
    payload: DatabaseCheckRecordRequest,
) -> DatabaseStatusResponse:
    current = devops_catalog_service._db_statuses.get(db_status_id)
    if current is None:
        raise HTTPException(status_code=404, detail=f"db status not found: {db_status_id}")
    updated = current.model_copy(
        update={
            key: value
            for key, value in payload.model_dump(exclude_none=True).items()
            if key != "checked_at"
        }
    )
    if payload.checked_at is not None:
        updated = updated.model_copy(update={"last_checked_at": payload.checked_at})
    devops_catalog_service._db_statuses[db_status_id] = updated
    return updated


@router.get("/devops/dashboard", response_model=DevOpsDashboardResponse)
async def get_dashboard() -> DevOpsDashboardResponse:
    return devops_catalog_service.build_dashboard_summary()
