"""배포 API 라우트 (deploy 도메인)."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv4Interface, ip_address, ip_interface
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field



router = APIRouter()


class DeployRequest(BaseModel):
    """배포 요청 모델 (Proxmox/VM/Ansible 설정 포함)"""

    # Proxmox 리소스 선택 (마법사 스타일)
    server_id: Optional[str] = None
    template_id: Optional[str] = None
    storage_id: Optional[str] = None
    storage_type: Optional[str] = None
    network_ids: Optional[List[str]] = None

    # VM 설정 (템플릿 미사용 시)
    cpu_cores: Optional[int] = Field(default=None, ge=1)
    memory_gb: Optional[int] = Field(default=None, ge=1)
    disk_size_gb: Optional[int] = Field(default=None, ge=1)

    # 인스턴스 이름
    server_name: Optional[str] = None
    vm_ip: Optional[str] = None
    vm_gateway: Optional[str] = None

    # Ansible 설정
    ansible_packages: List[str] = Field(default_factory=list)
    ansible_roles: List[str] = Field(default_factory=list)

    # 옵션 플래그
    skip_terraform: Optional[bool] = False
    skip_ansible: Optional[bool] = False
    create_as_staging_host: Optional[bool] = False


class DeployResponse(BaseModel):
    """배포 응답 모델"""

    task_id: str
    message: str
    status: str


def _validate_static_network(request: DeployRequest) -> None:
    vm_ip = request.vm_ip
    vm_gateway = request.vm_gateway

    if not vm_ip and not vm_gateway:
        return

    if not vm_ip or not vm_gateway:
        raise HTTPException(
            status_code=400,
            detail="Static IP deploys require both vm_ip (CIDR) and vm_gateway.",
        )

    if "/" not in vm_ip:
        raise HTTPException(
            status_code=400,
            detail="vm_ip must be an IPv4 host CIDR like 192.168.2.100/24.",
        )

    try:
        parsed_ip = ip_interface(vm_ip)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="vm_ip must be an IPv4 host CIDR like 192.168.2.100/24.",
        ) from exc

    if not isinstance(parsed_ip, IPv4Interface):
        raise HTTPException(
            status_code=400,
            detail="vm_ip must be an IPv4 host CIDR like 192.168.2.100/24.",
        )

    try:
        parsed_gateway = ip_address(vm_gateway)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="vm_gateway must be a valid IPv4 address like 192.168.2.1.",
        ) from exc

    if not isinstance(parsed_gateway, IPv4Address):
        raise HTTPException(
            status_code=400,
            detail="vm_gateway must be a valid IPv4 address like 192.168.2.1.",
        )


@router.post("/deploy", response_model=DeployResponse)
async def deploy(
    request: DeployRequest,
    background_tasks: BackgroundTasks,
):
    """
    Deprecated VM provisioning endpoint.

    Heimdall no longer owns Proxmox VM/instance creation. Gjallar is the
    provisioning owner; Heimdall consumes Gjallar-created hosts/workers through
    typed registries and self-report APIs.
    """
    raise HTTPException(
        status_code=410,
        detail=(
            "VM/instance provisioning has moved to Gjallar. "
            "Create hosts or VMs in Gjallar, then register the resulting "
            "worker/host in Heimdall."
        ),
    )


__all__ = ["router"]
