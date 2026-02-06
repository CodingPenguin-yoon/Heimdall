# 백엔드 실행 방법

## 사전 요구사항

### 1. Python 환경
- Python 3.9 이상
- pip 패키지 관리자

### 2. 시스템 도구
- **Terraform**: CLI 설치 필요
- **Ansible**: CLI 설치 필요
- **SSH 키**: Ansible이 VM에 접속하기 위한 SSH 키

### 3. 환경 변수 설정
`.env` 파일에 다음 변수들을 설정해야 합니다:

```bash
# Proxmox API 설정
PROXMOX_API_URL=https://your-proxmox-server:8006/api2/json
PROXMOX_API_TOKEN_ID=user@pam!token-name
PROXMOX_API_TOKEN_SECRET=your-token-secret
PROXMOX_TLS_INSECURE=false

# Ansible 설정
ANSIBLE_SSH_USER=root
ANSIBLE_SSH_PRIVATE_KEY_FILE=/path/to/ssh/private/key

# 서버 포트 설정
BACKEND_PORT=8000
FRONTEND_PORT=5173
```

자세한 환경 변수 설명은 [ENV_SETTINGS_EXPLAINED.md](../ENV_SETTINGS_EXPLAINED.md)를 참고하세요.

---

## 실행 방법

### 방법 1: run.sh 스크립트 사용 (권장)

프로젝트 루트에서 실행:

```bash
./run.sh
```

**동작 과정**:
1. Python 가상환경 확인 및 생성
2. 백엔드 의존성 설치
3. 프론트엔드 의존성 설치
4. 백엔드 서버 시작 (포트 8000)
5. 프론트엔드 서버 시작 (포트 5173)

**로그 확인**:
```bash
# 백엔드 로그
tail -f backend.log

# 프론트엔드 로그
tail -f frontend.log
```

---

### 방법 2: 수동 실행

#### 2.1 가상환경 설정

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows
```

#### 2.2 의존성 설치

```bash
pip install -r requirements.txt
```

#### 2.3 환경 변수 설정

프로젝트 루트에 `.env` 파일 생성:

```bash
cp env.example .env
# .env 파일 편집
```

#### 2.4 서버 실행

```bash
# 가상환경 활성화 상태에서
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**옵션 설명**:
- `--host 0.0.0.0`: 모든 네트워크 인터페이스에서 접속 허용
- `--port 8000`: 서버 포트 (기본값: 8000)
- `--reload`: 코드 변경 시 자동 재시작 (개발 모드)

---

## 서버 확인

### 1. 헬스체크

```bash
curl http://localhost:8000/health
```

**응답**:
```json
{
  "status": "healthy",
  "service": "backend"
}
```

### 2. API 문서 확인

브라우저에서 접속:
```
http://localhost:8000/docs
```

Swagger UI가 표시되며, 모든 API 엔드포인트를 테스트할 수 있습니다.

### 3. 기본 엔드포인트 확인

```bash
curl http://localhost:8000/
```

**응답**:
```json
{
  "message": "Terraform & Ansible Control API",
  "status": "running"
}
```

---

## 디렉토리 구조 확인

백엔드가 정상적으로 작동하려면 다음과 유사한 디렉토리 구조가 필요합니다:

```
backend/
├── app/
│   ├── main.py
│   ├── domains/
│   │   ├── deploy/
│   │   │   └── router.py
│   │   ├── task/
│   │   │   └── router.py
│   │   ├── proxmox/
│   │   │   └── router.py
│   │   └── llm/
│   │       └── router.py
│   └── services/
│       ├── deployment/
│       │   └── service.py
│       ├── terraform_service.py
│       ├── ansible/
│       │   └── __init__.py
│       ├── proxmox/
│       │   └── __init__.py
│       ├── task/
│       │   └── manager.py
│       └── llm/
│           ├── llm_core.py
│           ├── service.py
│           └── infra_action_service.py
├── iac/
│   ├── terraform/
│   │   └── main.tf
│   └── ansible/
│       ├── playbook.yml
│       └── inventory.yml.example
└── venv/
```

---

## 문제 해결

### 1. 포트가 이미 사용 중인 경우

**에러 메시지**:
```
ERROR:    [Errno 48] Address already in use
```

**해결 방법**:
- 다른 포트 사용: `--port 8001`
- 기존 프로세스 종료: `lsof -ti:8000 | xargs kill`

### 2. 가상환경이 활성화되지 않는 경우

**에러 메시지**:
```
ModuleNotFoundError: No module named 'fastapi'
```

**해결 방법**:
```bash
# 가상환경 활성화 확인
which python  # venv/bin/python을 가리켜야 함

# 가상환경 재활성화
source venv/bin/activate

# 의존성 재설치
pip install -r requirements.txt
```

### 3. Proxmox API 연결 실패

**에러 메시지**:
```
서버 목록 조회 실패: Connection refused
```

**해결 방법**:
1. `.env` 파일의 `PROXMOX_API_URL` 확인
2. Proxmox 서버 접근 가능 여부 확인
3. API Token 권한 확인
4. `PROXMOX_TLS_INSECURE=true` 설정 (자체 서명 인증서 사용 시)

### 4. Terraform 명령어를 찾을 수 없는 경우

**에러 메시지**:
```
FileNotFoundError: [Errno 2] No such file or directory: 'terraform'
```

**해결 방법**:
1. Terraform 설치 확인: `terraform --version`
2. PATH 환경 변수에 Terraform 경로 추가

### 5. Ansible 명령어를 찾을 수 없는 경우

**에러 메시지**:
```
FileNotFoundError: [Errno 2] No such file or directory: 'ansible-playbook'
```

**해결 방법**:
1. Ansible 설치 확인: `ansible-playbook --version`
2. PATH 환경 변수에 Ansible 경로 추가

---

## 개발 모드

개발 중에는 `--reload` 옵션을 사용하여 코드 변경 시 자동으로 서버가 재시작됩니다:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**주의**: 프로덕션 환경에서는 `--reload` 옵션을 사용하지 마세요.

---

## 프로덕션 배포

프로덕션 환경에서는 다음을 고려하세요:

### 1. 프로세스 관리자 사용

**systemd 예시** (`/etc/systemd/system/backend.service`):
```ini
[Unit]
Description=Terraform Ansible Backend
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/terraform_ansible/backend
Environment="PATH=/path/to/terraform_ansible/backend/venv/bin"
ExecStart=/path/to/terraform_ansible/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**활성화**:
```bash
sudo systemctl enable backend
sudo systemctl start backend
sudo systemctl status backend
```

### 2. 리버스 프록시 사용

Nginx를 리버스 프록시로 사용:

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. 로그 관리

로그는 `backend.log` 파일에 저장되며, 로그 로테이션을 설정하세요:

```bash
# logrotate 설정 예시
/path/to/terraform_ansible/backend.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

---

## 환경 변수 상세

### 필수 환경 변수

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `PROXMOX_API_URL` | Proxmox API URL | `https://pve.example.com:8006/api2/json` |
| `PROXMOX_API_TOKEN_ID` | API Token ID | `user@pam!token-name` |
| `PROXMOX_API_TOKEN_SECRET` | API Token Secret | `uuid-secret-string` |

### 선택적 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `PROXMOX_TLS_INSECURE` | TLS 검증 비활성화 | `false` |
| `ANSIBLE_SSH_USER` | Ansible SSH 사용자 | `root` |
| `ANSIBLE_SSH_PRIVATE_KEY_FILE` | SSH 개인키 경로 | 없음 |
| `BACKEND_PORT` | 백엔드 서버 포트 | `8000` |
| `FRONTEND_PORT` | 프론트엔드 서버 포트 | `5173` |

---

## 다음 단계

- [01_OVERVIEW.md](./01_OVERVIEW.md) - 백엔드 개요로 돌아가기
- [프론트엔드 문서](../frontend/README.md) - 프론트엔드 연동 방법
