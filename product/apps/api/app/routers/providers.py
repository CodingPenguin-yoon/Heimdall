from __future__ import annotations

from fastapi import APIRouter

from ..schemas import ProvidersStatus, RepoValidationRead, RepoValidationRequest, WebhookRegistrationRead
from ..services import providers

router = APIRouter(tags=["providers"])


@router.get("/api/providers/status", response_model=ProvidersStatus)
def get_provider_status() -> ProvidersStatus:
    return providers.get_provider_status()


@router.post("/api/providers/validate-repo", response_model=RepoValidationRead)
def validate_repo(payload: RepoValidationRequest) -> RepoValidationRead:
    return providers.validate_repo(payload)


@router.post("/api/projects/{project_id}/webhook-registration", response_model=WebhookRegistrationRead)
def register_project_webhook(project_id: str) -> WebhookRegistrationRead:
    return providers.register_project_webhook(project_id)
