"""
배포 작업 통합 서비스 모듈

이 모듈은 Terraform과 Ansible을 순차적으로 실행하여 전체 배포 프로세스를 관리합니다.
- BackgroundTasks를 활용한 비동기 배포 실행
- Terraform apply -> Ansible playbook 순차 실행
- 작업 상태 및 로그 통합 관리
"""

import uuid
import os
from fastapi import BackgroundTasks
from app.services.task_manager import task_manager, TaskStatus
from app.services.terraform_service import TerraformService
from app.services.ansible_service import AnsibleService


class DeploymentService:
    """
    배포 작업을 통합 관리하는 서비스 클래스
    
    Terraform과 Ansible을 순차적으로 실행하여 인프라 배포를 수행합니다.
    BackgroundTasks를 활용하여 비동기적으로 작업을 처리합니다.
    """
    
    def __init__(self):
        """초기화: Terraform 및 Ansible 서비스 인스턴스 생성"""
        self.terraform_service = TerraformService()
        self.ansible_service = AnsibleService()
    
    def start_deployment(
        self,
        background_tasks: BackgroundTasks,
        skip_terraform: bool = False,
        skip_ansible: bool = False
    ) -> str:
        """
        배포 작업 시작
        
        Args:
            background_tasks: FastAPI BackgroundTasks 인스턴스
            skip_terraform: Terraform 단계 건너뛰기 여부
            skip_ansible: Ansible 단계 건너뛰기 여부
            
        Returns:
            생성된 task_id
        """
        # 고유 작업 ID 생성
        task_id = str(uuid.uuid4())
        
        # 작업 초기화
        task_manager.create_task(task_id)
        task_manager.update_status(task_id, TaskStatus.PENDING)
        
        # 백그라운드 작업 등록
        background_tasks.add_task(
            self._execute_deployment,
            task_id,
            skip_terraform,
            skip_ansible,
            None  # deploy_request는 나중에 추가 가능
        )
        
        return task_id
    
    def start_deployment_with_request(
        self,
        background_tasks: BackgroundTasks,
        deploy_request: dict,
        skip_terraform: bool = False,
        skip_ansible: bool = False
    ) -> str:
        """
        배포 요청 정보와 함께 배포 작업 시작
        
        Args:
            background_tasks: FastAPI BackgroundTasks 인스턴스
            deploy_request: 배포 요청 정보 딕셔너리
            skip_terraform: Terraform 단계 건너뛰기 여부
            skip_ansible: Ansible 단계 건너뛰기 여부
            
        Returns:
            생성된 task_id
        """
        # 고유 작업 ID 생성
        task_id = str(uuid.uuid4())
        
        # 작업 초기화
        task_manager.create_task(task_id)
        task_manager.update_status(task_id, TaskStatus.PENDING)
        
        # 백그라운드 작업 등록
        background_tasks.add_task(
            self._execute_deployment,
            task_id,
            skip_terraform,
            skip_ansible,
            deploy_request
        )
        
        return task_id
    
    def _execute_deployment(
        self,
        task_id: str,
        skip_terraform: bool = False,
        skip_ansible: bool = False,
        deploy_request: dict = None
    ) -> None:
        """
        실제 배포 작업 실행 (내부 메서드)
        
        Terraform apply -> Ansible playbook 순차 실행
        
        Args:
            task_id: 작업 식별자
            skip_terraform: Terraform 단계 건너뛰기 여부
            skip_ansible: Ansible 단계 건너뛰기 여부
            deploy_request: 배포 요청 정보 (선택적)
        """
        vm_ip = None  # Terraform에서 추출한 IP 주소
        
        try:
            task_manager.update_status(task_id, TaskStatus.RUNNING)
            task_manager.append_log(task_id, "=== 배포 작업 시작 ===")
            
            # 배포 요청 정보 로깅
            if deploy_request:
                task_manager.append_log(task_id, f"배포 설정: {deploy_request}")
            
            # 1단계: Terraform Init
            if not skip_terraform:
                task_manager.append_log(task_id, "\n[1/4] Terraform Init 실행 중...")
                success, error = self.terraform_service.init(task_id)
                if not success:
                    task_manager.update_status(task_id, TaskStatus.FAILED)
                    task_manager.append_log(task_id, f"Terraform Init 실패: {error}")
                    return
                
                # 2단계: Terraform Plan (선택적)
                task_manager.append_log(task_id, "\n[2/4] Terraform Plan 실행 중...")
                success, error = self.terraform_service.plan(task_id)
                if not success:
                    task_manager.append_log(task_id, f"Terraform Plan 경고: {error}")
                    # Plan 실패는 치명적이지 않을 수 있으므로 계속 진행
                
                # 3단계: Terraform Apply (프론트엔드 입력값을 변수로 전달)
                task_manager.append_log(task_id, "\n[3/4] Terraform Apply 실행 중...")
                
                # 프론트엔드 입력값을 Terraform 변수로 변환
                terraform_vars = {}
                if deploy_request:
                    # VM 이름
                    if deploy_request.get("server_name"):
                        terraform_vars["vm_name"] = deploy_request["server_name"]
                    
                    # 타겟 노드 (서버)
                    if deploy_request.get("server_id"):
                        terraform_vars["target_node"] = deploy_request["server_id"]
                    
                    # 템플릿 ID (형식: node/template-vmid)
                    if deploy_request.get("template_id"):
                        # template_id가 이미 "node/vmid" 형식인지 확인
                        if "/" in str(deploy_request["template_id"]):
                            terraform_vars["template_id"] = deploy_request["template_id"]
                        else:
                            # template_id만 있으면 노드와 조합 필요 (나중에 개선 가능)
                            terraform_vars["template_id"] = deploy_request["template_id"]
                    
                    # CPU 코어
                    if deploy_request.get("cpu_cores"):
                        terraform_vars["cpu_cores"] = int(deploy_request["cpu_cores"])
                    
                    # 메모리 (GB)
                    if deploy_request.get("memory_gb"):
                        terraform_vars["memory_gb"] = int(deploy_request["memory_gb"])
                    
                    # 디스크 크기 (기본값 50GB)
                    terraform_vars["disk_size_gb"] = deploy_request.get("disk_size_gb", 50)
                    
                    # 스토리지
                    if deploy_request.get("storage_id"):
                        terraform_vars["storage_id"] = deploy_request["storage_id"]
                    
                    # 네트워크 (리스트)
                    if deploy_request.get("network_ids"):
                        terraform_vars["network_ids"] = deploy_request["network_ids"]
                    
                    task_manager.append_log(task_id, f"Terraform 변수: {terraform_vars}")
                
                success, error = self.terraform_service.apply(
                    task_id, 
                    auto_approve=True,
                    variables=terraform_vars if terraform_vars else None
                )
                if not success:
                    task_manager.update_status(task_id, TaskStatus.FAILED)
                    task_manager.append_log(task_id, f"Terraform Apply 실패: {error}")
                    return
                
                task_manager.append_log(task_id, "Terraform Apply 완료")
                
                # Terraform Output에서 IP 주소 추출
                task_manager.append_log(task_id, "Terraform Output에서 IP 주소 추출 중...")
                terraform_outputs = self.terraform_service.get_output()
                task_manager.append_log(task_id, f"Terraform Outputs: {terraform_outputs}")
                
                # IP 주소 추출 (vm_ip, instance_ip, ip_address 등 다양한 키 이름 지원)
                vm_ip = None
                for key in ["vm_ip", "instance_ip", "ip_address", "ip", "default_ipv4_address"]:
                    if key in terraform_outputs:
                        vm_ip = terraform_outputs[key]
                        break
                
                # Output이 딕셔너리인 경우 value 추출
                if vm_ip and isinstance(vm_ip, dict):
                    vm_ip = vm_ip.get("value", vm_ip)
                
                if vm_ip:
                    task_manager.append_log(task_id, f"추출된 IP 주소: {vm_ip}")
                else:
                    task_manager.append_log(task_id, "경고: Terraform Output에서 IP 주소를 찾을 수 없습니다.")
            else:
                task_manager.append_log(task_id, "Terraform 단계 건너뛰기")
            
            # 4단계: Ansible Playbook 실행
            if not skip_ansible:
                task_manager.append_log(task_id, "\n[4/4] Ansible Playbook 실행 중...")
                
                # Inventory 호스트 정보 준비 (Terraform에서 추출한 IP 사용)
                inventory_hosts = None
                if not skip_terraform and vm_ip:
                    inventory_hosts = [{
                        "name": "proxmox_vm",
                        "ip": str(vm_ip),
                        "user": os.getenv("ANSIBLE_SSH_USER", "root")
                    }]
                    task_manager.append_log(task_id, f"Ansible Inventory에 IP {vm_ip} 추가")
                
                # Ansible extra_vars 준비 (선택한 패키지 및 역할)
                extra_vars = {}
                if deploy_request:
                    packages = deploy_request.get("ansible_packages", [])
                    roles = deploy_request.get("ansible_roles", [])
                    
                    if packages:
                        extra_vars["packages_to_install"] = packages
                        task_manager.append_log(task_id, f"설치할 패키지: {', '.join(packages)}")
                    
                    if roles:
                        extra_vars["roles_to_apply"] = roles
                        task_manager.append_log(task_id, f"적용할 역할: {', '.join(roles)}")
                
                success, error = self.ansible_service.run_playbook(
                    playbook_file="playbook.yml",
                    task_id=task_id,
                    inventory_hosts=inventory_hosts,
                    extra_vars=extra_vars if extra_vars else None
                )
                if not success:
                    task_manager.update_status(task_id, TaskStatus.FAILED)
                    task_manager.append_log(task_id, f"Ansible Playbook 실행 실패: {error}")
                    return
                
                task_manager.append_log(task_id, "Ansible Playbook 실행 완료")
            else:
                task_manager.append_log(task_id, "Ansible 단계 건너뛰기")
            
            # 배포 성공
            task_manager.update_status(task_id, TaskStatus.SUCCESS)
            task_manager.append_log(task_id, "\n=== 배포 작업 완료 ===")
            
        except Exception as e:
            # 예외 발생 시 실패 처리
            error_msg = f"배포 작업 중 예외 발생: {str(e)}"
            task_manager.update_status(task_id, TaskStatus.FAILED)
            task_manager.append_log(task_id, f"EXCEPTION: {error_msg}")
