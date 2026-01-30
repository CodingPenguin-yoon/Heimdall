# Terraform 변수 정의 파일
#
# 이 파일은 Proxmox Provider와 리소스 생성을 위한 변수들을 정의합니다.
# 환경변수나 terraform.tfvars 파일을 통해 값을 제공할 수 있습니다.

# Proxmox 연결 정보는 main.tf에 정의되어 있습니다.

# VM 생성 변수 (프론트엔드에서 전달받음)
variable "vm_name" {
  description = "생성할 VM 이름"
  type        = string
  default     = ""
}

variable "target_node" {
  description = "VM을 생성할 Proxmox 노드 (서버)"
  type        = string
  default     = ""
}

variable "template_id" {
  description = "클론할 템플릿 ID (형식: node/template-vmid, 예: pve-node-01/100)"
  type        = string
  default     = ""
}

variable "cpu_cores" {
  description = "VM CPU 코어 수"
  type        = number
  default     = 2
}

variable "memory_gb" {
  description = "VM 메모리 크기 (GB)"
  type        = number
  default     = 4
}

variable "disk_size_gb" {
  description = "디스크 크기 (GB)"
  type        = number
  default     = 50
}

variable "storage_id" {
  description = "스토리지 ID"
  type        = string
  default     = ""
}

variable "network_ids" {
  description = "네트워크 ID 리스트 (예: [\"vmbr0\", \"vmbr1\"])"
  type        = list(string)
  default     = []
}

# 템플릿 없이 VM 생성 시 사용할 ISO 이미지 (선택사항)
variable "iso_file" {
  description = "ISO 이미지 파일 경로 (템플릿 없이 VM 생성 시 사용, 예: local:iso/ubuntu-22.04-server-amd64.iso)"
  type        = string
  default     = ""
}

# Cloud-init 사용자 데이터 (선택사항)
variable "cloudinit_user_data" {
  description = "Cloud-init user-data (템플릿 없이 VM 생성 시 OS 설정용)"
  type        = string
  default     = ""
}
