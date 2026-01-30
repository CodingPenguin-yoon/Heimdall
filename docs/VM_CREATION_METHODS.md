# VM 생성 방법 가이드

Proxmox에서 Terraform으로 VM을 생성하는 방법은 크게 두 가지가 있습니다.

## 1. 템플릿에서 클론 (권장)

가장 일반적이고 빠른 방법입니다. 미리 준비된 템플릿에서 VM을 복제합니다.

### 장점
- ✅ 빠른 생성 (클론만 하면 됨)
- ✅ 일관된 설정 보장
- ✅ OS 설치 불필요
- ✅ Cloud-init으로 즉시 사용 가능

### 사용 방법

```hcl
# Terraform 변수
template_id = "pve-node-01/100"  # node/vmid 형식
```

프론트엔드에서:
- Step 2에서 템플릿 선택
- 템플릿이 선택되면 자동으로 클론 방식 사용

### 템플릿 준비 방법

1. Proxmox 웹 UI에서 VM 생성
2. OS 설치 및 기본 설정
3. Cloud-init 설정 (선택사항)
4. VM을 템플릿으로 변환:
   ```bash
   # Proxmox 웹 UI: VM > More > Convert to Template
   # 또는 CLI:
   qm template <vmid>
   ```

## 2. 템플릿 없이 생성

템플릿이 없을 때 사용하는 방법입니다. 두 가지 방식이 있습니다.

### 2-1. ISO 이미지에서 설치

ISO 이미지를 사용하여 VM을 생성하고 OS를 설치합니다.

#### 장점
- ✅ 템플릿 없이도 VM 생성 가능
- ✅ 최신 OS 이미지 사용 가능
- ✅ 커스텀 OS 설치 가능

#### 단점
- ❌ OS 설치 시간 필요 (수동 또는 자동화 필요)
- ❌ 템플릿 방식보다 느림

#### 사용 방법

**1. ISO 이미지 업로드**

Proxmox에 ISO 이미지를 업로드합니다:

```bash
# Proxmox 웹 UI: Datacenter > Storage > local > Content > ISO Images > Upload
# 또는 CLI:
scp ubuntu-22.04-server-amd64.iso root@proxmox-server:/var/lib/vz/template/iso/
```

**2. Terraform 변수 설정**

```hcl
# 템플릿 ID는 비워둠
template_id = ""

# ISO 이미지 경로 설정
iso_file = "local:iso/ubuntu-22.04-server-amd64.iso"
# 형식: storage:path/to/file.iso
```

**3. VM 생성**

```bash
terraform apply
```

**4. OS 설치**

VM이 생성되면:
- VNC 콘솔로 접속하여 OS 설치 진행
- 또는 자동화 스크립트 사용 (preseed/kickstart)

### 2-2. Cloud-init 이미지 사용

Cloud-init을 지원하는 OS 이미지를 직접 사용합니다.

#### 장점
- ✅ 자동화된 OS 설치
- ✅ Cloud-init으로 초기 설정 자동화
- ✅ 템플릿보다 유연함

#### 단점
- ❌ Cloud-init 지원 이미지 필요
- ❌ 설정이 복잡할 수 있음

#### 사용 방법

**1. Cloud-init 이미지 준비**

Proxmox가 지원하는 Cloud-init 이미지 형식:
- QCOW2 이미지
- VMDK 이미지

**2. Terraform 설정**

```hcl
template_id = ""  # 템플릿 없음
iso_file = ""     # ISO 없음
os_type = "cloud-init"

# Cloud-init user-data 설정
cloudinit_user_data = <<-EOF
  #cloud-config
  users:
    - name: admin
      ssh-authorized-keys:
        - ssh-rsa AAAAB3NzaC1yc2E...
  packages:
    - curl
    - git
EOF
```

## 현재 프로젝트 구현 상태

### 템플릿 방식 (완료)
- ✅ 프론트엔드에서 템플릿 선택 가능
- ✅ Terraform에서 자동으로 클론

### 템플릿 없이 생성 (부분 구현)
- ✅ ISO 이미지 지원 (변수 추가됨)
- ⚠️ 프론트엔드에서 ISO 선택 UI 미구현
- ⚠️ Cloud-init user-data 입력 UI 미구현

## 권장 사항

### 프로덕션 환경
- **템플릿 방식 사용 권장**
  - 빠르고 일관된 VM 생성
  - 표준화된 설정 보장

### 개발/테스트 환경
- **ISO 방식 사용 가능**
  - 다양한 OS 테스트
  - 최신 이미지 사용

### 자동화가 필요한 경우
- **Cloud-init 이미지 사용**
  - 완전 자동화된 설치
  - 설정 스크립트 통합

## 예제: 템플릿 없이 Ubuntu VM 생성

```hcl
# variables.tf
variable "iso_file" {
  description = "ISO 이미지 경로"
  type        = string
  default     = "local:iso/ubuntu-22.04-server-amd64.iso"
}

# main.tf
resource "proxmox_vm_qemu" "instance" {
  name        = "ubuntu-vm"
  target_node = "pve-node-01"
  
  # 템플릿 없이 생성
  clone = null
  
  # ISO 이미지 사용
  iso = var.iso_file
  
  # VM 설정
  cores  = 2
  memory = 4096
  # ... 기타 설정
}
```

## 문제 해결

### ISO 이미지가 인식되지 않음
- ISO 파일 경로 확인: `storage:path/to/file.iso` 형식
- 스토리지 이름 확인: Proxmox 웹 UI에서 확인
- 파일 권한 확인: Proxmox 서버에서 읽기 가능한지 확인

### Cloud-init이 작동하지 않음
- `os_type = "cloud-init"` 설정 확인
- Cloud-init 이미지인지 확인
- user-data 형식 확인 (YAML 형식)

### VM이 부팅되지 않음
- 부팅 순서 확인: ISO가 첫 번째인지 확인
- 네트워크 설정 확인: DHCP 또는 정적 IP 설정
- VNC 콘솔로 직접 확인
