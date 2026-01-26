# Terraform & Ansible Control Backend

Terraform과 Ansible을 제어하는 FastAPI 백엔드 서버입니다.

## 기능

- **인프라 배포**: Terraform apply와 Ansible playbook을 순차적으로 실행
- **작업 상태 관리**: 배포 작업의 실시간 상태 추적 (Pending, Running, Success, Failed)
- **로그 조회**: 실행 중인 프로세스의 실시간 로그 조회
- **Proxmox 연동**: Proxmox Provider를 통한 가상화 환경 관리

## 프로젝트 구조

```
backend/
├── app/
│   ├── main.py                 # FastAPI 애플리케이션 진입점
│   ├── routes/                 # API 라우트
│   │   ├── deploy.py           # POST /api/deploy
│   │   ├── status.py           # GET /api/status/{task_id}
│   │   └── logs.py             # GET /api/logs/{task_id}
│   └── services/               # 비즈니스 로직
│       ├── task_manager.py     # 작업 상태 관리
│       ├── terraform_service.py # Terraform 실행 서비스
│       ├── ansible_service.py  # Ansible 실행 서비스
│       └── deployment_service.py # 배포 통합 서비스
├── iac/
│   ├── terraform/              # Terraform 설정 파일
│   │   ├── main.tf             # Proxmox Provider 설정
│   │   └── variables.tf        # 변수 정의
│   └── ansible/                # Ansible Playbook
│       ├── playbook.yml        # 메인 Playbook
│       └── inventory.yml.example # Inventory 예제
├── requirements.txt            # Python 의존성
└── .env.example                # 환경변수 예제
```

## 설치 및 실행

### 1. 가상환경 설정

```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate  # macOS/Linux
# 또는
venv\Scripts\activate  # Windows
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 편집하여 Proxmox API 정보 입력
```

### 4. Terraform Provider 설정

`iac/terraform/main.tf` 파일의 변수에 환경변수를 설정하거나, `terraform.tfvars` 파일을 생성하세요.

환경변수로 설정하는 경우:
```bash
export TF_VAR_proxmox_api_url="https://proxmox.example.com:8006/api2/json"
export TF_VAR_proxmox_api_token_id="user@pam!token_name"
export TF_VAR_proxmox_api_token_secret="your-token-secret"
```

### 5. 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

서버는 `http://localhost:8000`에서 실행됩니다.

## API 엔드포인트

### POST /api/deploy
배포 작업을 시작합니다.

**요청 본문:**
```json
{
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

## 주의사항

1. **Terraform 및 Ansible 설치 필요**: 서버가 실행되는 환경에 `terraform`과 `ansible-playbook` 명령어가 설치되어 있어야 합니다.

2. **Proxmox API 인증**: Proxmox API Token을 생성하고 환경변수에 설정해야 합니다.

3. **네트워크 접근**: Terraform과 Ansible이 대상 리소스에 접근할 수 있는 네트워크 환경이 필요합니다.

4. **보안**: 프로덕션 환경에서는 환경변수와 API 토큰을 안전하게 관리하세요.

## 개발

### 코드 스타일
- Python 3.10+ 사용
- 타입 힌팅 사용
- 상세한 주석 작성 (비즈니스 로직, 예외 처리, MCP 메시지 핸들링)

### 테스트
```bash
# API 테스트
curl -X POST http://localhost:8000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{"skip_terraform": false, "skip_ansible": false}'
```
