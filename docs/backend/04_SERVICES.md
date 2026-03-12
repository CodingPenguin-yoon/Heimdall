# Services

이 문서는 백엔드 핵심 서비스 클래스의 실제 책임과 연결 관계를 정리한다.

## 1. DeploymentService

파일:

- `backend/app/services/deployment/service.py`

역할:

- 배포 task 생성
- BackgroundTasks 등록
- Terraform -> Ansible 순차 실행
- 배포 요청 payload 를 Terraform/Ansible 입력으로 변환

핵심 포인트:

- workspace key 는 `server_name` 또는 `task-<id>` 기반
- Terraform output 에서 VM IP 를 추출
- VM IP 를 못 얻으면 Ansible 을 자동 건너뜀
- SSH 공개키를 읽어 Terraform cloud-init 변수로 전달

## 2. TerraformService

파일:

- `backend/app/services/terraform/__init__.py`

역할:

- Terraform CLI 실행
- workspace 선택/생성
- legacy state migration
- output 조회
- 로그에서 진행률과 Proxmox task 흔적 파싱

특징:

- 루트 `.env` 로드
- `PROXMOX_*` 를 `TF_VAR_proxmox_*` 로 매핑
- 작업 디렉터리는 `infra/terraform`

중요 메서드:

- `init()`
- `plan()`
- `apply()`
- `destroy()`
- `get_output()`
- `select_or_create_workspace()`
- `migrate_legacy_local_state()`

주의:

- `destroy()` 메서드는 존재하지만 현재 활성 API 라우트에서 직접 쓰지 않는다.

## 3. AnsibleService

파일:

- `backend/app/services/ansible/__init__.py`

역할:

- 동적 inventory 생성
- `ansible-playbook` 실행
- stdout 을 task 로그로 스트리밍

특징:

- inventory 파일 경로는 고정 `infra/ansible/inventory.yml`
- SSH 개인키 경로가 있으면 inventory 에 포함
- extra vars 는 JSON 문자열로 `-e` 전달

## 4. ProxmoxService

파일:

- `backend/app/services/proxmox/__init__.py`

역할:

- Proxmox REST API 조회
- 노드/VM/템플릿/스토리지/네트워크/ISO 목록 제공
- 모니터링 데이터 수집
- VM 종료/삭제 제어

특징:

- 인증은 API token header 사용
- read/write request helper 가 분리돼 있다
- 네트워크 목록은 `vmbr*` bridge 위주

중요 메서드 예:

- `get_nodes()`
- `get_templates()`
- `get_vms()`
- `get_storages()`
- `get_networks()`
- `get_all_nodes_monitoring()`
- `terminate_vm()`

## 5. NetworkService

파일:

- `backend/app/services/network/__init__.py`

역할:

- IP 풀 설정 로드
- 사용 가능 IP 조회
- 개별 IP 사용 여부 확인

제한:

- 사용 여부 판단이 `ping` 기반이다.
- DHCP lease, ARP, Proxmox IPAM 과 연동하지 않는다.

## 6. TaskManager

파일:

- `backend/app/services/task/manager.py`

역할:

- task 상태 저장
- 로그 저장
- 진행률 추적
- SSE 이벤트 버퍼 제공
- 파일 persistence
- 자동 아카이브

특징:

- 싱글톤
- thread-safe lock 사용
- 완료 상태 문자열과 진행률 source 를 별도로 관리

## 7. LLM 서비스 묶음

현재 활성 라우트는 `backend/app/domains/llm/*` 이다.

구성:

- `domains/llm/router.py`: API 엔드포인트
- `domains/llm/commands/infra_action.py`: 액션 타입 매핑
- `domains/llm/commands/chat_session.py`: Redis 세션 저장
- `services/llm/llm_core.py`: Gemini 프롬프트/호출

특징:

- 일부 조회 액션은 `/llm/chat` 내부에서 자동 실행
- `create_vm` 액션은 결국 DeploymentService 를 호출
- Redis 는 선택 사항

## 8. 서비스 간 의존 관계

```text
deploy router
  -> DeploymentService
    -> TerraformService
    -> AnsibleService
    -> TaskManager

task router
  -> TaskManager

proxmox router
  -> ProxmoxService
  -> NetworkService

llm router
  -> LLMService
  -> ChatSessionService
  -> InfraActionService
    -> ProxmoxService
    -> DeploymentService
```

## 9. 현재 가장 민감한 경계

- DeploymentService 와 Terraform/Ansible subprocess 경계
- TaskManager 와 프론트 SSE 소비 경계
- LLM action schema 와 실제 인프라 기능 지원 범위 경계
