# 템플릿 준비 가이드 (원클릭 설정을 위해)

원클릭으로 VM을 생성하고 설정하려면, **템플릿 생성 전에 SSH 키를 준비**해야 합니다.

## 🎯 목표: 완전 자동화

```
웹에서 배포 버튼 클릭
  ↓
VM 자동 생성
  ↓
Ansible 자동 실행 (SSH 접속 자동)
  ↓
패키지/역할 자동 설치
  ↓
완료! (수동 작업 없음)
```

## 📋 템플릿 생성 전 준비사항

### 1. SSH 키 쌍 생성 (한 번만)

```bash
# SSH 키 생성 (없는 경우)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa

# 권한 설정
chmod 600 ~/.ssh/id_rsa
chmod 700 ~/.ssh
```

**중요:** 이 키는:
- **개인키**: Ansible이 사용 (`ANSIBLE_SSH_PRIVATE_KEY_FILE`)
- **공개키**: 템플릿에 포함 (VM에 자동 설정)

### 2. 공개키 확인

```bash
# 공개키 내용 확인
cat ~/.ssh/id_rsa.pub

# 출력 예시:
# ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQC... user@host
```

### 3. 템플릿 VM 생성 및 설정

#### Step 1: VM 생성
```bash
# Proxmox 웹 UI에서:
# 1. Create VM 클릭
# 2. OS 설치 (Ubuntu, Debian 등)
# 3. 기본 설정 완료
```

#### Step 2: SSH 키 추가
```bash
# VM에 접속 (비밀번호로)
ssh root@template-vm-ip

# 공개키를 authorized_keys에 추가
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "ssh-rsa AAAAB3NzaC1yc2E..." >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# SSH 서비스 확인
systemctl status ssh
```

#### Step 3: 템플릿으로 변환
```bash
# Proxmox 웹 UI:
# VM > More > Convert to Template

# 또는 CLI:
qm template <vmid>
```

### 4. 환경 변수 설정

```bash
# .env 파일
ANSIBLE_SSH_USER=root
ANSIBLE_SSH_PRIVATE_KEY_FILE=~/.ssh/id_rsa
```

## ✅ 완료 후 동작

템플릿 준비가 완료되면:

1. **웹에서 템플릿 선택**
2. **배포 버튼 클릭**
3. **자동 완료!**
   - VM 자동 생성
   - SSH 자동 접속 (템플릿에 키 포함)
   - 패키지 자동 설치
   - 역할 자동 적용

## 🔄 더 나은 방법: Cloud-init 사용

템플릿에 SSH 키를 미리 포함시키는 대신, **Cloud-init으로 VM 생성 시 자동 주입**할 수 있습니다.

### Cloud-init 방식의 장점

- ✅ 템플릿에 SSH 키 포함 불필요
- ✅ 동적으로 SSH 키 주입 가능
- ✅ 더 유연한 설정

### Cloud-init 구현 (향후 추가 가능)

현재는 템플릿에 SSH 키를 포함하는 방식을 사용하지만, Cloud-init으로 자동 주입하는 기능을 추가할 수 있습니다.

---

## 📝 체크리스트

템플릿 생성 전:

- [ ] SSH 키 쌍 생성 (`~/.ssh/id_rsa`)
- [ ] 공개키 내용 확인 (`cat ~/.ssh/id_rsa.pub`)
- [ ] 템플릿 VM 생성 및 OS 설치
- [ ] 공개키를 템플릿 VM에 추가
- [ ] 템플릿으로 변환
- [ ] `.env` 파일에 SSH 키 경로 설정
- [ ] 테스트: 템플릿에서 VM 생성 후 SSH 접속 확인

---

## 🆘 문제 해결

### SSH 접속이 안 되면?

1. **템플릿에 키가 포함되었는지 확인:**
   ```bash
   # 템플릿에서 VM 생성 후
   ssh root@new-vm-ip
   # → 비밀번호 없이 접속되어야 함
   ```

2. **공개키 형식 확인:**
   ```bash
   # 올바른 형식:
   ssh-rsa AAAAB3NzaC1yc2E... user@host
   
   # 잘못된 형식 (공백, 줄바꿈 등):
   ssh-rsa AAAAB3NzaC1yc2E...
   user@host
   ```

3. **권한 확인:**
   ```bash
   # 템플릿 VM에서
   ls -la ~/.ssh/authorized_keys
   # → -rw------- (600) 이어야 함
   ```

---

## 💡 요약

**원클릭 설정을 위해:**

1. ✅ **템플릿 생성 전에 SSH 키 준비 필요**
2. ✅ **공개키를 템플릿에 포함**
3. ✅ **개인키는 `.env`에 설정**
4. ✅ **이후 완전 자동화 가능**

**한 번만 준비하면, 이후 모든 VM에서 자동으로 작동합니다!**
