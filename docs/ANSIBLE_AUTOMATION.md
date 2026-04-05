# Ansible Automation

현재 구현에서 Ansible 은 Terraform 뒤의 후처리 단계다.
Heimdall 에서는 GitLab Workspace/control-plane 과 분리된 low-level VM engine 일부로 본다.

기준 경로:

- `backend/app/domains/deploy/service.py`
- `backend/app/integrations/ansible/__init__.py`
- `infra/ansible/playbook.yml`

## 현재 동작

1. Terraform 이 VM 생성
2. 템플릿 clone 기반 생성이면 필요 시 VM stop -> CPU/memory 조정 -> start
3. Terraform 출력 또는 static 입력으로 VM IP 확보
4. backend 가 task별 `infra/ansible/inventory.<task>.yml` inventory 를 동적으로 생성
5. `ansible-playbook` 실행

IP 를 얻지 못하면 Ansible 단계는 건너뛴다.

## inventory 생성

동적 inventory 는 task마다 `infra/ansible/inventory.<task>.yml` 형태로 기록되고 실행 후 정리된다.
여기서 말하는 inventory 는 VM 접속용 Ansible inventory 다. GitLab project inventory 와는 다른 개념이다.

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
- task별 inventory 파일로 바뀌어서 이전보다 안전하지만, 같은 VM/같은 release 를 동시에 배포하면 여전히 운영 충돌은 날 수 있다
- `ansible-playbook` CLI 는 backend 가 실행되는 로컬 환경에 설치돼 있어야 한다
- 현재 SSH 공통 옵션에 `StrictHostKeyChecking=no` 가 들어가므로, 신뢰 가능한 내부망/테스트 환경 기준으로 운영하는 편이 안전하다
- GitLab Workspace 의 `Deploy Staging` 은 현재 수동 staging app deploy 슬라이스에서 이 경로를 재사용한다
- 현재 플레이북은 GitLab archive 를 받아 release 디렉터리에 풀고, `docker compose up -d --build` 와 HTTP healthcheck 까지 수행한다
- DB 자동화와 `DATABASE_URL` 주입은 아직 별도 구현 전이다
