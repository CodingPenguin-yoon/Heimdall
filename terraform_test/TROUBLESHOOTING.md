# Terraform Proxmox Provider 문제 해결 가이드

## 개요
이 문서는 Terraform을 사용하여 Proxmox VE 9.x에서 VM을 생성하는 과정에서 발생한 문제들과 해결 방법을 정리한 것입니다.

**환경:**
- Proxmox VE: 9.x
- Terraform Provider: `telmate/proxmox` 3.0.2-rc04
- OS: Ubuntu (템플릿)

---

## 문제 1: Provider Source 및 버전 오류

### 증상
```bash
Error: Failed to query available provider packages...
provider registry registry.terraform.io does not have a provider named 
registry.terraform.io/proxmox/proxmox
```

### 원인
- 잘못된 provider source 사용: `Proxmox/proxmox` (존재하지 않음)
- 오래된 provider 버전: `~> 0.45.0`

### 해결 방법
```hcl
# provider.tf
terraform {
  required_providers {
    proxmox = {
      source  = "telmate/proxmox"  # 올바른 provider source
      version = "~> 2.9.0"         # 최신 안정 버전
    }
  }
}
```

**핵심 포인트:**
- Proxmox Terraform Provider의 공식 source는 `telmate/proxmox`입니다
- `Proxmox/proxmox`는 존재하지 않는 provider입니다

---

## 문제 2: Proxmox 9.x 권한 오류

### 증상
```bash
Error: permissions for user/token root@pam are not sufficient, 
please provide also the following permissions that are missing: [VM.Monitor]
```

### 원인
- **Proxmox 9.x에서 권한 시스템이 변경됨**
- `VM.Monitor` 권한이 Proxmox 9.x에서 제거되고 `Sys.Audit`로 대체됨
- Provider 버전 2.9.14는 여전히 구버전 권한(`VM.Monitor`)을 체크함

### 해결 방법

#### 1단계: Proxmox에서 권한 확인
- Proxmox 웹 UI에서 API Token에 다음 권한이 있는지 확인:
  - `Sys.Audit` (Proxmox 9.x에서 필수)
  - `Administrator` 역할 (또는 필요한 모든 권한)

#### 2단계: Provider 버전 업그레이드
```hcl
# provider.tf
terraform {
  required_providers {
    proxmox = {
      source  = "telmate/proxmox"
      version = "3.0.2-rc04"  # Proxmox 9.x 호환 버전
    }
  }
}
```

**핵심 포인트:**
- Proxmox 9.x는 권한 시스템이 변경되어 provider 3.0 이상이 필요합니다
- `3.0.2-rc04`는 `VM.Monitor` 문제를 해결한 특정 버전입니다
- 안정 버전(`~> 3.0.0`)은 아직 릴리즈되지 않았을 수 있습니다

**명령어:**
```bash
terraform init -upgrade
```

---

## 문제 3: Provider 3.0 형식 변경

### 증상
```bash
Error: Missing required argument
The argument "slot" is required...
The argument "id" is required...
```

그리고 이후:
```bash
Error: type must be one of 'disk', 'cdrom', 'cloudinit', 'ignore'
Error: slot must be one of 'ide0', 'ide1', 'ide2', 'sata0', ..., 'scsi0', ..., 'virtio0', ...
```

### 원인
**Provider 3.0에서 디스크 및 네트워크 블록 형식이 완전히 변경됨**

#### Provider 2.x 형식 (구버전)
```hcl
disk {
  type    = "scsi"
  slot    = 0
  size    = "50G"
  storage = "local-lvm"
}

network {
  model  = "virtio"
  bridge = "vmbr0"
}
```

#### Provider 3.0 형식 (신버전)
```hcl
disks {
  scsi {
    scsi0 {
      disk {
        size    = 50
        storage = "local-lvm"
      }
    }
  }
}

network {
  id     = 0      # 필수 인자 추가
  model  = "virtio"
  bridge = "vmbr0"
}
```

### 해결 방법

#### 디스크 블록 변경
```hcl
# ❌ 구버전 (Provider 2.x)
disk {
  type    = "scsi"
  slot    = 0
  size    = "50G"
  storage = "local-lvm"
}

# ✅ 신버전 (Provider 3.0)
disks {
  scsi {
    scsi0 {  # 슬롯을 문자열로: "scsi0", "virtio0" 등
      disk {
        size    = 50  # 숫자로 (GB 단위)
        storage = "local-lvm"
      }
    }
  }
}
```

#### 네트워크 블록 변경
```hcl
# ❌ 구버전
network {
  model  = "virtio"
  bridge = "vmbr0"
}

# ✅ 신버전
network {
  id     = 0  # 필수 인자 추가
  model  = "virtio"
  bridge = "vmbr0"
}
```

#### CPU 설정 변경
```hcl
# ❌ 구버전
cores = 2

# ✅ 신버전
cpu {
  cores = 2
}
```

**핵심 포인트:**
- `slot`은 이제 문자열 형식: `"scsi0"`, `"virtio0"`, `"ide0"` 등
- `type`은 `"scsi"`가 아닌 `"disk"`로 변경 (또는 `disks` 블록 내에서 슬롯 타입으로 구분)
- `size`는 문자열(`"50G"`)이 아닌 숫자(`50`)로 지정
- `network` 블록에 `id` 필수 인자 추가

---

## 문제 4: Cloud-init IP 설정이 적용되지 않음

### 증상
- VM은 정상적으로 생성됨
- 하지만 설정한 고정 IP(`192.168.2.79`)가 아닌 DHCP로 할당된 IP(`192.168.2.244`)가 할당됨

### 원인
1. Cloud-init 설정이 불완전함
2. Cloud-init이 완료되기 전에 IP를 확인함
3. `os_type`이 설정되지 않음
4. Cloud-init 드라이브가 제대로 마운트되지 않음

### 해결 방법

#### 1단계: Cloud-init 필수 설정 추가
```hcl
resource "proxmox_vm_qemu" "test_vm" {
  # ... 기타 설정 ...
  
  # OS 타입 설정 (Cloud-init 사용 시 필수)
  os_type = "cloud-init"
  
  # Cloud-init 사용자 설정
  ciuser     = "root"
  cipassword = "dbsghtjqj1081"
  
  # Cloud-init 네트워크 설정
  ipconfig0 = "ip=192.168.2.79/24,gw=192.168.2.1"
  nameserver = "192.168.2.1"
  
  # Cloud-init 완료 대기 시간
  ci_wait = 30
  
  # 자동 재부팅 (Cloud-init 설정 적용)
  automatic_reboot = true
  
  # Guest Agent 활성화
  agent = 1
}
```

#### 2단계: Cloud-init 드라이브 추가 (Provider 3.0 형식)
```hcl
disks {
  # Cloud-init 드라이브 (ide3 슬롯 사용 - 공식 예제 기준)
  ide {
    ide3 {
      cloudinit {
        storage = "server3-storage"
      }
    }
  }
  
  # 데이터 디스크
  scsi {
    scsi0 {
      disk {
        size    = 50
        storage = "server3-storage"
      }
    }
  }
}
```

**핵심 포인트:**
- `os_type = "cloud-init"` 필수
- `ci_wait`로 Cloud-init 완료 대기 시간 확보
- `automatic_reboot = true`로 Cloud-init 설정 적용 보장
- Cloud-init 드라이브를 `ide3` 슬롯에 명시적으로 추가
- `ipconfig0` 형식: `"ip=192.168.2.79/24,gw=192.168.2.1"`

**참고:**
- 공식 예제: https://github.com/Telmate/terraform-provider-proxmox/blob/master/docs/examples/cloudinit_example.tf

---

## 문제 5: VM 부팅 실패 (Bootable Disk 오류)

### 증상
```
BIOS (version rel-1.17.0-0-gb52ca86e094d-prebuilt.qemu.org)
Boot failed: not a bootable disk
No bootable device found. Retrying in 1 seconds.
```

### 원인
1. **템플릿의 원래 부팅 디스크 슬롯과 불일치**
   - 템플릿이 `scsi0`에서 부팅하도록 설정되어 있음
   - 하지만 `virtio0`으로 디스크를 새로 생성하고 `boot = "order=virtio0"`으로 설정함
   - 클론된 디스크는 템플릿의 원래 위치(`scsi0`)에 있지만, 부팅 순서는 `virtio0`을 가리킴

2. **Provider 3.0에서 `disks` 블록 사용 시 템플릿의 원래 디스크를 명시적으로 정의해야 함**
   - 클론 시 템플릿의 디스크가 자동으로 복제되지만
   - `disks` 블록을 사용하면 모든 디스크를 명시적으로 정의해야 함

### 해결 방법

#### 1단계: 템플릿의 원래 디스크 슬롯 확인
- Proxmox 웹 UI에서 템플릿 VM의 하드웨어 설정 확인
- 일반적으로 Ubuntu 템플릿은 `scsi0`을 사용

#### 2단계: 템플릿의 원래 디스크를 명시적으로 정의
```hcl
disks {
  # Cloud-init 드라이브
  ide {
    ide3 {
      cloudinit {
        storage = "server3-storage"
      }
    }
  }
  
  # 템플릿의 원래 디스크 (클론 시 자동으로 복제되지만 명시적으로 정의)
  scsi {
    scsi0 {
      disk {
        size    = 50  # 템플릿의 디스크 크기와 동일하게 설정
        storage = "server3-storage"
      }
    }
  }
}
```

#### 3단계: 부팅 순서를 템플릿의 원래 디스크로 설정
```hcl
# 템플릿이 scsi0에서 부팅하도록 설정되어 있다면
boot = "order=scsi0"
```

**핵심 포인트:**
- 클론 시 템플릿의 디스크는 원래 슬롯(`scsi0`)에 복제됨
- `disks` 블록을 사용할 때는 템플릿의 원래 디스크도 명시적으로 정의해야 함
- 부팅 순서(`boot`)는 템플릿의 원래 부팅 디스크 슬롯과 일치해야 함
- 템플릿이 다른 슬롯(`virtio0`, `sata0` 등)을 사용한다면 해당 슬롯으로 변경

**템플릿 디스크 슬롯 확인 방법:**
1. Proxmox 웹 UI에서 템플릿 VM 선택
2. 하드웨어(Hardware) 탭 확인
3. Hard Disk 항목의 Bus/Device 확인 (예: `scsi0`, `virtio0`)

---

## 최종 작동하는 설정

### provider.tf
```hcl
terraform {
  required_providers {
    proxmox = {
      source  = "telmate/proxmox"
      version = "3.0.2-rc04"
    }
  }
}

provider "proxmox" {
  pm_api_url          = "https://192.168.2.11:8006/api2/json"
  pm_api_token_id     = "root@pam!terraform-admin"
  pm_api_token_secret = "69d75d7e-620a-4b97-8d1e-db36d66fed84"
  pm_tls_insecure     = true
  pm_debug            = true
}
```

### main.tf
```hcl
resource "proxmox_vm_qemu" "test_vm" {
  name        = "testvm"
  target_node = "yoonserver3"
  clone       = "ubutu-temp"
  clone_wait  = 10
  os_type     = "cloud-init"

  cpu {
    cores = 2
  }
  memory = 4096

  disks {
    # Cloud-init 드라이브
    ide {
      ide3 {
        cloudinit {
          storage = "server3-storage"
        }
      }
    }
    
    # 템플릿의 원래 디스크
    scsi {
      scsi0 {
        disk {
          size    = 50
          storage = "server3-storage"
        }
      }
    }
  }

  network {
    id     = 0
    model  = "virtio"
    bridge = "vmbr0"
  }

  # Cloud-init 설정
  ciuser     = "root"
  cipassword = "dbsghtjqj1081"
  ipconfig0  = "ip=192.168.2.80/24,gw=192.168.2.1"
  nameserver = "192.168.2.1"
  ci_wait    = 30
  agent      = 1
  automatic_reboot = true
  
  # 부팅 순서 (템플릿의 원래 디스크 슬롯과 일치)
  boot = "order=scsi0"
}
```

---

## 요약: 주요 변경 사항

| 항목 | Provider 2.x | Provider 3.0 |
|------|-------------|---------------|
| Provider Source | `telmate/proxmox` | `telmate/proxmox` (동일) |
| Provider Version | `~> 2.9.0` | `3.0.2-rc04` (Proxmox 9.x 호환) |
| 권한 | `VM.Monitor` | `Sys.Audit` (Proxmox 9.x) |
| 디스크 블록 | `disk { type = "scsi", slot = 0 }` | `disks { scsi { scsi0 { ... } } }` |
| 슬롯 형식 | 숫자 (`0`) | 문자열 (`"scsi0"`) |
| 디스크 크기 | 문자열 (`"50G"`) | 숫자 (`50`) |
| 네트워크 | `network { model, bridge }` | `network { id = 0, model, bridge }` |
| CPU | `cores = 2` | `cpu { cores = 2 }` |
| Cloud-init | 선택사항 | `os_type = "cloud-init"` 필수 |
| Cloud-init 드라이브 | 자동 | `disks { ide { ide3 { cloudinit } } }` 명시적 |

---

## 참고 자료

1. **공식 Provider 문서:**
   - https://registry.terraform.io/providers/telmate/proxmox/latest/docs

2. **Cloud-init 예제:**
   - https://github.com/Telmate/terraform-provider-proxmox/blob/master/docs/examples/cloudinit_example.tf

3. **Proxmox 9.x 권한 변경:**
   - Proxmox 9.x에서 `VM.Monitor` 권한이 `Sys.Audit`로 변경됨
   - Provider 3.0 이상이 필요

4. **Provider 버전 호환성:**
   - Provider 2.x: Proxmox 8.x 이하
   - Provider 3.0: Proxmox 9.x (권장)

---

## 문제 해결 체크리스트

VM 생성 시 문제가 발생하면 다음을 확인하세요:

- [ ] Provider source가 `telmate/proxmox`인가?
- [ ] Provider 버전이 `3.0.2-rc04` 이상인가? (Proxmox 9.x 사용 시)
- [ ] API Token에 `Sys.Audit` 권한이 있는가?
- [ ] `disks` 블록 형식이 Provider 3.0에 맞는가?
- [ ] 네트워크 블록에 `id = 0`이 있는가?
- [ ] Cloud-init 사용 시 `os_type = "cloud-init"`이 설정되어 있는가?
- [ ] Cloud-init 드라이브가 `ide3`에 추가되어 있는가?
- [ ] 부팅 순서가 템플릿의 원래 디스크 슬롯과 일치하는가?
- [ ] 템플릿의 원래 디스크가 `disks` 블록에 명시적으로 정의되어 있는가?

---

## 작성일
2024년 (문제 해결 완료 시점)

