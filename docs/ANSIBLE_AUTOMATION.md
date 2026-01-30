# Ansible 자동화 동작 방식

## 🔄 자동화 워크플로우

Ansible은 **자동으로 실행**되며, VM에 수동으로 접속할 필요가 없습니다.

### 1. 전체 프로세스

```
1. Terraform으로 VM 생성
   ↓
2. Terraform Output에서 IP 주소 추출
   ↓
3. Ansible이 자동으로 IP로 SSH 접속
   ↓
4. 선택한 패키지/역할 자동 설치
   ↓
5. 완료 (수동 작업 불필요)
```

### 2. 자동 실행 과정

**Step 1: Terraform VM 생성**
```bash
# Terraform이 Proxmox에 VM 생성
terraform apply
# → VM 생성 완료, IP 주소 획득
```

**Step 2: IP 주소 추출**
```python
# deployment_service.py에서 자동으로 실행
terraform_outputs = terraform_service.get_output()
vm_ip = terraform_outputs["vm_ip"]  # 예: "192.168.1.100"
```

**Step 3: Ansible Inventory 자동 생성**
```yaml
# ansible_service.py가 자동으로 생성
# inventory.yml
all:
  children:
    proxmox_vms:
      hosts:
        proxmox_vm:
          ansible_host: 192.168.1.100
          ansible_user: root
          ansible_ssh_private_key_file: ~/.ssh/id_rsa
```

**Step 4: Ansible Playbook 자동 실행**
```bash
# ansible_service.py가 자동으로 실행
ansible-playbook -i inventory.yml playbook.yml \
  -e '{"packages_to_install": ["curl", "git"], "roles_to_apply": ["docker"]}'
```

**Step 5: 패키지/역할 자동 설치**
- 선택한 패키지 자동 설치
- 선택한 역할 자동 적용
- 모든 작업이 자동으로 완료됨

---

## ⚠️ 중요: SSH 접속 가능해야 함

Ansible이 자동으로 실행되려면 **SSH 접속이 가능해야 합니다**.

### SSH 접속이 가능한 경우

#### ✅ 템플릿 사용 시 (권장)

**Cloud-init으로 SSH 키 자동 설정:**
1. 템플릿 생성 시 공개키를 포함
2. VM 클론 시 자동으로 SSH 키 설정됨
3. Ansible이 즉시 접속 가능

**템플릿 준비 방법:**
```bash
# 1. VM 생성 및 OS 설치
# 2. 공개키를 authorized_keys에 추가
echo "ssh-rsa AAAAB3..." >> ~/.ssh/authorized_keys

# 3. VM을 템플릿으로 변환
# Proxmox 웹 UI: VM > More > Convert to Template
```

#### ⚠️ ISO 사용 시 (수동 작업 필요)

**ISO로 VM 생성 시:**
1. VM 생성 후 VNC 콘솔로 접속
2. OS 수동 설치
3. SSH 서비스 시작
4. 공개키를 VM에 복사 (수동)

**수동 설정 방법:**
```bash
# 1. VM에 SSH 접속 (비밀번호로)
ssh root@vm-ip

# 2. 공개키 복사
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "ssh-rsa AAAAB3..." >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# 3. 이후 Ansible이 자동으로 접속 가능
```

---

## 📋 실제 사용 시나리오

### 시나리오 1: 템플릿 사용 (완전 자동화)

```bash
# 1. 템플릿 선택 (프론트엔드)
template_id: "pve-node-01/100"

# 2. 배포 시작
# → Terraform: VM 생성 (자동)
# → Ansible: 패키지 설치 (자동)
# → 완료! (수동 작업 없음)
```

**결과:**
- ✅ VM 자동 생성
- ✅ SSH 접속 자동 설정 (템플릿에 포함)
- ✅ 패키지 자동 설치
- ✅ 역할 자동 적용
- ✅ **수동 작업 불필요**

### 시나리오 2: ISO 사용 (부분 자동화)

```bash
# 1. ISO 선택 (프론트엔드)
iso_image_id: "local:iso/ubuntu-22.04.iso"

# 2. 배포 시작
# → Terraform: VM 생성 (자동)
# → ⚠️ OS 수동 설치 필요 (VNC 콘솔)
# → ⚠️ SSH 키 수동 복사 필요
# → 이후 Ansible: 패키지 설치 (자동)
```

**결과:**
- ✅ VM 자동 생성
- ⚠️ OS 수동 설치 필요
- ⚠️ SSH 키 수동 복사 필요
- ✅ 이후 패키지 자동 설치
- ✅ 이후 역할 자동 적용

---

## 🔧 SSH 키 설정 방법

### 방법 1: 템플릿에 포함 (권장)

**템플릿 생성 시:**
```bash
# VM에 접속
ssh root@template-vm-ip

# 공개키 추가
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# 템플릿으로 변환
# Proxmox 웹 UI: VM > More > Convert to Template
```

**장점:**
- 이후 모든 VM에서 자동으로 SSH 접속 가능
- 수동 작업 불필요

### 방법 2: Cloud-init 사용

**Terraform에서 Cloud-init 설정:**
```hcl
# main.tf
cicustom = "user=${var.cloudinit_user_data}"
```

**user-data 예시:**
```yaml
#cloud-config
users:
  - name: root
    ssh-authorized-keys:
      - ssh-rsa AAAAB3NzaC1yc2E...
```

**장점:**
- VM 생성 시 자동으로 SSH 키 설정
- 템플릿 없이도 자동화 가능

### 방법 3: 수동 복사 (ISO 사용 시)

**VM 생성 후:**
```bash
# 공개키 복사
ssh-copy-id -i ~/.ssh/id_rsa.pub root@vm-ip

# 또는 수동
cat ~/.ssh/id_rsa.pub | ssh root@vm-ip \
  "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

---

## ❓ 자주 묻는 질문

### Q1: Ansible이 자동으로 실행되나요?
**A:** 네, 자동으로 실행됩니다. VM 생성 후 자동으로 패키지와 역할이 설치됩니다.

### Q2: VM에 수동으로 접속해야 하나요?
**A:** 템플릿 사용 시: **아니요** (완전 자동화)
ISO 사용 시: **예** (OS 설치 및 SSH 키 복사 필요)

### Q3: SSH 키는 어떻게 설정하나요?
**A:** 
- 템플릿 사용: 템플릿에 포함되어 있으면 자동 설정
- ISO 사용: OS 설치 후 수동으로 복사 필요

### Q4: Ansible이 실패하면?
**A:** 프론트엔드 로그에서 확인 가능합니다. SSH 접속 실패 시:
- SSH 키가 VM에 복사되었는지 확인
- SSH 서비스가 실행 중인지 확인
- 방화벽 설정 확인

### Q5: 패키지 설치가 안 되면?
**A:** 
- VM에 인터넷 연결 확인
- 패키지 저장소 설정 확인
- 로그에서 에러 메시지 확인

---

## ✅ 체크리스트

### 템플릿 사용 시 (완전 자동화)
- [ ] 템플릿에 SSH 공개키 포함됨
- [ ] `.env`에 `ANSIBLE_SSH_USER` 설정
- [ ] `.env`에 `ANSIBLE_SSH_PRIVATE_KEY_FILE` 설정
- [ ] 배포 시작 → 자동 완료

### ISO 사용 시 (부분 자동화)
- [ ] VM 생성 완료
- [ ] OS 수동 설치 완료
- [ ] SSH 서비스 시작됨
- [ ] 공개키를 VM에 복사 완료
- [ ] 이후 Ansible 자동 실행

---

## 📝 요약

**Ansible은 자동으로 실행됩니다!**

- ✅ VM 생성 후 자동으로 패키지/역할 설치
- ✅ 수동으로 VM에 접속할 필요 없음 (템플릿 사용 시)
- ⚠️ SSH 접속만 가능하면 자동화 완료
- ⚠️ ISO 사용 시 OS 설치 및 SSH 키 복사만 수동 작업 필요

**권장: 템플릿 사용으로 완전 자동화**
