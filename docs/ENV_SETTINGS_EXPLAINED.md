# 환경 변수 설정 상세 설명

이 문서는 `env.example` 파일의 Terraform과 Ansible 설정 부분에 대한 상세한 설명입니다.

## 📋 설정 항목 (22-46번 라인)

### 1. Terraform 설정 (23-32번 라인)

```bash
# ============================================
# Terraform 설정 (제어용)
# ============================================
# 주의: Terraform은 TF_VAR_ 접두사를 가진 환경변수를 자동으로 읽습니다.
# run.sh 스크립트가 자동으로 변환하므로, 아래 변수들은 설정하지 않아도 됩니다.
# (PROXMOX_API_URL, PROXMOX_API_TOKEN_ID, PROXMOX_API_TOKEN_SECRET가 자동 변환됨)

# Terraform TLS 검증 설정 (선택사항)
# PROXMOX_TLS_INSECURE와 동일한 값 사용
# TF_VAR_proxmox_tls_insecure=false
```

#### 🔍 설명

**자동 변환 메커니즘:**
- `run.sh` 스크립트가 `.env` 파일을 읽어서 자동으로 Terraform 변수로 변환합니다
- 별도로 `TF_VAR_` 접두사를 붙여서 설정할 필요가 없습니다

**자동 변환되는 변수들:**
```bash
# .env 파일에 이렇게 설정하면:
PROXMOX_API_URL=https://192.168.2.11:8006/api2/json
PROXMOX_API_TOKEN_ID=root@pam!terraform-admin
PROXMOX_API_TOKEN_SECRET=your-secret

# run.sh가 자동으로 이렇게 변환:
export TF_VAR_proxmox_api_url="https://192.168.2.11:8006/api2/json"
export TF_VAR_proxmox_api_token_id="root@pam!terraform-admin"
export TF_VAR_proxmox_api_token_secret="your-secret"
```

**Terraform이 환경변수를 읽는 방식:**
- Terraform은 `TF_VAR_` 접두사가 붙은 환경변수를 자동으로 변수로 인식합니다
- 예: `TF_VAR_proxmox_api_url` → Terraform의 `var.proxmox_api_url` 변수

**TLS 검증 설정 (선택사항):**
```bash
# 주석 처리되어 있음 (기본값 사용)
# TF_VAR_proxmox_tls_insecure=false

# 필요시 주석 해제하고 설정:
TF_VAR_proxmox_tls_insecure=true
```

**실제 사용 예시:**
```bash
# 1. .env 파일에 Proxmox 설정만 입력
PROXMOX_API_URL=https://192.168.2.11:8006/api2/json
PROXMOX_API_TOKEN_ID=root@pam!terraform-admin
PROXMOX_API_TOKEN_SECRET=your-secret
PROXMOX_TLS_INSECURE=true

# 2. run.sh 실행 시 자동 변환됨
./run.sh

# 3. Terraform이 자동으로 변수 읽음
# terraform apply 실행 시 자동으로 사용됨
```

---

### 2. Ansible 설정 (34-45번 라인)

```bash
# ============================================
# Ansible 설정
# ============================================
# SSH 접속 사용자명
# 생성된 VM에 Ansible이 접속할 때 사용하는 사용자
# 일반적으로 root 또는 sudo 권한이 있는 사용자
ANSIBLE_SSH_USER=root

# SSH 개인키 파일 경로
# VM에 SSH 접속할 때 사용할 개인키
# 절대 경로 또는 ~/.ssh/id_rsa 형식 사용 가능
ANSIBLE_SSH_PRIVATE_KEY_FILE=~/.ssh/id_rsa
```

#### 🔍 설명

**ANSIBLE_SSH_USER:**
- **용도**: 생성된 VM에 Ansible이 SSH로 접속할 때 사용하는 사용자명
- **기본값**: `root`
- **설정 방법**: 
  ```bash
  # root 사용자 (권장)
  ANSIBLE_SSH_USER=root
  
  # 다른 사용자 (sudo 권한 필요)
  ANSIBLE_SSH_USER=ubuntu
  ANSIBLE_SSH_USER=admin
  ```

**ANSIBLE_SSH_PRIVATE_KEY_FILE:**
- **용도**: VM에 SSH 접속할 때 사용할 개인키 파일 경로
- **기본값**: `~/.ssh/id_rsa`
- **설정 방법**:
  ```bash
  # 홈 디렉토리 기준 (권장)
  ANSIBLE_SSH_PRIVATE_KEY_FILE=~/.ssh/id_rsa
  
  # 절대 경로
  ANSIBLE_SSH_PRIVATE_KEY_FILE=/home/user/.ssh/id_rsa
  
  # 다른 키 파일
  ANSIBLE_SSH_PRIVATE_KEY_FILE=~/.ssh/proxmox_key
  ```

#### 🛠️ SSH 키 설정 방법

**1. SSH 키가 없는 경우 생성:**
```bash
# RSA 키 생성 (4096비트 권장)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa

# 또는 ED25519 키 생성 (더 안전)
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519
```

**2. 공개키를 VM에 복사:**
```bash
# 방법 1: ssh-copy-id 사용 (권장)
ssh-copy-id -i ~/.ssh/id_rsa.pub root@vm-ip-address

# 방법 2: 수동 복사
cat ~/.ssh/id_rsa.pub | ssh root@vm-ip-address "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

# 방법 3: Cloud-init 사용 (자동화)
# 템플릿에 공개키가 이미 포함되어 있으면 자동으로 설정됨
```

**3. SSH 키 권한 확인:**
```bash
# 개인키 권한 확인 (600이어야 함)
chmod 600 ~/.ssh/id_rsa

# 디렉토리 권한 확인 (700이어야 함)
chmod 700 ~/.ssh
```

#### 📝 실제 사용 예시

**시나리오 1: 기본 설정 (root 사용자)**
```bash
# .env 파일
ANSIBLE_SSH_USER=root
ANSIBLE_SSH_PRIVATE_KEY_FILE=~/.ssh/id_rsa

# SSH 키 생성 및 복사
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa
ssh-copy-id -i ~/.ssh/id_rsa.pub root@vm-ip
```

**시나리오 2: Ubuntu 사용자 (sudo 권한)**
```bash
# .env 파일
ANSIBLE_SSH_USER=ubuntu
ANSIBLE_SSH_PRIVATE_KEY_FILE=~/.ssh/id_rsa

# SSH 키 복사
ssh-copy-id -i ~/.ssh/id_rsa.pub ubuntu@vm-ip
```

**시나리오 3: 커스텀 키 파일**
```bash
# .env 파일
ANSIBLE_SSH_USER=root
ANSIBLE_SSH_PRIVATE_KEY_FILE=~/.ssh/proxmox_deploy_key

# 커스텀 키 생성
ssh-keygen -t rsa -b 4096 -f ~/.ssh/proxmox_deploy_key
ssh-copy-id -i ~/.ssh/proxmox_deploy_key.pub root@vm-ip
```

---

## 🔄 전체 워크플로우

### 1. 환경 변수 설정
```bash
# .env 파일 생성
cp env.example .env

# .env 파일 편집
nano .env
```

### 2. 필수 항목 설정
```bash
# Proxmox 설정 (자동으로 Terraform 변수로 변환됨)
PROXMOX_API_URL=https://192.168.2.11:8006/api2/json
PROXMOX_API_TOKEN_ID=root@pam!terraform-admin
PROXMOX_API_TOKEN_SECRET=your-secret

# Ansible 설정
ANSIBLE_SSH_USER=root
ANSIBLE_SSH_PRIVATE_KEY_FILE=~/.ssh/id_rsa
```

### 3. SSH 키 준비
```bash
# 키 생성 (없는 경우)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa

# 권한 설정
chmod 600 ~/.ssh/id_rsa
chmod 700 ~/.ssh
```

### 4. 실행
```bash
# run.sh 실행 (자동으로 환경변수 로드 및 변환)
./run.sh
```

---

## ❓ 자주 묻는 질문

### Q1: Terraform 변수를 직접 설정해야 하나요?
**A:** 아니요. `run.sh`가 자동으로 변환하므로 `.env` 파일에 Proxmox 설정만 하면 됩니다.

### Q2: SSH 키가 없으면 어떻게 하나요?
**A:** `ssh-keygen` 명령어로 생성하세요:
```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa
```

### Q3: VM에 SSH 접속이 안 되면?
**A:** 다음을 확인하세요:
- SSH 키 권한: `chmod 600 ~/.ssh/id_rsa`
- 공개키가 VM에 복사되었는지 확인
- VM의 SSH 서비스가 실행 중인지 확인

### Q4: 다른 사용자로 접속하려면?
**A:** `ANSIBLE_SSH_USER`를 변경하고 해당 사용자에게 공개키를 복사하세요:
```bash
ANSIBLE_SSH_USER=ubuntu
ssh-copy-id -i ~/.ssh/id_rsa.pub ubuntu@vm-ip
```

### Q5: 여러 개의 SSH 키를 사용하려면?
**A:** 각 키 파일에 대해 별도로 설정하거나, SSH config 파일을 사용하세요:
```bash
ANSIBLE_SSH_PRIVATE_KEY_FILE=~/.ssh/proxmox_key
```

---

## ✅ 체크리스트

설정 완료 후 확인사항:

- [ ] `.env` 파일에 Proxmox API 정보 입력 완료
- [ ] `ANSIBLE_SSH_USER` 설정 완료
- [ ] `ANSIBLE_SSH_PRIVATE_KEY_FILE` 경로 확인
- [ ] SSH 키 파일 존재 확인 (`ls -la ~/.ssh/id_rsa`)
- [ ] SSH 키 권한 확인 (`chmod 600 ~/.ssh/id_rsa`)
- [ ] 공개키가 VM에 복사되었는지 확인
- [ ] `run.sh` 실행 시 자동 변환 확인
