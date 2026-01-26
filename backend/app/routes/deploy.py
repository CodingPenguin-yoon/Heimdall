"""
배포 API 라우트 모듈

이 모듈은 인프라 배포를 시작하는 API 엔드포인트를 제공합니다.
- POST /api/deploy: 배포 작업 시작 및 task_id 반환
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.deployment_service import DeploymentService

router = APIRouter()
deployment_service = DeploymentService()


class DeployRequest(BaseModel):
    """배포 요청 모델"""
    # Proxmox 리소스 선택 (마법사 스타일)
    server_id: Optional[str] = None
    template_id: Optional[str] = None
    storage_id: Optional[str] = None
    storage_type: Optional[str] = None
    network_ids: Optional[list] = None
    
    # VM 설정 (템플릿 미사용 시)
    cpu_cores: Optional[int] = None
    memory_gb: Optional[int] = None
    
    # 인스턴스 이름
    server_name: Optional[str] = None
    
    # Ansible 설정
    ansible_packages: Optional[list] = []
    ansible_roles: Optional[list] = []
    
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
    background_tasks: BackgroundTasks
):
    """
    인프라 배포 시작
    
    Terraform apply와 Ansible playbook을 순차적으로 실행합니다.
    BackgroundTasks를 사용하여 비동기적으로 처리됩니다.
    
    Args:
        request: 배포 요청 데이터 (skip_terraform, skip_ansible 옵션)
        background_tasks: FastAPI BackgroundTasks 인스턴스
        
    Returns:
        DeployResponse: task_id와 상태 정보
        
    Raises:
        HTTPException: 배포 시작 실패 시
    """
    try:
        # 배포 요청 정보를 딕셔너리로 변환
        deploy_request_dict = request.model_dump(exclude_none=True)
        
        # 배포 요청 정보와 함께 배포 시작
        task_id = deployment_service.start_deployment_with_request(
            background_tasks=background_tasks,
            deploy_request=deploy_request_dict,
            skip_terraform=request.skip_terraform or False,
            skip_ansible=request.skip_ansible or False
        )
        
        return DeployResponse(
            task_id=task_id,
            message="배포 작업이 시작되었습니다.",
            status="pending"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"배포 시작 실패: {str(e)}"
        )
