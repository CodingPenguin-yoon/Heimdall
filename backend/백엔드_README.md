# Proxmox 웹 관리 플랫폼 - 백엔드

Terraform과 Ansible을 제어하고 Proxmox API와 연동하는 FastAPI 백엔드 서버입니다.

## 🎯 주요 기능

### 1. 인프라 배포 관리
- **Terraform 통합**: Terraform apply를 통한 Proxmox VM 자동 생성
- **Ansible 통합**: Ansible playbook을 통한 자동 설정 적용
- **IP 주소 자동 추출**: Terraform output에서 IP 주소 추출 및 Ansible inventory 자동 생성
- **실시간 로그 스트리밍**: 배포 과정의 실시간 로그 수집 및 제공

### 2. 작업 상태 관리
- **작업 추적**: 배포 작업의 실시간 상태 추적 (Pending, Running, Success, Failed)
- **작업 ID**: 각 배포 작업에 고유한 UUID 할당
- **상태 조회 API**: 작업 상태를 실시간으로 조회할 수 있는 API 제공

### 3. Proxmox 리소스 조회
- **노드(서버) 조회**: Proxmox 클러스터의 모든 노드 목록 조회
- **템플릿 조회**: 사용 가능한 VM 템플릿 목록 조회
- **VM 조회**: 배포된 모든 VM 목록 조회 (템플릿 제외)
- **스토리지 조회**: 각 노드의 스토리지 목록 조회
- **네트워크 조회**: 각 노드의 네트워크 인터페이스 목록 조회
- **ISO 이미지 조회**: 각 노드의 ISO 이미지 목록 조회

### 4. 모니터링
- **노드 모니터링**: 모든 노드의 리소스 사용률 조회
- **VM 모니터링**: 특정 VM의 상세 모니터링 정보 조회
- **RRD 데이터**: Proxmox RRD 데이터를 통한 시계열 모니터링 정보 제공

## 🏗️ 프로젝트 구조

```
backend/
├── app/
│   ├── main.py                 # FastAPI 애플리케이션 진입점
│   │                           # - CORS 설정
│   │                           # - 라우트 등록
│   │                           # - 환경 변수 로드
│   ├── routes/                  # API 라우트 모듈
│   │   ├── __init__.py
│   │   ├── deploy.py           # POST /api/deploy - 배포 시작
│   │   ├── status.py           # GET /api/status/{task_id} - 상태 조회
│   │   ├── logs.py             # GET /api/logs/{task_id} - 로그 조회
│   │   └── proxmox.py          # GET /api/* - Proxmox 리소스 조회
│   └── services/               # 비즈니스 로직 서비스
│       ├── __init__.py
│       ├── task_manager.py     # 작업 상태 관리 (메모리 기반)
│       ├── terraform_service.py # Terraform 실행 서비스
│       ├── ansible_service.py  # Ansible 실행 서비스
│       ├── deployment_service.py # 배포 통합 서비스
│       └── proxmox_service.py  # Proxmox API 연동 서비스
├── iac/                        # Infrastructure as Code
│   ├── terraform/              # Terraform 설정 파일
│   │   ├── main.tf             # Proxmox Provider 설정
│   │   └── variables.tf        # 변수 정의
│   └── ansible/                # Ansible Playbook
│       ├── playbook.yml        # 메인 Playbook
│       └── inventory.yml.example # Inventory 예제
├── requirements.txt            # Python 의존성
└── 백엔드_README.md            # 이 파일
```

## 🏛️ 아키텍처 원칙

### 조회 vs 제어 분리

이 백엔드는 **조회(Read)와 제어(Create/Update/Delete)를 명확히 분리**합니다:

#### 🔍 조회 (Proxmox API 직접 사용)
- **서비스**: `proxmox_service.py`
- **라우트**: `routes/proxmox.py`
- **용도**: 리소스 정보 조회 (서버, 템플릿, 스토리지, 네트워크, VM 목록)
- **방식**: Proxmox API 직접 호출
- **장점**: 
  - 빠른 응답 시간
  - 실시간 데이터
  - 네트워크 부하 최소화

#### ⚙️ 제어 (Terraform 사용)
- **서비스**: `terraform_service.py`, `deployment_service.py`
- **라우트**: `routes/deploy.py`
- **용도**: 리소스 생성/수정/삭제 (VM 생성, 설정 변경 등)
- **방식**: Terraform IaC (Infrastructure as Code)
- **장점**:
  - 코드로 관리 (버전 관리, 추적 가능)
  - 안전성 (plan으로 변경사항 미리 확인)
  - 일관성 보장
  - 롤백 가능

## 📦 설치 및 실행

### 1. 사전 요구사항

- Python 3.8 이상
- Terraform 1.0 이상
- Ansible 2.9 이상
- Proxmox 서버 및 API Token

### 2. 가상환경 설정

```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate  # macOS/Linux
# 또는
venv\Scripts\activate  # Windows
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

프로젝트 루트의 `.env` 파일을 설정하세요. (백엔드 디렉토리가 아닌 프로젝트 루트)

```bash
# 프로젝트 루트에서
cp ../env.example ../.env
# .env 파일을 편집하여 Proxmox API 정보 입력
```

필수 환경 변수:
- `PROXMOX_API_URL`: Proxmox API URL
- `PROXMOX_API_TOKEN_ID`: API Token ID
- `PROXMOX_API_TOKEN_SECRET`: API Token Secret
- `ANSIBLE_SSH_USER`: SSH 사용자명
- `ANSIBLE_SSH_PRIVATE_KEY_FILE`: SSH 개인키 경로

### 5. Terraform 환경 변수 설정

`run.sh` 스크립트가 자동으로 변환하지만, 수동 실행 시:

```bash
# 환경 변수 로드
export $(cat ../.env | grep -v '^#' | xargs)

# Terraform 환경 변수 설정
export TF_VAR_proxmox_api_url="${PROXMOX_API_URL}"
export TF_VAR_proxmox_api_token_id="${PROXMOX_API_TOKEN_ID}"
export TF_VAR_proxmox_api_token_secret="${PROXMOX_API_TOKEN_SECRET}"
export TF_VAR_proxmox_tls_insecure="${PROXMOX_TLS_INSECURE}"
```

### 6. 서버 실행

```bash
# 개발 모드 (자동 리로드)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 프로덕션 모드
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

서버는 `http://localhost:8000`에서 실행됩니다.

## 🔧 API 엔드포인트

### 배포 API

#### POST `/api/deploy`
배포 작업을 시작합니다.

**요청 본문:**
```json
{
  "server_id": "pve-node-01",
  "template_id": "pve-node-01/100",
  "iso_image_id": "local:iso/ubuntu.iso",
  "storage_id": "local-lvm",
  "network_ids": ["vmbr0"],
  "server_name": "my-vm",
  "cpu_cores": 2,
  "memory_gb": 4,
  "ansible_packages": ["nginx", "docker"],
  "ansible_roles": ["docker"],
  "skip_terraform": false,
  "skip_ansible": false
}
```

**응답:**
```json
{
  "task_id": "uuid-string",
  "message": "배포 작업이 시작되었습니다.",
  "status": "pending"
}
```

### 상태 및 로그 API

#### GET `/api/status/{task_id}`
배포 작업의 현재 상태를 조회합니다.

**응답:**
```json
{
  "task_id": "uuid-string",
  "status": "Running",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:01"
}
```

**상태 값:**
- `Pending`: 작업 대기 중
- `Running`: 작업 실행 중
- `Success`: 작업 성공
- `Failed`: 작업 실패

#### GET `/api/logs/{task_id}`
배포 작업의 로그를 조회합니다.

**응답:**
```json
{
  "task_id": "uuid-string",
  "logs": [
    "[2024-01-01 00:00:00] === 배포 작업 시작 ===",
    "[2024-01-01 00:00:01] === Terraform Init 시작 ==="
  ],
  "total_lines": 2
}
```

### Proxmox 조회 API

모든 Proxmox 조회 API는 **GET 메서드만 사용**하며, 리소스 생성/수정/삭제는 Terraform을 통해 수행합니다.

#### GET `/api/servers`
Proxmox 노드(서버) 목록 조회

#### GET `/api/templates`
템플릿 목록 조회

#### GET `/api/vms`
VM 목록 조회 (템플릿 제외)

#### GET `/api/instances`
인스턴스 목록 조회 (VM 목록과 동일, 프론트엔드 호환성)

#### GET `/api/servers/{server_id}/storage`
특정 서버의 스토리지 목록 조회

#### GET `/api/servers/{server_id}/networks`
특정 서버의 네트워크 목록 조회

#### GET `/api/servers/{server_id}/iso-images`
특정 서버의 ISO 이미지 목록 조회

#### GET `/api/servers/{server_id}/vms`
특정 서버의 VM 목록 조회

### 모니터링 API

#### GET `/api/monitoring/nodes`
모든 노드의 모니터링 정보 조회

#### GET `/api/monitoring/nodes/{node_id}`
특정 노드의 상세 모니터링 정보 조회

#### GET `/api/monitoring/vms/{node_id}/{vmid}`
특정 VM의 모니터링 정보 조회

### 헬스체크

#### GET `/`
기본 헬스체크

#### GET `/health`
상세 헬스체크

자세한 API 문서는 http://localhost:8000/docs (Swagger UI)에서 확인할 수 있습니다.

## 🔄 배포 워크플로우

1. **배포 요청 수신** (`POST /api/deploy`)
   - 요청 데이터 검증 (Pydantic 모델)
   - 고유 `task_id` 생성
   - `TaskManager`에 작업 등록
   - `BackgroundTasks`에 배포 작업 등록
   - 즉시 `task_id` 반환 (비동기 처리)

2. **Terraform 실행** (백그라운드)
   - `terraform init`: Terraform 초기화
   - `terraform plan`: 변경사항 계획
   - `terraform apply`: VM 생성
   - 실시간 로그를 `TaskManager`에 저장

3. **IP 주소 추출**
   - `terraform output -json`으로 출력 조회
   - `vm_ip`, `instance_ip` 등의 키에서 IP 주소 추출

4. **Ansible Inventory 생성**
   - 추출한 IP 주소로 `inventory.yml` 동적 생성
   - SSH 사용자 및 키 정보 포함

5. **Ansible Playbook 실행**
   - 생성된 inventory로 `ansible-playbook` 실행
   - 실시간 로그 스트리밍

6. **상태 업데이트**
   - 성공/실패에 따라 작업 상태 업데이트
   - 최종 로그 저장

## 📝 서비스 모듈 상세

### TaskManager (`task_manager.py`)
- 작업 상태를 메모리에 저장 (in-memory)
- 작업별 로그 수집 및 관리
- 작업 상태 변경 추적

### TerraformService (`terraform_service.py`)
- Terraform 명령어 실행 (`init`, `plan`, `apply`, `output`)
- 실시간 로그 캡처
- Terraform 출력 파싱 및 IP 주소 추출

### AnsibleService (`ansible_service.py`)
- Ansible inventory 동적 생성
- Ansible playbook 실행
- 실시간 로그 캡처

### DeploymentService (`deployment_service.py`)
- Terraform과 Ansible을 통합하여 배포 프로세스 관리
- 배포 요청 데이터 처리
- 배포 단계별 상태 관리

### ProxmoxService (`proxmox_service.py`)
- Proxmox API와 통신
- 리소스 정보 조회 및 변환
- 모니터링 데이터 수집

## ⚠️ 주의사항

1. **Terraform 및 Ansible 설치 필요**: 서버가 실행되는 환경에 `terraform`과 `ansible-playbook` 명령어가 설치되어 있어야 합니다.

2. **Proxmox API 인증**: Proxmox API Token을 생성하고 환경변수에 설정해야 합니다.

3. **네트워크 접근**: Terraform과 Ansible이 대상 리소스에 접근할 수 있는 네트워크 환경이 필요합니다.

4. **SSH 키 설정**: Ansible이 VM에 접속하기 위해 SSH 키가 올바르게 설정되어 있어야 합니다.

5. **보안**: 프로덕션 환경에서는 환경변수와 API 토큰을 안전하게 관리하세요.

6. **작업 상태 저장**: 현재는 메모리 기반이므로 서버 재시작 시 작업 상태가 초기화됩니다.

## 🧪 개발

### 코드 스타일
- Python 3.8+ 사용
- 타입 힌팅 사용
- 상세한 주석 작성 (비즈니스 로직, 예외 처리, MCP 메시지 핸들링)

### 테스트

```bash
# API 테스트
curl -X POST http://localhost:8000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "server_id": "pve-node-01",
    "template_id": "pve-node-01/100",
    "storage_id": "local-lvm",
    "network_ids": ["vmbr0"],
    "server_name": "test-vm",
    "cpu_cores": 2,
    "memory_gb": 4
  }'

# 상태 조회
curl http://localhost:8000/api/status/{task_id}

# 로그 조회
curl http://localhost:8000/api/logs/{task_id}

# 서버 목록 조회
curl http://localhost:8000/api/servers
```

### 로그 확인

```bash
# 백엔드 로그 (run.sh 사용 시)
tail -f backend.log

# 또는 직접 실행 시 터미널 출력 확인
```

## 📚 추가 문서

- [백엔드 아키텍처](./docs/backend/02_ARCHITECTURE.md)
- [API 엔드포인트 상세](./docs/backend/03_API_ENDPOINTS.md)
- [서비스 레이어 상세](./docs/backend/04_SERVICES.md)
- [배포 플로우 상세](./docs/backend/05_DEPLOYMENT_FLOW.md)
