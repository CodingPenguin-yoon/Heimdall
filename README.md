# Terraform & Ansible 통합 배포 플랫폼

프론트엔드와 백엔드를 통합한 인프라 배포 관리 시스템입니다. Terraform을 사용하여 Proxmox에 VM을 생성하고, Ansible을 통해 자동으로 설정을 적용합니다.

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 프로젝트 루트에서 .env 파일 생성
cp env.example .env

# .env 파일 편집 (Proxmox API 정보 입력)
# PROXMOX_API_URL=https://your-proxmox-server:8006/api2/json
# PROXMOX_API_TOKEN_ID=user@pam!token_name
# PROXMOX_API_TOKEN_SECRET=your_token_secret
```

### 2. 백엔드 설정

```bash
cd backend

# Python 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정 (Terraform용)
export TF_VAR_proxmox_api_url="${PROXMOX_API_URL}"
export TF_VAR_proxmox_api_token_id="${PROXMOX_API_TOKEN_ID}"
export TF_VAR_proxmox_api_token_secret="${PROXMOX_API_TOKEN_SECRET}"
```

### 3. 프론트엔드 설정

```bash
cd frontend

# 의존성 설치
npm install
```

### 4. 실행

#### 방법 1: 자동 실행 스크립트 사용 (권장)

```bash
# 프로젝트 루트에서
chmod +x run.sh
./run.sh
```

#### 방법 2: 수동 실행

**터미널 1 - 백엔드:**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**터미널 2 - 프론트엔드:**
```bash
cd frontend
npm run dev
```

### 5. 접속

- 프론트엔드: http://localhost:5173
- 백엔드 API: http://localhost:8000
- API 문서: http://localhost:8000/docs

## 📋 주요 기능

### 1. 인프라 배포
- Terraform을 통한 Proxmox VM 자동 생성
- Terraform Output에서 IP 주소 자동 추출
- Ansible Inventory에 IP 주소 자동 전달
- 실시간 로그 스트리밍

### 2. 실시간 모니터링
- 배포 상태 실시간 확인
- 로그 실시간 폴링 (2초 간격)
- 에러 메시지 자동 표시

### 3. 환경 변수 관리
- `.env` 파일을 통한 통합 설정 관리
- Proxmox API 인증 정보 관리
- 백엔드/프론트엔드 포트 설정

## 🏗️ 프로젝트 구조

```
terraform_ansible/
├── backend/                 # FastAPI 백엔드
│   ├── app/
│   │   ├── main.py         # FastAPI 앱 진입점
│   │   ├── routes/          # API 라우트
│   │   │   ├── deploy.py   # 배포 API
│   │   │   ├── status.py   # 상태 조회 API
│   │   │   └── logs.py     # 로그 조회 API
│   │   └── services/       # 비즈니스 로직
│   │       ├── terraform_service.py  # Terraform 실행
│   │       ├── ansible_service.py    # Ansible 실행
│   │       ├── deployment_service.py # 배포 통합 관리
│   │       └── task_manager.py      # 작업 상태 관리
│   ├── iac/
│   │   ├── terraform/       # Terraform 설정
│   │   └── ansible/         # Ansible Playbook
│   └── requirements.txt
├── frontend/                # React 프론트엔드
│   ├── src/
│   │   ├── App.jsx         # 메인 앱 컴포넌트
│   │   ├── components/     # UI 컴포넌트
│   │   └── services/       # API 클라이언트
│   └── package.json
├── .env                     # 환경 변수 (gitignore)
├── env.example             # 환경 변수 예제
├── run.sh                  # 실행 스크립트
└── README.md
```

## 🔧 API 엔드포인트

### POST /api/deploy
배포 작업을 시작합니다.

**요청 본문:**
```json
{
  "server_id": "pve-node-01",
  "template_id": "ubuntu-template",
  "storage_id": "local-lvm",
  "network_ids": ["vmbr0"],
  "server_name": "my-vm",
  "cpu_cores": 2,
  "memory_gb": 4,
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

### GET /api/status/{task_id}
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

### GET /api/logs/{task_id}
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

## 🔄 워크플로우

1. **프론트엔드에서 배포 요청**
   - 사용자가 배포 설정을 입력하고 "Launch Instance" 버튼 클릭
   - 프론트엔드가 `/api/deploy`로 POST 요청

2. **백엔드 배포 시작**
   - `task_id` 생성 및 반환
   - BackgroundTasks로 비동기 배포 시작

3. **Terraform 실행**
   - `terraform init` → `terraform plan` → `terraform apply`
   - 실시간 로그를 `task_manager`에 저장

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
   - 2초 간격으로 `/api/status/{task_id}`와 `/api/logs/{task_id}` 폴링
   - 새로운 로그를 UI에 실시간 표시
   - 에러 발생 시 빨간색으로 표시

## ⚙️ 환경 변수

`.env` 파일에 다음 변수들을 설정하세요:

```bash
# Proxmox API 설정
PROXMOX_API_URL=https://proxmox.example.com:8006/api2/json
PROXMOX_API_TOKEN_ID=user@pam!token_name
PROXMOX_API_TOKEN_SECRET=your_token_secret_here
PROXMOX_TLS_INSECURE=false

# 백엔드 서버 설정
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# 프론트엔드 설정
FRONTEND_PORT=5173

# Ansible 설정
ANSIBLE_SSH_USER=root
ANSIBLE_SSH_PRIVATE_KEY_FILE=~/.ssh/id_rsa
```

## 🐛 문제 해결

### 백엔드가 시작되지 않음
- Python 가상환경이 활성화되어 있는지 확인
- `requirements.txt`의 모든 패키지가 설치되었는지 확인
- 포트 8000이 사용 중이 아닌지 확인

### 프론트엔드가 백엔드에 연결되지 않음
- `vite.config.js`의 프록시 설정 확인
- 백엔드가 `http://localhost:8000`에서 실행 중인지 확인
- CORS 설정 확인 (`backend/app/main.py`)

### Terraform 실행 실패
- `.env` 파일의 Proxmox API 정보 확인
- 환경 변수가 `TF_VAR_` 접두사로 설정되었는지 확인
- Terraform이 설치되어 있는지 확인 (`terraform version`)

### Ansible 실행 실패
- Ansible이 설치되어 있는지 확인 (`ansible --version`)
- SSH 키가 올바른 경로에 있는지 확인
- Inventory 파일이 올바르게 생성되었는지 확인 (`backend/iac/ansible/inventory.yml`)

### 로그가 실시간으로 업데이트되지 않음
- 브라우저 콘솔에서 네트워크 오류 확인
- 백엔드 로그에서 에러 메시지 확인
- `task_id`가 올바른지 확인

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
- Python: PEP 8 준수, 타입 힌팅 사용
- JavaScript: ESLint 규칙 준수

## 📄 라이선스

이 프로젝트는 내부 사용을 위한 것입니다.
