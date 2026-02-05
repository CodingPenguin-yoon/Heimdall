# Proxmox 웹 관리 플랫폼

Proxmox 가상화 환경을 웹 기반으로 관리할 수 있는 통합 플랫폼입니다. Terraform을 사용하여 VM을 생성하고, Ansible을 통해 자동 설정을 적용합니다.

## 📋 목차

- [주요 기능](#-주요-기능)
- [기술 스택](#-기술-스택)
- [아키텍처 원칙](#️-아키텍처-원칙)
- [빠른 시작](#-빠른-시작)
- [프로젝트 구조](#️-프로젝트-구조)
- [API 엔드포인트](#-api-엔드포인트)
- [워크플로우](#-워크플로우)
- [환경 변수](#️-환경-변수)
- [문제 해결](#-문제-해결)
- [개발 가이드](#-개발-가이드)
- [추가 문서](#-추가-문서)

## ✨ 주요 기능

### 1. 인스턴스 관리

#### 인스턴스 생성 (Create Instance)
- **4단계 마법사**: 직관적인 단계별 인터페이스로 VM 생성
  - **Step 1**: 서버(노드) 선택 및 템플릿/ISO 이미지 선택
  - **Step 2**: CPU 코어 수, 메모리 크기, 스토리지 선택
  - **Step 3**: 네트워크 인터페이스 선택 (다중 선택 가능)
  - **Step 4**: Ansible 패키지 및 역할 선택
- **실시간 상태 표시**: 배포 진행 상황을 실시간으로 확인
- **로그 뷰어**: 배포 과정의 실시간 로그를 터미널 스타일로 표시

#### 인스턴스 목록 (Instance List)
- **VM 목록 조회**: 배포된 모든 VM을 테이블 형식으로 표시
- **상태 표시**: 각 인스턴스의 상태 배지 (Running, Stopped, Deploying, Failed)
- **자동 새로고침**: 30초마다 자동으로 목록 갱신
- **수동 새로고침**: Refresh 버튼으로 즉시 갱신

### 2. Proxmox 리소스 조회

- **노드(서버) 조회**: Proxmox 클러스터의 모든 노드 목록 조회
- **템플릿 조회**: 사용 가능한 VM 템플릿 목록 조회
- **VM 조회**: 배포된 모든 VM 목록 조회 (템플릿 제외)
- **스토리지 조회**: 각 노드의 스토리지 목록 및 사용량 조회
- **네트워크 조회**: 각 노드의 네트워크 인터페이스 목록 조회
- **ISO 이미지 조회**: 각 노드의 ISO 이미지 목록 조회

### 3. 실시간 모니터링

- **노드 모니터링 대시보드**: 모든 Proxmox 노드의 리소스 사용률 표시
- **VM 모니터링**: 특정 VM의 상세 모니터링 정보
- **리소스 사용률 추적**: CPU, 메모리, 디스크 사용률 시각화
- **RRD 데이터 시각화**: Proxmox RRD 데이터를 통한 시계열 모니터링

### 4. 배포 관리

- **Terraform 통합**: Terraform apply를 통한 Proxmox VM 자동 생성
- **IP 주소 자동 추출**: Terraform output에서 IP 주소 추출
- **Ansible Inventory 자동 생성**: 추출한 IP 주소로 inventory.yml 동적 생성
- **Ansible Playbook 자동 실행**: 생성된 inventory로 playbook 실행
- **실시간 로그 스트리밍**: 배포 과정의 실시간 로그 수집 및 제공 (2초 간격 폴링)

## 🛠️ 기술 스택

### 백엔드
- **FastAPI**: Python 기반의 현대적인 웹 프레임워크
- **Uvicorn**: ASGI 서버 (FastAPI 실행)
- **Pydantic**: 데이터 검증 및 직렬화
- **Python-dotenv**: 환경 변수 관리
- **Requests**: HTTP 클라이언트 (Proxmox API 호출)
- **PyYAML**: YAML 파일 처리 (Ansible inventory 생성)

### 프론트엔드
- **React 18**: 사용자 인터페이스 구축
- **Vite**: 빠른 개발 서버 및 빌드 도구
- **Tailwind CSS**: 유틸리티 기반 CSS 프레임워크
- **Lucide React**: 아이콘 라이브러리
- **Axios**: HTTP 클라이언트
- **React Router DOM v7**: 클라이언트 사이드 라우팅

### 인프라 도구
- **Terraform**: Infrastructure as Code (IaC)
- **Ansible**: 구성 관리 및 자동화
- **Proxmox**: 가상화 플랫폼

## 🏛️ 아키텍처 원칙

### 조회 vs 제어 분리

이 프로젝트는 **조회(Read)와 제어(Create/Update/Delete)를 명확히 분리**합니다:

#### 🔍 조회 (Proxmox API 직접 사용)
- **용도**: 리소스 정보 조회 (서버, 템플릿, 스토리지, 네트워크, VM 목록)
- **방식**: Proxmox API 직접 호출
- **서비스**: `proxmox_service.py`
- **라우트**: `routes/proxmox.py`
- **장점**: 
  - 빠른 응답 시간
  - 실시간 데이터
  - 네트워크 부하 최소화
- **API 예시**: `GET /api/servers`, `GET /api/templates`, `GET /api/vms` 등

#### ⚙️ 제어 (Terraform 사용)
- **용도**: 리소스 생성/수정/삭제 (VM 생성, 설정 변경 등)
- **방식**: Terraform IaC (Infrastructure as Code)
- **서비스**: `terraform_service.py`, `deployment_service.py`
- **라우트**: `routes/deploy.py`
- **장점**:
  - 코드로 관리 (버전 관리, 추적 가능)
  - 안전성 (plan으로 변경사항 미리 확인)
  - 일관성 보장
  - 롤백 가능
- **API 예시**: `POST /api/deploy` (Terraform apply 실행)

이 분리로 **안전성과 효율성을 모두 확보**합니다.

## 🚀 빠른 시작

### 사전 요구사항

- **Python 3.8 이상**
- **Node.js 16 이상** 및 npm
- **Terraform 1.0 이상**
- **Ansible 2.9 이상**
- **Proxmox 서버** 및 API Token

### 1. 저장소 클론

```bash
git clone <repository-url>
cd proxmox_web
```

### 2. 환경 설정

```bash
# 프로젝트 루트에서 .env 파일 생성
cp env.example .env

# .env 파일 편집 (Proxmox API 정보 입력)
# PROXMOX_API_URL=https://your-proxmox-server:8006/api2/json
# PROXMOX_API_TOKEN_ID=user@pam!token_name
# PROXMOX_API_TOKEN_SECRET=your_token_secret
```

### 3. 백엔드 설정

```bash
cd backend

# Python 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 4. 프론트엔드 설정

```bash
cd frontend

# 의존성 설치
npm install
```

### 5. 실행

#### 방법 1: 자동 실행 스크립트 사용 (권장)

```bash
# 프로젝트 루트에서
chmod +x run.sh
./run.sh
```

스크립트가 자동으로:
- 백엔드 가상환경 확인 및 생성
- 의존성 설치 확인
- 환경 변수 로드 및 Terraform 변수 설정
- 백엔드와 프론트엔드를 동시에 실행

#### 방법 2: 수동 실행

**터미널 1 - 백엔드:**
```bash
cd backend
source venv/bin/activate

# 환경 변수 로드 (프로젝트 루트의 .env 파일)
export $(cat ../.env | grep -v '^#' | xargs)

# Terraform 환경 변수 설정
export TF_VAR_proxmox_api_url="${PROXMOX_API_URL}"
export TF_VAR_proxmox_api_token_id="${PROXMOX_API_TOKEN_ID}"
export TF_VAR_proxmox_api_token_secret="${PROXMOX_API_TOKEN_SECRET}"
export TF_VAR_proxmox_tls_insecure="${PROXMOX_TLS_INSECURE}"

# 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**터미널 2 - 프론트엔드:**
```bash
cd frontend
npm run dev
```

### 6. 접속

- **프론트엔드**: http://localhost:5173
- **백엔드 API**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs (Swagger UI)

## 🏗️ 프로젝트 구조

```
proxmox_web/
├── backend/                      # FastAPI 백엔드
│   ├── app/
│   │   ├── main.py              # FastAPI 앱 진입점
│   │   │                        # - CORS 설정
│   │   │                        # - 라우트 등록
│   │   │                        # - 환경 변수 로드
│   │   ├── routes/              # API 라우트 모듈
│   │   │   ├── __init__.py
│   │   │   ├── deploy.py        # POST /api/deploy - 배포 시작
│   │   │   ├── status.py        # GET /api/status/{task_id} - 상태 조회
│   │   │   ├── logs.py          # GET /api/logs/{task_id} - 로그 조회
│   │   │   └── proxmox.py       # GET /api/* - Proxmox 리소스 조회
│   │   └── services/            # 비즈니스 로직 서비스
│   │       ├── __init__.py
│   │       ├── task_manager.py  # 작업 상태 관리 (메모리 기반)
│   │       ├── terraform_service.py  # Terraform 실행 서비스
│   │       ├── ansible_service.py    # Ansible 실행 서비스
│   │       ├── deployment_service.py # 배포 통합 서비스
│   │       └── proxmox_service.py    # Proxmox API 연동 서비스
│   ├── iac/                     # Infrastructure as Code
│   │   ├── terraform/           # Terraform 설정 파일
│   │   │   ├── main.tf         # Proxmox Provider 설정
│   │   │   └── variables.tf    # 변수 정의
│   │   └── ansible/             # Ansible Playbook
│   │       ├── playbook.yml    # 메인 Playbook
│   │       └── inventory.yml.example  # Inventory 예제
│   ├── requirements.txt         # Python 의존성
│   └── README.md                # 백엔드 README
├── frontend/                    # React 프론트엔드
│   ├── src/
│   │   ├── App.jsx             # 메인 앱 컴포넌트
│   │   │                       # - 라우팅 설정
│   │   │                       # - 전역 상태 관리
│   │   │                       # - 배포 로직
│   │   ├── main.jsx            # React 진입점
│   │   ├── index.css           # 전역 스타일 (Tailwind CSS)
│   │   ├── components/         # UI 컴포넌트
│   │   │   ├── CreateInstanceWizard.jsx  # 인스턴스 생성 마법사
│   │   │   ├── InstanceList.jsx          # 인스턴스 목록
│   │   │   ├── MonitoringDashboard.jsx   # 모니터링 대시보드
│   │   │   ├── StatusPanel.jsx           # 상태 패널
│   │   │   ├── LogViewer.jsx             # 로그 뷰어
│   │   │   ├── ControlCenter.jsx         # 제어 센터 (레거시)
│   │   │   └── DeployForm.jsx            # 배포 폼 (레거시)
│   │   └── services/           # API 클라이언트
│   │       └── api.js          # Axios 기반 API 클라이언트
│   ├── index.html              # HTML 템플릿
│   ├── vite.config.js          # Vite 설정 (프록시 설정 포함)
│   ├── tailwind.config.js      # Tailwind CSS 설정
│   ├── postcss.config.js       # PostCSS 설정
│   ├── package.json            # 의존성 및 스크립트
│   └── README.md               # 프론트엔드 README
├── docs/                        # 문서
│   ├── backend/                # 백엔드 문서
│   │   ├── 01_OVERVIEW.md
│   │   ├── 02_ARCHITECTURE.md
│   │   ├── 03_API_ENDPOINTS.md
│   │   ├── 04_SERVICES.md
│   │   ├── 05_DEPLOYMENT_FLOW.md
│   │   └── 06_RUNNING.md
│   ├── frontend/               # 프론트엔드 문서
│   │   ├── API_REQUIREMENTS.md
│   │   ├── DATA_MODEL.md
│   │   └── FEATURE_SPECIFICATION.md
│   ├── ENV_SETTINGS_EXPLAINED.md
│   ├── TEMPLATE_PREPARATION.md
│   └── VM_CREATION_METHODS.md
├── .env                         # 환경 변수 (gitignore)
├── env.example                  # 환경 변수 예제
├── run.sh                       # 실행 스크립트
└── README.md                    # 이 파일
```

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

#### 리소스 조회
- `GET /api/servers` - Proxmox 노드(서버) 목록 조회
- `GET /api/templates` - 템플릿 목록 조회
- `GET /api/vms` - VM 목록 조회 (템플릿 제외)
- `GET /api/instances` - 인스턴스 목록 조회 (VM 목록과 동일, 프론트엔드 호환성)
- `GET /api/servers/{server_id}/storage` - 특정 서버의 스토리지 목록 조회
- `GET /api/servers/{server_id}/networks` - 특정 서버의 네트워크 목록 조회
- `GET /api/servers/{server_id}/iso-images` - 특정 서버의 ISO 이미지 목록 조회
- `GET /api/servers/{server_id}/vms` - 특정 서버의 VM 목록 조회

#### 모니터링 API
- `GET /api/monitoring/nodes` - 모든 노드의 모니터링 정보 조회
- `GET /api/monitoring/nodes/{node_id}` - 특정 노드의 상세 모니터링 정보 조회
- `GET /api/monitoring/vms/{node_id}/{vmid}` - 특정 VM의 모니터링 정보 조회

### 헬스체크

- `GET /` - 기본 헬스체크
- `GET /health` - 상세 헬스체크

자세한 API 문서는 http://localhost:8000/docs (Swagger UI)에서 확인할 수 있습니다.

## 🔄 워크플로우

### 배포 프로세스

1. **프론트엔드에서 배포 요청**
   - 사용자가 CreateInstanceWizard에서 단계별로 설정 입력
   - "Launch Instance" 버튼 클릭
   - 프론트엔드가 `POST /api/deploy`로 요청 전송

2. **백엔드 배포 시작**
   - 요청 데이터 검증 (Pydantic 모델)
   - 고유 `task_id` 생성 (UUID)
   - `TaskManager`에 작업 등록
   - `BackgroundTasks`에 배포 작업 등록
   - 즉시 `task_id` 반환 (비동기 처리)

3. **Terraform 실행** (백그라운드)
   - `terraform init`: Terraform 초기화
   - `terraform plan`: 변경사항 계획
   - `terraform apply`: VM 생성
   - 실시간 로그를 `TaskManager`에 저장

4. **IP 주소 추출**
   - `terraform output -json`으로 출력 조회
   - `vm_ip`, `instance_ip` 등의 키에서 IP 주소 추출

5. **Ansible Inventory 생성**
   - 추출한 IP 주소로 `inventory.yml` 동적 생성
   - SSH 사용자 및 키 정보 포함

6. **Ansible Playbook 실행**
   - 생성된 inventory로 `ansible-playbook` 실행
   - 실시간 로그 스트리밍

7. **프론트엔드 실시간 업데이트**
   - `startPolling(taskId)` 함수 실행
   - 2초 간격으로 `/api/status/{task_id}`와 `/api/logs/{task_id}` 폴링
   - 새로운 로그를 UI에 실시간 표시
   - 성공/실패 상태 도달 시 폴링 중지
   - 최대 10분 후 타임아웃

## ⚙️ 환경 변수

`.env` 파일에 다음 변수들을 설정하세요:

```bash
# ============================================
# Proxmox API 설정 (조회용)
# ============================================
PROXMOX_API_URL=https://proxmox.example.com:8006/api2/json
PROXMOX_API_TOKEN_ID=user@pam!token_name
PROXMOX_API_TOKEN_SECRET=your_token_secret_here
PROXMOX_TLS_INSECURE=false

# ============================================
# Terraform 설정 (제어용)
# ============================================
# 주의: Terraform은 TF_VAR_ 접두사를 가진 환경변수를 자동으로 읽습니다.
# run.sh 스크립트가 자동으로 변환하므로, 아래 변수들은 설정하지 않아도 됩니다.
# (PROXMOX_API_URL, PROXMOX_API_TOKEN_ID, PROXMOX_API_TOKEN_SECRET가 자동 변환됨)

# ============================================
# Ansible 설정
# ============================================
ANSIBLE_SSH_USER=root
ANSIBLE_SSH_PRIVATE_KEY_FILE=~/.ssh/id_rsa
ANSIBLE_SSH_PUBLIC_KEY_FILE=~/.ssh/id_rsa.pub

# ============================================
# 백엔드 서버 설정
# ============================================
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# ============================================
# 프론트엔드 설정
# ============================================
FRONTEND_PORT=5173
```

자세한 환경 변수 설명은 [ENV_SETTINGS_EXPLAINED.md](./docs/ENV_SETTINGS_EXPLAINED.md)를 참조하세요.

## 🐛 문제 해결

### 백엔드가 시작되지 않음
- Python 가상환경이 활성화되어 있는지 확인
- `requirements.txt`의 모든 패키지가 설치되었는지 확인
- 포트 8000이 사용 중이 아닌지 확인 (`lsof -i :8000`)
- `.env` 파일이 올바르게 설정되었는지 확인
- 백엔드 로그 확인 (`tail -f backend.log`)

### 프론트엔드가 백엔드에 연결되지 않음
- `vite.config.js`의 프록시 설정 확인
- 백엔드가 `http://localhost:8000`에서 실행 중인지 확인
- CORS 설정 확인 (`backend/app/main.py`)
- 브라우저 콘솔에서 네트워크 오류 확인

### Terraform 실행 실패
- `.env` 파일의 Proxmox API 정보 확인
- 환경 변수가 `TF_VAR_` 접두사로 설정되었는지 확인 (`run.sh`가 자동 처리)
- Terraform이 설치되어 있는지 확인 (`terraform version`)
- Terraform 로그 확인 (`backend.log` 또는 `backend/iac/terraform/terraform.log`)

### Ansible 실행 실패
- Ansible이 설치되어 있는지 확인 (`ansible --version`)
- SSH 키가 올바른 경로에 있는지 확인
- Inventory 파일이 올바르게 생성되었는지 확인 (`backend/iac/ansible/inventory.yml`)
- SSH 접속 테스트 (`ssh -i ~/.ssh/id_rsa root@<vm_ip>`)

### 로그가 실시간으로 업데이트되지 않음
- 브라우저 콘솔에서 네트워크 오류 확인
- 백엔드 로그에서 에러 메시지 확인 (`tail -f backend.log`)
- `task_id`가 올바른지 확인
- 폴링 간격 확인 (기본 2초)

### Proxmox API 연결 실패
- Proxmox 서버 URL이 올바른지 확인
- API Token이 유효한지 확인 (Proxmox 웹 UI에서 확인)
- TLS 인증서 문제인 경우 `PROXMOX_TLS_INSECURE=true` 설정
- 방화벽 설정 확인 (포트 8006)
- 네트워크 연결 확인 (`curl -k https://proxmox-server:8006/api2/json/version`)

## 📝 개발 가이드

### 백엔드 개발

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

### 프론트엔드 개발

```bash
cd frontend
npm run dev
```

### 코드 스타일
- **Python**: PEP 8 준수, 타입 힌팅 사용, 상세한 주석 작성
- **JavaScript**: ESLint 규칙 준수, 함수형 컴포넌트 사용

### 로그 확인

```bash
# 백엔드 로그 (run.sh 사용 시)
tail -f backend.log

# 프론트엔드 로그 (run.sh 사용 시)
tail -f frontend.log

# 또는 직접 실행 시 터미널 출력 확인
```

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
```

## 📚 추가 문서

### 백엔드 문서
- [백엔드 개요](./docs/backend/01_OVERVIEW.md)
- [아키텍처](./docs/backend/02_ARCHITECTURE.md)
- [API 엔드포인트 상세](./docs/backend/03_API_ENDPOINTS.md)
- [서비스 레이어](./docs/backend/04_SERVICES.md)
- [배포 플로우](./docs/backend/05_DEPLOYMENT_FLOW.md)
- [실행 방법](./docs/backend/06_RUNNING.md)
- [백엔드 README](./backend/README.md)

### 프론트엔드 문서
- [기능 명세](./frontend/docs/FEATURE_SPECIFICATION.md)
- [API 요구사항](./frontend/docs/API_REQUIREMENTS.md)
- [데이터 모델](./frontend/docs/DATA_MODEL.md)
- [프론트엔드 README](./frontend/README.md)

### 기타 문서
- [환경 변수 설명](./docs/ENV_SETTINGS_EXPLAINED.md)
- [템플릿 준비](./docs/TEMPLATE_PREPARATION.md)
- [VM 생성 방법](./docs/VM_CREATION_METHODS.md)
- [Ansible 자동화](./docs/ANSIBLE_AUTOMATION.md)

## 🤝 기여

이 프로젝트는 내부 사용을 위한 것입니다. 기여를 원하시면 프로젝트 관리자에게 문의하세요.

## 📄 라이선스

이 프로젝트는 내부 사용을 위한 것입니다.

## 🙏 감사의 말

- [Proxmox](https://www.proxmox.com/) - 가상화 플랫폼
- [Terraform](https://www.terraform.io/) - Infrastructure as Code
- [Ansible](https://www.ansible.com/) - 구성 관리 및 자동화
- [FastAPI](https://fastapi.tiangolo.com/) - 현대적인 Python 웹 프레임워크
- [React](https://react.dev/) - 사용자 인터페이스 라이브러리
