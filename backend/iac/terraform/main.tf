# Proxmox Provider 설정
# 
# 이 파일은 Proxmox 가상화 환경에 인프라를 배포하기 위한 Terraform 설정입니다.
# 환경변수를 통해 Proxmox API 인증 정보를 제공합니다.
#
# 필수 환경변수:
#   - PM_API_URL: Proxmox API URL (예: https://proxmox.example.com:8006/api2/json)
#   - PM_API_TOKEN_ID: Proxmox API Token ID (예: user@pam!token_name)
#   - PM_API_TOKEN_SECRET: Proxmox API Token Secret

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    proxmox = {
      source  = "telmate/proxmox"
      version = "~> 2.9"
    }
  }
}

# Proxmox Provider 설정
provider "proxmox" {
  pm_api_url          = var.proxmox_api_url
  pm_api_token_id     = var.proxmox_api_token_id
  pm_api_token_secret = var.proxmox_api_token_secret
  
  # TLS 검증 설정 (필요시 false로 변경)
  pm_tls_insecure = var.proxmox_tls_insecure
}

# 변수 정의
variable "proxmox_api_url" {
  description = "Proxmox API URL"
  type        = string
  # 환경변수에서 읽기: TF_VAR_proxmox_api_url 또는 export로 설정
}

variable "proxmox_api_token_id" {
  description = "Proxmox API Token ID"
  type        = string
  sensitive   = true
  # 환경변수에서 읽기: TF_VAR_proxmox_api_token_id 또는 export로 설정
}

variable "proxmox_api_token_secret" {
  description = "Proxmox API Token Secret"
  type        = string
  sensitive   = true
  # 환경변수에서 읽기: TF_VAR_proxmox_api_token_secret 또는 export로 설정
}

variable "proxmox_tls_insecure" {
  description = "Proxmox TLS 검증 비활성화 여부"
  type        = bool
  default     = false
}

# Proxmox VM 리소스 생성
# 프론트엔드에서 전달받은 변수로 VM 생성
resource "proxmox_vm_qemu" "instance" {
  # 필수 변수 확인
  count = var.vm_name != "" && var.target_node != "" ? 1 : 0
  
  name        = var.vm_name
  target_node = var.target_node
  
  # 템플릿이 있으면 클론, 없으면 새로 생성
  clone = var.template_id != "" ? var.template_id : null
  
  # VM 설정
  agent    = 1
  os_type  = "cloud-init"
  cores    = var.cpu_cores
  sockets  = 1
  cpu      = "host"
  memory   = var.memory_gb * 1024  # GB를 MB로 변환
  scsihw   = "virtio-scsi-pci"
  
  # 디스크 설정
  disk {
    slot    = 0
    storage = var.storage_id != "" ? var.storage_id : "local-lvm"
    type    = "scsi"
    size    = "${var.disk_size_gb}G"
  }
  
  # 네트워크 설정 (여러 네트워크 지원)
  dynamic "network" {
    for_each = length(var.network_ids) > 0 ? var.network_ids : ["vmbr0"]
    content {
      model  = "virtio"
      bridge = network.value
    }
  }
  
  # Cloud-init 설정 (IP 자동 할당을 위해)
  ipconfig0 = "ip=dhcp"
  
  lifecycle {
    ignore_changes = [
      network,
      disk,
    ]
  }
}

# VM IP 주소 출력
output "vm_ip" {
  description = "생성된 VM의 IP 주소"
  value       = length(proxmox_vm_qemu.instance) > 0 ? proxmox_vm_qemu.instance[0].default_ipv4_address : null
}

output "vm_id" {
  description = "생성된 VM의 ID"
  value       = length(proxmox_vm_qemu.instance) > 0 ? proxmox_vm_qemu.instance[0].vmid : null
}

output "vm_name" {
  description = "생성된 VM의 이름"
  value       = length(proxmox_vm_qemu.instance) > 0 ? proxmox_vm_qemu.instance[0].name : null
}
