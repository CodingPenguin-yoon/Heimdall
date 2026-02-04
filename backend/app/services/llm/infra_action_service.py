"""
인프라 액션 실행 서비스 모듈 (llm 도메인)

기존 app.services.infra_action_service 모듈을
도메인 기준으로 정리하여 이 위치로 이동했습니다.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks
from pydantic import BaseModel, Field

from app.services.deployment.service import DeploymentService
from app.services.proxmox import ProxmoxService


class InfraActionType(str, Enum):
    """지원하는 인프라 액션 타입 정의"""

    LIST_VMS = "list_vms"
    LIST_NODES = "list_nodes"
    GET_VM_DETAIL = "get_vm_detail"
    CREATE_VM = "create_vm"


class InfraAction(BaseModel):
    """LLM이 제안한 액션을 백엔드에서 사용하는 표준 형태로 표현"""

    type: InfraActionType = Field(description="액션 타입")
    description: Optional[str] = Field(
        default=None,
        description="이 액션이 수행하는 작업에 대한 자연어 설명 (선택)",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="액션 실행에 필요한 파라미터 딕셔너리",
    )


class InfraActionResult(BaseModel):
    """액션 실행 결과를 프론트엔드/LLM에게 전달하기 위한 표준 응답 모델"""

    result_message: str = Field(description="사용자에게 보여줄 결과 메시지")
    raw_result: Any = Field(
        default=None,
        description="원본 결과 데이터 (리스트/딕셔너리 등, 필요 시 프론트에서 추가 처리)",
    )


class InfraActionService:
    """
    인프라 액션 실행 서비스

    - 액션 타입별로 올바른 서비스(ProxmoxService, DeploymentService 등)를 호출
    - LLM이 제안한 params 를 내부 서비스 입력 형식으로 변환
    - 사용자에게 의미 있는 result_message 를 생성
    """

    def __init__(self) -> None:
        self.proxmox_service = ProxmoxService()
        self.deployment_service = DeploymentService()

    def execute_action(
        self,
        action: InfraAction,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> InfraActionResult:
        if action.type == InfraActionType.LIST_VMS:
            return self._execute_list_vms(action)
        if action.type == InfraActionType.LIST_NODES:
            return self._execute_list_nodes(action)
        if action.type == InfraActionType.GET_VM_DETAIL:
            return self._execute_get_vm_detail(action)
        if action.type == InfraActionType.CREATE_VM:
            return self._execute_create_vm(action, background_tasks=background_tasks)

        return InfraActionResult(
            result_message=f"지원되지 않는 액션 타입입니다: {action.type}",
            raw_result={"supported_types": [t.value for t in InfraActionType]},
        )

    def _execute_list_vms(self, action: InfraAction) -> InfraActionResult:
        node = action.params.get("node")
        vms = self.proxmox_service.get_vms(node=node)

        count = len(vms)
        if node:
            header = f"노드 '{node}'에서 {count}개의 VM을 조회했습니다."
        else:
            header = f"모든 노드에서 {count}개의 VM을 조회했습니다."

        if count == 0:
            msg = header + "\n(표시할 VM이 없습니다.)"
        else:
            preview_lines = []
            for vm in vms[:5]:
                name = vm.get("name") or vm.get("vm_id") or vm.get("id") or "이름 없음"
                status = vm.get("status", "unknown")
                node_name = vm.get("node", "-")
                cpu = vm.get("cpu_cores", 0)
                mem = vm.get("memory_gb", 0)
                preview_lines.append(
                    f"- {name} (노드: {node_name}, 상태: {status}, CPU: {cpu}, 메모리: {mem}GB)"
                )

            if count > 5:
                preview_lines.append(f"... 그 외 {count - 5}개 VM 더 있음")

            msg = header + "\n\n" + "\n".join(preview_lines)

        return InfraActionResult(result_message=msg, raw_result={"vms": vms})

    def _execute_list_nodes(self, action: InfraAction) -> InfraActionResult:
        nodes = self.proxmox_service.get_nodes()
        count = len(nodes)
        msg = f"{count}개의 Proxmox 노드를 조회했습니다."
        return InfraActionResult(result_message=msg, raw_result={"nodes": nodes})

    def _execute_get_vm_detail(self, action: InfraAction) -> InfraActionResult:
        vm_id = action.params.get("vm_id") or action.params.get("id")
        if not isinstance(vm_id, str) or "/" not in vm_id:
            return InfraActionResult(
                result_message="vm_id 파라미터가 올바른 형식이 아닙니다. 예: 'pve-node/100'.",
                raw_result={"vm_id": vm_id},
            )

        node, vmid_str = vm_id.split("/", 1)
        try:
            vmid = int(vmid_str)
        except ValueError:
            return InfraActionResult(
                result_message="vm_id의 VM ID 부분이 숫자가 아닙니다.",
                raw_result={"vm_id": vm_id},
            )

        status = self.proxmox_service.get_vm_status(node=node, vmid=vmid)
        if status is None:
            msg = f"VM 상태를 조회하지 못했습니다: {vm_id}"
        else:
            msg = f"VM '{vm_id}'의 현재 상태를 조회했습니다."

        return InfraActionResult(
            result_message=msg,
            raw_result={"vm_id": vm_id, "status": status},
        )

    def _execute_create_vm(
        self,
        action: InfraAction,
        background_tasks: Optional[BackgroundTasks],
    ) -> InfraActionResult:
        if background_tasks is None:
            return InfraActionResult(
                result_message="VM 생성 액션에는 BackgroundTasks 인스턴스가 필요합니다.",
                raw_result=None,
            )

        params = action.params or {}
        deploy_request: Dict[str, Any] = {}

        if "server_name" in params:
            deploy_request["server_name"] = params["server_name"]
        if "server_id" in params:
            deploy_request["server_id"] = params["server_id"]
        if "template_id" in params:
            deploy_request["template_id"] = params["template_id"]
        if "iso_image_id" in params:
            deploy_request["iso_image_id"] = params["iso_image_id"]
        if "cpu_cores" in params:
            deploy_request["cpu_cores"] = params["cpu_cores"]
        if "memory_gb" in params:
            deploy_request["memory_gb"] = params["memory_gb"]
        if "disk_size_gb" in params:
            deploy_request["disk_size_gb"] = params["disk_size_gb"]
        if "storage_id" in params:
            deploy_request["storage_id"] = params["storage_id"]
        if "network_ids" in params:
            deploy_request["network_ids"] = params["network_ids"]

        if "ansible_packages" in params:
            deploy_request["ansible_packages"] = params["ansible_packages"]
        if "ansible_roles" in params:
            deploy_request["ansible_roles"] = params["ansible_roles"]

        task_id = self.deployment_service.start_deployment_with_request(
            background_tasks=background_tasks,
            deploy_request=deploy_request,
            skip_terraform=False,
            skip_ansible=False,
        )

        server_name = deploy_request.get("server_name") or "(이름 미지정)"
        msg = f"VM 생성 배포 작업을 시작했습니다. 이름: {server_name}, task_id: {task_id}"

        return InfraActionResult(
            result_message=msg,
            raw_result={
                "task_id": task_id,
                "deploy_request": deploy_request,
            },
        )


__all__ = [
    "InfraActionService",
    "InfraAction",
    "InfraActionResult",
    "InfraActionType",
]

