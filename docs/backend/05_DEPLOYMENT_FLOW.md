# Deployment Flow

이 문서는 `POST /api/deploy` 요청이 실제로 어떤 순서로 Terraform 과 Ansible 까지 이어지는지 정리한다.

기준 파일:

- `backend/app/domains/deploy/router.py`
- `backend/app/services/deployment/service.py`
- `backend/app/services/terraform/__init__.py`
- `backend/app/services/ansible/__init__.py`

## 1. 요청 수신

프론트 또는 LLM 액션이 `POST /api/deploy` 를 호출한다.

주요 입력:

- 배포 대상 노드 `server_id`
- 템플릿 `template_id`
- VM 자원 스펙
- 스토리지 / 네트워크
- VM 이름
- 선택 패키지 / 역할
- 고정 IP / gateway

## 2. Task 생성

DeploymentService 는 먼저 `task_id` 를 만들고 TaskManager 에 메타데이터를 저장한다.

메타데이터 예:

- `action=deploy`
- `server_name`
- `server_id`
- `template_id`
- `storage_id`
- `network_ids`
- `cpu_cores`
- `memory_gb`
- `requested_vm_ip`
- `requested_vm_gateway`
- `ansible_packages`
- `ansible_roles`

그 뒤 FastAPI `BackgroundTasks` 로 실제 배포 함수를 예약한다.

## 3. Workspace 결정

실행 시작 시 workspace key 를 정한다.

우선순위:

1. `server_name`
2. 없으면 `task-<id>`

이 값은 Terraform workspace 이름으로 정규화돼 state 분리에 사용된다.

## 4. Terraform 단계

### 4.1 `init`

- 작업 디렉터리: `infra/terraform`
- 실패 시 즉시 task 실패

### 4.2 workspace select/create

- 있으면 `terraform workspace select`
- 없으면 `terraform workspace new`

### 4.3 optional legacy state migration

아래 환경변수가 켜져 있을 때만 동작한다.

- `TF_AUTO_MIGRATE_LEGACY_STATE`
- `TF_AUTO_MIGRATE_LEGACY_STATE_FORCE`
- `TF_AUTO_MIGRATE_LEGACY_STATE_STRICT`

legacy source 기본 경로:

- `backend/iac/terraform/terraform.tfstate`

### 4.4 `plan`

- 경고성 실패는 로그만 남기고 계속 갈 수 있다

### 4.5 `apply`

DeploymentService 가 요청값을 Terraform 변수로 바꾼다.

대표 매핑:

- `server_name` -> `vm_name`
- `server_id` -> `target_node`
- `template_id` -> `template_id`
- `cpu_cores` -> `cpu_cores`
- `memory_gb` -> `memory_gb`
- `disk_size_gb` -> `disk_size_gb`
- `storage_id` -> `storage_id`
- `network_ids` -> `network_ids`
- `vm_ip` -> `vm_ip`
- `vm_gateway` -> `vm_gateway`

추가 매핑:

- SSH 공개키 -> `ssh_public_key`
- `ANSIBLE_SSH_USER` -> `ssh_user`

## 5. Terraform output 처리

`apply` 후 백엔드는 Terraform output 에서 VM IP 를 찾는다.

조회 후보 키:

- `vm_ip`
- `instance_ip`
- `ip_address`
- `ip`
- `default_ipv4_address`

`infra/terraform/main.tf` 의 현재 출력은 `vm_ip`, `vm_id`, `vm_name` 다.

## 6. Ansible 단계 진입 조건

Ansible 은 아래 조건일 때만 자동으로 실행된다.

- `skip_ansible` 가 아님
- Terraform 을 건너뛰지 않았거나, 별도 inventory 호스트를 구성할 수 있음
- VM IP 를 확보함

VM IP 를 못 얻으면 로그에 이유를 남기고 Ansible 을 건너뛴다.

## 7. Inventory 생성

백엔드는 단일 호스트 inventory 를 만든다.

예상 값:

- host name: `proxmox_vm`
- IP: Terraform output 기반
- user: `ANSIBLE_SSH_USER` 또는 `root`

## 8. Ansible extra vars

요청에서 선택한 값이 다음과 같이 전달된다.

- `ansible_packages` -> `packages_to_install`
- `ansible_roles` -> `roles_to_apply`

## 9. 완료/실패 처리

성공 시:

- task status -> `Success`
- 진행률 98 부근까지 업데이트
- 완료 로그 기록

실패 시:

- task status -> `Failed`
- 마지막 에러 로그 기록

## 10. 실제로 자주 깨지는 지점

### 템플릿 clone

템플릿 ID, 스토리지, 네트워크 조합이 Proxmox 실제 상태와 맞지 않으면 Terraform 에서 실패한다.

### guest agent / IP 추출

DHCP 템플릿에 guest agent 가 없으면 VM 생성은 성공했는데 IP 추출이 실패하고, 그 결과 Ansible 이 건너뛰어진다.

### SSH 키

공개키를 못 읽으면 VM 내부 계정에 키 주입이 안 되고 Ansible SSH 접속이 깨질 수 있다.

### Ansible playbook 의 느슨한 실패 처리

플레이북이 이제 fail-fast 로 동작하므로 패키지 설치/서비스 시작 오류가 바로 작업 실패로 이어진다.

## 11. 현재 문서상 꼭 알아야 할 제한

- `destroy` API 플로우는 현재 활성화돼 있지 않다.
- 여러 배포가 동시에 `infra/ansible/inventory.yml` 을 덮어쓸 수 있다.
