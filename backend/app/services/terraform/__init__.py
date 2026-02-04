"""
Terraform 실행 서비스 패키지

이 패키지는 Terraform 명령어를 OS 레벨에서 실행하고 결과를 관리합니다.
기존 단일 모듈이었던 `terraform_service.py`의 구현을 패키지 구조로 옮겼습니다.
"""

import subprocess
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from app.services.task.manager import task_manager, TaskStatus

# .env 파일 로드
# 패키지로 이동하면서 경로 깊이가 1단계 늘어났기 때문에
# 항상 프로젝트 루트(backend 기준 한 단계 위)의 .env 를 바라보도록 조정한다.
project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"[TerraformService] .env 파일 로드됨: {env_path}")


class TerraformService:
    """
    Terraform 명령어 실행을 담당하는 서비스 클래스
    
    /iac/terraform 디렉토리 내의 Terraform 파일들을 대상으로
    terraform init, plan, apply 등의 명령어를 실행합니다.
    """
    
    def __init__(self, terraform_dir: Optional[str] = None):
        """
        초기화
        
        Args:
            terraform_dir: Terraform 작업 디렉토리 경로 (기본값: 프로젝트 루트/iac/terraform)
        """
        if terraform_dir:
            self.terraform_dir = Path(terraform_dir)
        else:
            # 프로젝트 루트 기준으로 iac/terraform 경로 설정
            project_root = Path(__file__).parent.parent.parent
            self.terraform_dir = project_root / "iac" / "terraform"
        
        # 디렉토리 존재 여부 확인
        if not self.terraform_dir.exists():
            self.terraform_dir.mkdir(parents=True, exist_ok=True)

        # ------------------------------------------------------------------
        # Proxmox 관련 환경변수를 Terraform 변수(TF_VAR_*)로 연결
        # .env 에서는 PROXMOX_* 이름을 쓰고, Terraform은 TF_VAR_proxmox_* 를 기대하므로
        # 여기서 한 번만 매핑해 두면 이후 subprocess 에서 그대로 사용 가능하다.
        # ------------------------------------------------------------------
        proxmox_api_url = os.getenv("PROXMOX_API_URL")
        if proxmox_api_url and not os.getenv("TF_VAR_proxmox_api_url"):
            os.environ["TF_VAR_proxmox_api_url"] = proxmox_api_url

        proxmox_token_id = os.getenv("PROXMOX_API_TOKEN_ID")
        if proxmox_token_id and not os.getenv("TF_VAR_proxmox_api_token_id"):
            os.environ["TF_VAR_proxmox_api_token_id"] = proxmox_token_id

        proxmox_token_secret = os.getenv("PROXMOX_API_TOKEN_SECRET")
        if proxmox_token_secret and not os.getenv("TF_VAR_proxmox_api_token_secret"):
            os.environ["TF_VAR_proxmox_api_token_secret"] = proxmox_token_secret

        proxmox_tls_insecure = os.getenv("PROXMOX_TLS_INSECURE")
        if proxmox_tls_insecure is not None and not os.getenv("TF_VAR_proxmox_tls_insecure"):
            # 문자열(true/false)를 Terraform 이 이해할 수 있는 bool 값으로 넘긴다.
            value = str(proxmox_tls_insecure).strip().lower() in ["1", "true", "yes", "on"]
            os.environ["TF_VAR_proxmox_tls_insecure"] = "true" if value else "false"

        # 디버깅: 환경변수 확인
        print(f"[TerraformService] TF_VAR_proxmox_api_url: {os.getenv('TF_VAR_proxmox_api_url', 'NOT SET')}")
        print(f"[TerraformService] TF_VAR_proxmox_api_token_id: {os.getenv('TF_VAR_proxmox_api_token_id', 'NOT SET')}")
        print(f"[TerraformService] TF_VAR_proxmox_api_token_secret: {'SET' if os.getenv('TF_VAR_proxmox_api_token_secret') else 'NOT SET'}")
    
    def _run_command(
        self,
        command: list,
        task_id: str,
        cwd: Optional[Path] = None
    ) -> tuple[bool, str]:
        """
        Terraform 명령어 실행 (내부 메서드)
        
        Args:
            command: 실행할 명령어 리스트 (예: ['terraform', 'init'])
            task_id: 작업 식별자 (로그 및 상태 추적용)
            cwd: 작업 디렉토리 (기본값: self.terraform_dir)
            
        Returns:
            (성공 여부, 에러 메시지) 튜플
        """
        if cwd is None:
            cwd = self.terraform_dir
        
        try:
            task_manager.append_log(task_id, f"실행 명령어: {' '.join(command)}")
            task_manager.append_log(task_id, f"작업 디렉토리: {cwd}")
            
            # 현재 환경변수를 상속받아 subprocess 실행
            # Terraform은 TF_VAR_ 접두사를 가진 환경변수를 자동으로 읽습니다
            env = os.environ.copy()
            
            # subprocess로 명령어 실행 (실시간 로그 스트리밍)
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env
            )
            
            # 실시간 로그 수집
            for line in iter(process.stdout.readline, ''):
                if line:
                    task_manager.append_log(task_id, line.strip())
            
            process.wait()
            
            if process.returncode == 0:
                return True, ""
            else:
                error_msg = f"명령어 실행 실패 (종료 코드: {process.returncode})"
                task_manager.append_log(task_id, f"ERROR: {error_msg}")
                return False, error_msg
                
        except Exception as e:
            error_msg = f"명령어 실행 중 예외 발생: {str(e)}"
            task_manager.append_log(task_id, f"EXCEPTION: {error_msg}")
            return False, error_msg
    
    def init(self, task_id: str) -> tuple[bool, str]:
        """
        terraform init 실행
        
        Args:
            task_id: 작업 식별자
            
        Returns:
            (성공 여부, 에러 메시지) 튜플
        """
        task_manager.append_log(task_id, "=== Terraform Init 시작 ===")
        return self._run_command(["terraform", "init"], task_id)
    
    def plan(self, task_id: str) -> tuple[bool, str]:
        """
        terraform plan 실행
        
        Args:
            task_id: 작업 식별자
            
        Returns:
            (성공 여부, 에러 메시지) 튜플
        """
        task_manager.append_log(task_id, "=== Terraform Plan 시작 ===")
        return self._run_command(["terraform", "plan", "-input=false"], task_id)
    
    def apply(
        self, 
        task_id: str, 
        auto_approve: bool = True,
        variables: Optional[dict] = None
    ) -> tuple[bool, str]:
        """
        terraform apply 실행
        
        Args:
            task_id: 작업 식별자
            auto_approve: 자동 승인 여부 (기본값: True)
            variables: Terraform 변수 딕셔너리 (예: {"vm_name": "test-vm", "cpu_cores": 2})
            
        Returns:
            (성공 여부, 에러 메시지) 튜플
        """
        task_manager.append_log(task_id, "=== Terraform Apply 시작 ===")
        command = ["terraform", "apply", "-input=false"]
        if auto_approve:
            command.append("-auto-approve")
        
        # 변수 추가 (-var 옵션)
        if variables:
            for key, value in variables.items():
                if value is not None:
                    # 리스트는 JSON 문자열로 변환
                    if isinstance(value, list):
                        import json
                        command.extend(["-var", f"{key}={json.dumps(value)}"])
                    else:
                        command.extend(["-var", f"{key}={value}"])
        
        return self._run_command(command, task_id)
    
    def destroy(self, task_id: str, auto_approve: bool = True) -> tuple[bool, str]:
        """
        terraform destroy 실행 (인프라 삭제)
        
        Args:
            task_id: 작업 식별자
            auto_approve: 자동 승인 여부 (기본값: True)
            
        Returns:
            (성공 여부, 에러 메시지) 튜플
        """
        task_manager.append_log(task_id, "=== Terraform Destroy 시작 ===")
        command = ["terraform", "destroy"]
        if auto_approve:
            command.append("-auto-approve")
        
        return self._run_command(command, task_id)
    
    def get_output(self, output_name: str = None) -> dict:
        """
        Terraform output 값 조회
        
        Args:
            output_name: 조회할 output 이름 (None이면 모든 output 반환)
            
        Returns:
            output 값 딕셔너리
        """
        try:
            import json
            command = ["terraform", "output", "-json"]
            if output_name:
                command.append(output_name)
            
            result = subprocess.run(
                command,
                cwd=str(self.terraform_dir),
                capture_output=True,
                text=True,
                env=os.environ.copy()
            )
            
            if result.returncode == 0:
                outputs = json.loads(result.stdout)
                # Terraform output -json 형식 변환
                if output_name:
                    # 단일 output인 경우
                    if isinstance(outputs, dict) and "value" in outputs:
                        return {output_name: outputs["value"]}
                    return {output_name: outputs}
                else:
                    # 모든 output인 경우
                    parsed = {}
                    for key, value in outputs.items():
                        if isinstance(value, dict) and "value" in value:
                            parsed[key] = value["value"]
                        else:
                            parsed[key] = value
                    return parsed
            else:
                return {}
        except Exception as e:
            return {}

