# 변수 정의 파일 (Helm의 values.yaml 스키마 역할)

# ============================================
# Proxmox 접속 정보
# ============================================
# 환경변수로 설정 가능 (TF_VAR_ 접두사 사용)
# 예: export TF_VAR_proxmox_api_url="https://192.168.2.11:8006/api2/json"
# 또는 terraform.tfvars에서 설정
variable "proxmox_api_url" {
  description = "Proxmox API URL"
  type        = string
  default     = ""  # 환경변수나 terraform.tfvars에서 설정
}

variable "proxmox_token_id" {
  description = "Proxmox API Token ID"
  type        = string
  default     = ""  # 환경변수나 terraform.tfvars에서 설정
}

variable "proxmox_token_secret" {
  description = "Proxmox API Token Secret"
  type        = string
  sensitive   = true
  default     = ""  # 환경변수나 terraform.tfvars에서 설정
}

# ============================================
# SSH 키 경로 설정
# ============================================
variable "ssh_public_key_path" {
  description = "SSH 공개키 파일 경로 (terraform.tfvars에서 설정)"
  type        = string
  default     = ""  # terraform.tfvars에서 설정
}

# ============================================
# 공통 설정 (모든 VM에 공통으로 적용)
# ============================================
variable "common_settings" {
  description = "모든 VM에 공통으로 적용되는 설정 (terraform.tfvars에서 정의)"
  type = object({
    template        = string  # 템플릿 이름
    target_node     = string  # Proxmox 노드 이름
    disk_storage    = string  # 디스크 스토리지
    network_bridge  = string  # 네트워크 브릿지
    nameserver      = string  # DNS 서버
    gateway         = string  # 게이트웨이
    cpu_sockets     = number  # CPU 소켓 수
    cpu_type        = string  # CPU 타입
    clone_wait      = number  # 클론 대기 시간
    ci_wait         = number  # Cloud-init 대기 시간
    boot_order      = string  # 부팅 순서
  })
  # 기본값 제거: terraform.tfvars에서 반드시 정의해야 함
}

# ============================================
# VM 목록 (핵심 변수)
# ============================================
variable "vms" {
  description = "생성할 VM 목록 (Helm의 values.yaml처럼 여기서 관리)"
  type = map(object({
    # VM별 고유 설정
    name      = string  # VM 이름
    cores     = number  # CPU 코어 수
    memory    = number  # 메모리 (MB)
    disk_size = number  # 디스크 크기 (GB)
    ip        = string  # IP 주소 (CIDR 없이, 예: "192.168.2.98")
    
    # 선택적 설정 (공통 설정을 덮어쓸 수 있음)
    template     = optional(string)  # 템플릿 이름 (공통 설정 덮어쓰기)
    target_node  = optional(string)  # 노드 이름 (공통 설정 덮어쓰기)
    disk_storage = optional(string)  # 스토리지 (공통 설정 덮어쓰기)
    
    # Cloud-init 사용자 설정 (선택사항)
    ciuser     = optional(string)  # 사용자 이름
    cipassword = optional(string)  # 비밀번호 (sensitive)
    sshkeys    = optional(string)  # SSH 공개키
  }))
  
  # 기본값: 빈 맵 (terraform.tfvars에서 채워짐)
  default = {}
}

