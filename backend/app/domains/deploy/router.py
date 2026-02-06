"""
배포 API 라우트 (deploy 도메인)

기존 `app.routes.deploy` 라우터를 도메인 구조로 옮긴 구현입니다.
"""

from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.services.deployment.service import DeploymentService


router = APIRouter()
deployment_service = DeploymentService()


class DeployRequest(BaseModel):
    """배포 요청 모델 (Proxmox/VM/Ansible 설정 포함)"""

    # Proxmox 리소스 선택 (마법사 스타일)
    server_id: Optional[str] = None
    template_id: Optional[str] = None
    iso_image_id: Optional[str] = None  # ISO 이미지 ID (템플릿 없이 생성 시)
    storage_id: Optional[str] = None
    storage_type: Optional[str] = None
    network_ids: Optional[List[str]] = None

    # VM 설정 (템플릿 미사용 시)
    cpu_cores: Optional[int] = None
    memory_gb: Optional[int] = None

    # 인스턴스 이름
    server_name: Optional[str] = None

    # Ansible 설정
    ansible_packages: Optional[List[str]] = []
    ansible_roles: Optional[List[str]] = []

    # 옵션 플래그
    skip_terraform: Optional[bool] = False
    skip_ansible: Optional[bool] = False


class DeployResponse(BaseModel):
    """배포 응답 모델"""

    task_id: str
    message: str
    status: str


@router.post("/deploy", response_model=DeployResponse)
async def deploy(
    request: DeployRequest,
    background_tasks: BackgroundTasks,
):
    """
    인프라 배포 시작

    Terraform apply와 Ansible playbook을 순차적으로 실행합니다.
    BackgroundTasks를 사용하여 비동기적으로 처리됩니다.
    """
    try:
        deploy_request_dict = request.model_dump(exclude_none=True)

        task_id = deployment_service.start_deployment_with_request(
            background_tasks=background_tasks,
            deploy_request=deploy_request_dict,
            skip_terraform=request.skip_terraform or False,
            skip_ansible=request.skip_ansible or False,
        )

        return DeployResponse(
            task_id=task_id,
            message="배포 작업이 시작되었습니다.",
            status="pending",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"배포 시작 실패: {str(e)}",
        )


__all__ = ["router"]

