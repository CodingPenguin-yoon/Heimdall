# Ansible Automation

현재 구현에서 Ansible 은 Terraform 뒤의 후처리 단계다.

기준 경로:

- `backend/app/domains/deploy/service.py`
- `backend/app/integrations/ansible/__init__.py`
- `infra/ansible/playbook.yml`

## 현재 동작

1. Terraform 이 VM 생성
2. Terraform 출력 또는 static 입력으로 VM IP 확보
3. backend 가 `infra/ansible/inventory.yml` 을 동적으로 생성
4. `ansible-playbook` 실행

IP 를 얻지 못하면 Ansible 단계는 건너뛴다.

## inventory 생성

동적 inventory 는 `infra/ansible/inventory.yml` 에 기록된다.

주요 값:

- `ansible_host`
- `ansible_user`
- `ansible_ssh_private_key_file`
- `ansible_ssh_common_args=-o StrictHostKeyChecking=no`

## packages 와 roles

backend 는 아래 extra vars 를 넘긴다.

- `packages_to_install`
- `roles_to_apply`

현재 여기서 말하는 role 은 별도 `roles/` 디렉터리가 아니라 `playbook.yml` 안의 conditional block 이다.

즉:

- package: 개별 패키지 설치 중심
- role: 설치 + 서비스 enable/start 같은 묶음 동작

## 현재 플레이북 특성

- 단일 파일 플레이북
- 패키지와 역할을 조합해 실행
- 실패 시 그대로 task 실패로 반영
- cloud-init 안정화 대기 로직 포함
- SSH 가 부팅 직후 잠깐 끊기는 경우를 고려해 재접속을 한 번 더 시도

## 주의점

- Node.js 설치 등 일부 역할은 외부 네트워크 의존성이 있다
- inventory 파일은 고정 경로를 덮어쓰므로 동시 실행이 많아지면 파일 경합 여지가 있다
- `ansible-playbook` CLI 는 backend 가 실행되는 로컬 환경에 설치돼 있어야 한다
