# 환경 변수 설정 가이드

이 문서는 Terraform, Ansible, Proxmox를 사용하는 프로젝트에서 필요한 환경 변수 설정 방법을 설명합니다.

## 📋 필수 환경 변수 목록

### 1. Proxmox API 설정 (조회용)

Proxmox API를 통해 리소스 정보를 조회하기 위한 설정입니다.

```bash
# Proxmox 서버의 API URL
PROXMOX_API_URL=https://proxmox.example.com:8006/api2/json

# Proxmox API Token ID
PROXMOX_API_TOKEN_ID=user@pam!token_name

# Proxmox API Token Secret
PROXMOX_API_TOKEN_SECRET=your_token_secret_here

# TLS 인증서 검증 비활성화 (자체 서명 인증서 사용 시)
PROXMOX_TLS_INSECURE=false
```

**Proxmox API Token 생성 방법:**
1. Proxmox 웹 UI 접속
2. `Datacenter` > `Permissions` > `API Tokens` 이동
3. `Add` 클릭하여 새 Token 생성
4. Token ID와 Secret 복사하여 `.env` 파일에 입력

### 2. Terraform 설정 (제어용)

Terraform은 `TF_VAR_` 접두사를 가진 환경변수를 자동으로 읽습니다.
`run.sh` 스크립트가 자동으로 변환하므로 별도 설정이 필요 없습니다.

**자동 변환:**
- `PROXMOX_API_URL` → `TF_VAR_proxmox_api_url`
- `PROXMOX_API_TOKEN_ID` → `TF_VAR_proxmox_api_token_id`
- `PROXMOX_API_TOKEN_SECRET` → `TF_VAR_proxmox_api_token_secret`
- `PROXMOX_TLS_INSECURE` → `TF_VAR_proxmox_tls_insecure`

### 3. Ansible 설정

생성된 VM에 Ansible이 접속하여 설정을 적용하기 위한 SSH 설정입니다.

```bash
# SSH 접속 사용자명
ANSIBLE_SSH_USER=root

# SSH 개인키 파일 경로
ANSIBLE_SSH_PRIVATE_KEY_FILE=~/.ssh/id_rsa
```

**SSH 키 설정 방법:**
1. SSH 키가 없으면 생성:
   ```bash
   ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa
   ```

2. 공개키를 VM에 복사 (Cloud-init 또는 수동):
   ```bash
   ssh-copy-id -i ~/.ssh/id_rsa.pub root@vm-ip
   ```

### 4. 서버 포트 설정

```bash
# 백엔드 서버 바인딩 주소
BACKEND_HOST=0.0.0.0

# 백엔드 서버 포트
BACKEND_PORT=8000

# 프론트엔드 포트 (CORS 설정에 사용)
FRONTEND_PORT=5173
```

### 5. LLM / Gemini 설정

LLM 기반 자연어 채팅 탭에서 Google Gemini API를 사용하기 위한 설정입니다.

```bash
# Gemini API 키 (필수)
GEMINI_API_KEY=your_gemini_api_key_here

# 사용할 Gemini 모델명 (선택, 기본값 예: gemini-2.0-flash)
GEMINI_MODEL_NAME=gemini-2.0-flash

# LLM 호출 타임아웃 (초, 선택)
GEMINI_TIMEOUT_SECONDS=30
```

위 값들은 백엔드에서 LLM을 호출할 때만 사용되며,
VM 이름/스펙/상태 같은 **메타데이터 수준의 정보만** LLM API로 전달되도록 설계할 수 있습니다.

### 6. Redis 설정 (대화 이력 저장)

LLM 채팅의 대화 이력을 영구 저장하기 위한 Redis 설정입니다.
Redis가 없어도 동작하지만, 페이지 새로고침 시 대화 이력이 사라집니다.

```bash
# Redis 서버 주소 (선택, 기본값: localhost)
REDIS_HOST=localhost

# Redis 서버 포트 (선택, 기본값: 6379)
REDIS_PORT=6379

# Redis 데이터베이스 번호 (선택, 기본값: 0)
REDIS_DB=0

# Redis 비밀번호 (선택, 비밀번호가 없으면 생략)
REDIS_PASSWORD=

# 채팅 세션 만료 시간 (초, 선택, 기본값: 604800 = 7일)
CHAT_SESSION_TTL_SECONDS=604800

# 최대 저장 메시지 수 (선택, 기본값: 100)
CHAT_MAX_MESSAGES=100
```

### 7. IP 풀 설정 (VM IP 자동 할당)

VM 생성 시 고정 IP를 자동 할당하기 위한 IP 풀 설정입니다.
설정하지 않으면 수동으로 IP를 입력해야 합니다.

```bash
# IP 풀 시작 주소
IP_POOL_START=192.168.1.100

# IP 풀 끝 주소
IP_POOL_END=192.168.1.200

# 게이트웨이 주소
IP_GATEWAY=192.168.1.1

# 서브넷 마스크 (CIDR 형식, 선택, 기본값: 24)
IP_SUBNET=24
```

**동작 방식:**
- "Auto Assign" 버튼 클릭 시 IP 풀에서 사용 가능한 IP를 찾습니다
- ping으로 각 IP의 사용 여부를 확인합니다
- 사용 중이 아닌 첫 번째 IP를 자동으로 할당합니다

**Redis 설치 방법 (macOS):**
```bash
# Homebrew로 설치
brew install redis

# Redis 서버 시작
brew services start redis
# 또는 수동 실행: redis-server
```

**Redis 설치 방법 (Linux):**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install redis-server

# Redis 서버 시작
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**Redis 없이 사용:**
- Redis가 설정되지 않아도 LLM 채팅은 정상 동작합니다.
- 다만 페이지 새로고침 시 대화 이력이 사라집니다.
- Redis 연결 실패 시 자동으로 비활성화되고 경고 메시지만 출력됩니다.

## 🚀 설정 방법

### 1. 환경 파일 생성

```bash
# 프로젝트 루트에서
touch .env
```

### 2. 환경 파일 편집

```bash
# .env 파일을 열어서 실제 값으로 수정
nano .env
# 또는
vim .env
```

### 3. 필수 항목 확인

다음 항목들은 반드시 실제 값으로 설정해야 합니다:

- ✅ `PROXMOX_API_URL`: 실제 Proxmox 서버 주소
- ✅ `PROXMOX_API_TOKEN_ID`: 실제 Token ID
- ✅ `PROXMOX_API_TOKEN_SECRET`: 실제 Token Secret
- ✅ `ANSIBLE_SSH_PRIVATE_KEY_FILE`: 실제 SSH 키 경로

### 4. 선택 항목

다음 항목들은 기본값으로도 동작하지만, 환경에 맞게 조정할 수 있습니다:

- `PROXMOX_TLS_INSECURE`: 자체 서명 인증서 사용 시 `true`
- `ANSIBLE_SSH_USER`: 기본값 `root`
- `BACKEND_PORT`: 기본값 `8000`
- `FRONTEND_PORT`: 기본값 `5173`

## 🔒 보안 주의사항

1. **`.env` 파일은 절대 Git에 커밋하지 마세요**
   - `.gitignore`에 이미 포함되어 있습니다
   - 민감한 정보(API Token, Secret)가 포함되어 있습니다

2. **SSH 키 권한 확인**
   ```bash
   chmod 600 ~/.ssh/id_rsa
   ```

3. **프로덕션 환경에서는 TLS 검증 활성화**
   ```bash
   PROXMOX_TLS_INSECURE=false
   ```

## ✅ 설정 확인

### Proxmox 연결 테스트

```bash
# 백엔드 실행 후 API 테스트
curl http://localhost:8000/api/servers
```

### Terraform 변수 확인

```bash
# run.sh 실행 시 자동으로 변환되는지 확인
./run.sh
# 로그에서 "Terraform 변수:" 메시지 확인
```

### Ansible SSH 접속 테스트

```bash
# VM 생성 후 SSH 접속 테스트
ssh -i ~/.ssh/id_rsa root@vm-ip
```

## 📝 환경 변수 체크리스트

배포 전 다음 항목들을 확인하세요:

- [ ] `.env` 파일 생성 완료
- [ ] `PROXMOX_API_URL` 실제 주소로 설정
- [ ] `PROXMOX_API_TOKEN_ID` 실제 Token ID로 설정
- [ ] `PROXMOX_API_TOKEN_SECRET` 실제 Secret로 설정
- [ ] `ANSIBLE_SSH_PRIVATE_KEY_FILE` 실제 키 경로로 설정
- [ ] SSH 키 권한 확인 (`chmod 600`)
- [ ] Proxmox API 연결 테스트 성공
- [ ] `.env` 파일이 `.gitignore`에 포함되어 있는지 확인
- [ ] (선택) Redis 설치 및 실행 확인 (대화 이력 영구 저장용)

## 🆘 문제 해결

### Proxmox API 연결 실패

```bash
# TLS 검증 비활성화 (자체 서명 인증서 사용 시)
PROXMOX_TLS_INSECURE=true
```

### Terraform 변수 인식 안 됨

```bash
# run.sh가 자동으로 변환하는지 확인
# 또는 수동으로 export:
export TF_VAR_proxmox_api_url="${PROXMOX_API_URL}"
export TF_VAR_proxmox_api_token_id="${PROXMOX_API_TOKEN_ID}"
export TF_VAR_proxmox_api_token_secret="${PROXMOX_API_TOKEN_SECRET}"
```

### Ansible SSH 접속 실패

```bash
# SSH 키 경로 확인
ls -la ~/.ssh/id_rsa

# SSH 키 권한 확인
chmod 600 ~/.ssh/id_rsa

# VM에 공개키 복사 확인
ssh-copy-id -i ~/.ssh/id_rsa.pub root@vm-ip
```
