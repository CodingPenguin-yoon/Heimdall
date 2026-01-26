# Ansible GitLab 배포 가이드 및 트러블슈팅

## 개요
이 문서는 Ansible을 사용하여 GitLab CE 서버와 GitLab Runner를 배포하는 과정에서 발생한 문제들과 해결 방법을 정리한 것입니다.

**환경:**
- Ansible: 2.19.4
- 대상 OS: Ubuntu (Cloud-init으로 생성된 VM)
- GitLab CE: 최신 버전
- GitLab Runner: 최신 버전

**배포 대상:**
- GitLab 서버: 192.168.2.98
- GitLab Runner: 192.168.2.97

---

## 배포 전 준비 작업

### 1. SSH 키 생성 및 설정

#### 문제: SSH 인증 정보 없이 접속 불가

**해결:**
```bash
# SSH 키 생성
ssh-keygen -t ed25519 -f ~/.ssh/terraform_ssh -N "" -C "terraform-ansible"

# 생성된 키 확인
ls -la ~/.ssh/terraform_ssh*
```

**결과:**
- 개인키: `~/.ssh/terraform_ssh` (로컬에 보관)
- 공개키: `~/.ssh/terraform_ssh.pub` (VM에 주입)

#### Terraform에서 SSH 키 자동 주입

**설정:**
```hcl
# terraform.tfvars
ssh_public_key_path = "/Users/yoon/.ssh/terraform_ssh.pub"
```

```hcl
# main.tf
sshkeys = coalesce(each.value.sshkeys, try(file(var.ssh_public_key_path), ""))
```

**동작:**
1. Terraform이 공개키를 읽음
2. Cloud-init을 통해 VM 생성 시 자동 주입
3. `~/.ssh/authorized_keys`에 추가됨

#### Ansible에서 SSH 키 사용

**설정:**
```ini
# inventory.ini
ansible_user=yoon
ansible_ssh_private_key_file=/Users/yoon/.ssh/terraform_ssh
```

**중요:** 절대 경로 사용 (Ansible은 `~` 경로를 해석하지 못함)

---

### 2. Ansible Inventory 설정

**파일 구조:**
```ini
# inventory.ini
[gitlab_server]
192.168.2.98

[gitlab_runner]
192.168.2.97

[all:vars]
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
ansible_user=yoon
ansible_ssh_private_key_file=/Users/yoon/.ssh/terraform_ssh
```

**설명:**
- `StrictHostKeyChecking=no`: 처음 연결 시 호스트 키 체크 비활성화
- `ansible_user`: SSH 접속 사용자명
- `ansible_ssh_private_key_file`: SSH 개인키 경로 (절대 경로 필수)

---

## Playbook 구조

### 파일 구조

```
ansible_test/
├── inventory.ini              # 인벤토리 파일
├── deploy_gitlab.yml          # 통합 playbook
├── deploy_gitlab_server.yml   # GitLab 서버 설치
└── deploy_gitlab_runner.yml  # GitLab Runner 설치
```

### 통합 Playbook

```yaml
# deploy_gitlab.yml
---
- import_playbook: deploy_gitlab_server.yml
- import_playbook: deploy_gitlab_runner.yml
```

**사용법:**
```bash
ansible-playbook -i inventory.ini deploy_gitlab.yml
```

---

## 문제 1: Ansible Playbook YAML 문법 오류

### 증상
```bash
[ERROR]: YAML parsing failed: Expected a single document in the stream but found another document.
Origin: deploy_gitlab.yml:5:1
```

### 원인
- 여러 play를 하나의 파일에 `---`로 구분하여 작성
- Ansible 2.19.4에서 여러 문서를 지원하지 않음
- 주석이 `---` 앞에 있어서 YAML 파서가 혼란

### 해결 방법

#### 방법 1: 파일 분리 (권장)

**deploy_gitlab_server.yml:**
```yaml
---
# Play: GitLab 서버 설치
- name: Deploy GitLab CE Server
  hosts: gitlab_server
  # ... tasks ...
```

**deploy_gitlab_runner.yml:**
```yaml
---
# Play: GitLab Runner 설치
- name: Deploy GitLab Runner
  hosts: gitlab_runner
  # ... tasks ...
```

**통합 playbook:**
```yaml
---
- import_playbook: deploy_gitlab_server.yml
- import_playbook: deploy_gitlab_runner.yml
```

**장점:**
- 각 playbook을 독립적으로 실행 가능
- 문법 오류 없음
- 유지보수 용이

#### 방법 2: 단일 파일 사용 (비권장)

```yaml
---
- name: Deploy GitLab CE Server
  hosts: gitlab_server
  # ... tasks ...

- name: Deploy GitLab Runner
  hosts: gitlab_runner
  # ... tasks ...
```

**주의:** 주석을 `---` 뒤에 배치해야 함

---

## 문제 2: 필수 패키지 누락

### 증상
```bash
# GitLab 저장소 추가 시 오류
E: The repository 'https://packages.gitlab.com/...' is not signed.
```

### 원인
- `gnupg` 패키지가 설치되지 않음
- GPG 키 검증을 위한 필수 패키지 누락

### 해결 방법

**GitLab 서버:**
```yaml
- name: 1. Install prerequisites
  apt:
    name:
      - curl          # 패키지 다운로드용
      - ca-certificates  # SSL 인증서 검증용
      - gnupg         # 패키지 저장소 GPG 키 검증용 (필수)
      - openssh-server  # SSH 서버 (권장)
      - postfix       # 이메일 발송용 (선택사항)
    state: present
    update_cache: yes
```

**GitLab Runner:**
```yaml
- name: 1. Install prerequisites
  apt:
    name:
      - curl
      - ca-certificates
      - gnupg         # 필수
    state: present
    update_cache: yes
```

**핵심 포인트:**
- `gnupg`는 GitLab 공식 저장소 추가 시 필수
- GPG 키 검증에 사용됨
- 없으면 저장소 추가 실패

---

## 문제 3: external_url 설정 타이밍

### 증상
```bash
# external_url 설정 후 reconfigure 실행했는데 적용 안 됨
```

### 원인
- GitLab CE 설치 시 자동으로 `gitlab-ctl reconfigure` 실행
- 설치 완료 전에 설정 파일이 생성되지 않음
- 설정 파일이 없으면 `lineinfile` 모듈이 실패

### 해결 방법

**설정 파일 생성 대기 추가:**
```yaml
- name: 3. Install GitLab CE
  apt:
    name: gitlab-ce
    state: present

- name: 4. Wait for GitLab configuration file
  wait_for:
    path: /etc/gitlab/gitlab.rb
    state: present
    timeout: 60

- name: 5. Configure external_url
  lineinfile:
    path: /etc/gitlab/gitlab.rb
    regexp: "^#?external_url"
    line: "external_url '{{ gitlab_external_url }}'"
    backup: yes
  notify: Run gitlab-ctl reconfigure
```

**핵심 포인트:**
- `wait_for` 모듈로 설정 파일 생성 대기
- `timeout: 60`으로 최대 60초 대기
- 파일이 생성된 후에만 설정 변경

---

## 문제 4: stat lookup 플러그인 오류

### 증상
```bash
[ERROR]: The lookup plugin 'stat' was not found.
```

### 원인
- `stat` lookup 플러그인을 사용하려고 시도
- Ansible 버전에 따라 지원되지 않을 수 있음
- 복잡한 조건문 사용

### 해결 방법

**복잡한 조건 제거:**
```yaml
# 이전 (오류 발생)
- name: Wait for config file
  wait_for:
    path: /etc/gitlab/gitlab.rb
    state: present
  when: not (stat_result.stat.exists is defined and stat_result.stat.exists)
  vars:
    stat_result: "{{ lookup('stat', '/etc/gitlab/gitlab.rb') }}"

# 수정 후 (간단하고 안정적)
- name: Wait for config file
  wait_for:
    path: /etc/gitlab/gitlab.rb
    state: present
    timeout: 60
```

**핵심 포인트:**
- `wait_for` 모듈은 파일이 없으면 자동으로 대기
- 복잡한 조건문 불필요
- 간단한 코드가 더 안정적

---

## 문제 5: 환경변수 관리 복잡도

### 초기 접근 (복잡함)

**문제:**
- `.env` 파일 생성
- `terraform.sh` 스크립트 생성
- `export` 사용으로 셸 세션 전체에 환경변수 설정
- 다른 Terraform 프로젝트와 충돌 가능

**해결:**
- `terraform.tfvars`에 직접 값 입력
- `.gitignore`에 `*.tfvars` 포함되어 Git에 커밋되지 않음
- 가장 간단하고 표준적인 방법

**최종 구조:**
```hcl
# terraform.tfvars
proxmox_api_url     = "https://192.168.2.11:8006/api2/json"
proxmox_token_id     = "root@pam!terraform-admin"
proxmox_token_secret = "your_secret"
ssh_public_key_path = "/Users/yoon/.ssh/terraform_ssh.pub"
```

**핵심 포인트:**
- 업계 표준 방식
- 불필요한 복잡도 제거
- 프로젝트별로 독립적 관리

---

## 배포 실행

### 1. 문법 검사

```bash
# 개별 playbook 검사
ansible-playbook --syntax-check -i inventory.ini deploy_gitlab_server.yml
ansible-playbook --syntax-check -i inventory.ini deploy_gitlab_runner.yml

# 통합 playbook 검사
ansible-playbook --syntax-check -i inventory.ini deploy_gitlab.yml
```

### 2. 연결 테스트

```bash
# Ping 테스트
ansible all -i inventory.ini -m ping

# 결과 확인
ansible all -i inventory.ini -m shell -a "hostname"
```

### 3. 배포 실행

```bash
# 전체 배포
ansible-playbook -i inventory.ini deploy_gitlab.yml

# 개별 배포
ansible-playbook -i inventory.ini deploy_gitlab_server.yml
ansible-playbook -i inventory.ini deploy_gitlab_runner.yml
```

### 4. 배포 확인

```bash
# GitLab 서비스 상태 확인
ansible gitlab_server -i inventory.ini -m shell -a "sudo gitlab-ctl status" --become

# GitLab URL 확인
ansible gitlab_server -i inventory.ini -m shell -a "sudo gitlab-rake gitlab:env:info | grep URL" --become

# Runner 설치 확인
ansible gitlab_runner -i inventory.ini -m shell -a "gitlab-runner --version" --become
```

---

## 배포 후 작업

### 1. GitLab 초기 비밀번호 확인

```bash
ansible gitlab_server -i inventory.ini -m shell -a "sudo cat /etc/gitlab/initial_root_password" --become
```

### 2. GitLab 접속

1. 브라우저에서 `http://yoongitlab.com` 접속
2. 초기 비밀번호로 로그인
3. 비밀번호 변경

### 3. GitLab Runner 등록

```bash
# GitLab 서버에서 Runner 토큰 확인
# Settings → CI/CD → Runners → Registration token

# Runner 서버에서 등록
ansible gitlab_runner -i inventory.ini -m shell -a "sudo gitlab-runner register" --become
```

---

## 주요 변경 사항 요약

### 1. SSH 키 관리
- **이전:** 수동으로 서버에 접속하여 키 추가
- **이후:** Terraform Cloud-init으로 자동 주입

### 2. 환경변수 관리
- **이전:** 복잡한 스크립트와 `.env` 파일
- **이후:** `terraform.tfvars`에 직접 입력 (표준 방식)

### 3. Playbook 구조
- **이전:** 하나의 파일에 여러 play (문법 오류)
- **이후:** 파일 분리 + `import_playbook` 사용

### 4. 필수 패키지
- **이전:** `curl`, `ca-certificates`, `postfix`만 설치
- **이후:** `gnupg` 추가 (GPG 키 검증 필수)

### 5. external_url 설정
- **이전:** 설정 파일 생성 대기 없이 바로 설정
- **이후:** `wait_for` 모듈로 파일 생성 대기 후 설정

---

## 최종 파일 구조

```
ansible_test/
├── inventory.ini                  # 인벤토리 (IP, 사용자, SSH 키)
├── deploy_gitlab.yml              # 통합 playbook
├── deploy_gitlab_server.yml       # GitLab 서버 설치
├── deploy_gitlab_runner.yml       # GitLab Runner 설치
├── DNS_TROUBLESHOOTING.md         # DNS 관련 트러블슈팅
└── ANSIBLE_DEPLOYMENT.md          # 이 문서
```

---

## 참고 자료

- [Ansible 공식 문서](https://docs.ansible.com/)
- [GitLab CE 설치 가이드](https://about.gitlab.com/install/)
- [GitLab Runner 설치 가이드](https://docs.gitlab.com/runner/install/)
- [Ansible Best Practices](https://docs.ansible.com/ansible/latest/user_guide/playbooks_best_practices.html)

