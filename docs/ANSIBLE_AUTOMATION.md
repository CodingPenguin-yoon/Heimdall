# Ansible Automation

현재 구현에서 Ansible 은 “Terraform 후처리 단계”로 동작한다. 기준 파일은 `backend/app/services/deployment/service.py`, `backend/app/services/ansible/__init__.py`, `infra/ansible/playbook.yml` 이다.

## 1. 전체 구조

배포 요청이 들어오면:

1. Terraform 이 VM 을 만든다.
2. Terraform 출력에서 VM IP 를 읽는다.
3. IP 가 있으면 백엔드가 동적 `inventory.yml` 을 생성한다.
4. 선택한 패키지와 역할을 `extra_vars` 로 넘겨 `ansible-playbook` 을 실행한다.

IP 를 못 얻으면 Ansible 단계는 자동으로 건너뛴다.

## 2. 실제 실행 명령 형태

백엔드는 대략 아래 형태로 실행한다.

```bash
ansible-playbook infra/ansible/playbook.yml -i infra/ansible/inventory.yml -e '{"packages_to_install":["curl"],"roles_to_apply":["docker"]}'
```

작업 로그에는 전체 명령이 남는다.

## 3. Inventory 생성 방식

동적 inventory 파일은 `infra/ansible/inventory.yml` 에 작성된다.

생성 구조:

```yaml
all:
  children:
    proxmox_vms:
      hosts:
        proxmox_vm:
          ansible_host: 192.168.2.120
          ansible_user: root
          ansible_ssh_private_key_file: /path/to/key
  vars:
    ansible_ssh_common_args: -o StrictHostKeyChecking=no
```

특징:

- 호스트 그룹 이름은 `proxmox_vms`
- 기본 사용자명은 `ANSIBLE_SSH_USER` 또는 `root`
- 개인키 경로는 `ANSIBLE_SSH_PRIVATE_KEY_FILE` 이 있을 때만 포함
- host key checking 은 강제로 비활성화

주의:

- 저장소의 `infra/ansible/inventory.yml.example` 와 실제 생성 구조는 완전히 일치하지 않는다.

## 4. Playbook 입력값

백엔드는 두 종류의 `extra_vars` 를 전달한다.

- `packages_to_install`
- `roles_to_apply`

둘 다 프론트 VM 생성 마법사에서 선택한 값이 그대로 넘어온다.

## 5. 선택 가능한 패키지

현재 프론트와 플레이북에서 다루는 패키지 계열:

- `ca-certificates`
- `curl`
- `wget`
- `git`
- `git-lfs`
- `vim`
- `tmux`
- `tree`
- `htop`
- `jq`
- `ripgrep`
- `unzip`
- `zip`
- `rsync`
- `net-tools`
- `nfs-common`
- `openssh-server`
- `python3-venv`
- `docker`
- `docker-compose`
- `nginx`
- `nodejs`
- `python3-pip`
- `postgresql`
- `mysql-server`
- `redis`
- `certbot`
- `fail2ban`

주의:

- 모든 항목이 완전히 동일한 방식으로 설치되는 것은 아니다.
- 일부는 일반 `package` 태스크로, 일부는 별도 분기 태스크로 처리한다.

## 6. 선택 가능한 역할 ID

현재 플레이북의 역할성 블록:

- `base`
- `docker`
- `python`
- `nodejs`
- `nginx`
- `postgresql`
- `mysql`
- `redis`
- `nfs`
- `ssl`
- `firewall`

이 저장소에는 별도 `roles/` 디렉터리가 없고, 위 역할은 모두 `playbook.yml` 내부 block 으로 구현돼 있다.

## 7. 현재 Playbook 특성

- 단일 파일 플레이북이다.
- OS family 기준 분기가 있다.
- 실패한 태스크는 그대로 플레이북 실패로 반영된다.
- `docker`, `nodejs`, `postgresql`, `mysql`, `redis` 등은 역할 블록 안에서도 설치/서비스 기동을 같이 처리한다.

## 8. 실제로 주의해야 할 리스크

### fail-fast 동작

패키지 설치나 서비스 시작이 실패하면 플레이북도 즉시 실패한다.

결과적으로:

- Task Board 상태가 실제 실패와 더 잘 맞는다.
- 부분 성공 상태가 이전보다 덜 숨겨진다.
- 대신 패키지 저장소나 OS 별 패키지 이름 문제가 더 빨리 드러난다.

### Node.js 설치 방식

Debian 계열에서 `curl | bash` 로 NodeSource 스크립트를 실행한다. 네트워크 정책이 엄격한 환경에서는 실패 가능성이 높다.

### 방화벽 / SSL 역할

현재는 패키지 설치 수준에 가깝다. 실제 정책 적용이나 인증서 발급 자동화는 구현돼 있지 않다.

### Inventory 파일 재사용

`inventory.yml` 을 고정 경로에 덮어쓴다. 동시 실행이 많아지면 파일 경합 가능성이 있다.

## 9. 수동 실행 예시

inventory 준비 후:

```bash
cd infra/ansible
ansible-playbook -i inventory.yml playbook.yml -e '{"packages_to_install":["curl","git"],"roles_to_apply":["base","docker"]}'
```

## 10. 개선 우선순위

1. 역할을 실제 `roles/` 구조로 분리
2. inventory 파일을 작업별 임시 파일로 분리
3. 성공/실패 기준을 태스크 단위로 더 엄격히 정의
5. OS 별 설치 전략과 패키지 이름 표준화
