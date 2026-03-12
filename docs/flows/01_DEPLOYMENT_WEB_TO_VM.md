# Flow 01: Deployment Web to VM

이 문서는 사용자가 웹 UI 에서 VM 생성 버튼을 누른 뒤 실제 VM 이 만들어지고 Task Board 에 반영될 때까지의 흐름을 설명한다.

기준 파일:

- `frontend/src/App.jsx`
- `frontend/src/components/CreateInstanceWizard.jsx`
- `frontend/src/services/api.js`
- `backend/app/domains/deploy/router.py`
- `backend/app/services/deployment/service.py`

## 1. 프론트 초기 로딩

사용자가 `/` 화면에 들어오면 `CreateInstanceWizard` 가 데이터를 불러온다.

- 서버 목록: `GET /api/servers`
- 템플릿 목록: `GET /api/templates`
- 서버 선택 후 스토리지 목록: `GET /api/servers/{server_id}/storage`
- 서버 선택 후 네트워크 목록: `GET /api/servers/{server_id}/networks`

## 2. 사용자가 입력하는 값

주요 입력:

- 대상 노드
- 템플릿
- CPU / 메모리 / 디스크
- 스토리지
- 네트워크
- VM 이름
- 패키지 선택
- 역할 선택
- DHCP 또는 고정 IP

고정 IP 모드에서는 프론트가 먼저 `checkIpAvailability()` 로 `/api/network/ip-pool/check/{ip}` 를 호출해 ping 기반 중복 여부를 본다.

## 3. Launch 클릭

`App.jsx` 의 `handleDeploy()` 가 최종 payload 를 만들어 `deployInfrastructure()` 를 호출한다.

실제 요청:

```text
POST /api/deploy
```

전달 값 예:

- `server_id`
- `template_id`
- `cpu_cores`
- `memory_gb`
- `storage_id`
- `network_ids`
- `server_name`
- `ansible_packages`
- `ansible_roles`
- `vm_ip`
- `vm_gateway`

## 4. 백엔드 요청 수신

`domains/deploy/router.py` 가 요청을 받아 `DeploymentService.start_deployment_with_request()` 를 호출한다.

이 시점에:

- `task_id` 생성
- task metadata 저장
- FastAPI `BackgroundTasks` 등록
- HTTP 응답은 바로 반환

프론트는 이 `task_id` 를 받아 `/tasks` 로 이동한다.

## 5. 백그라운드 배포 실행

실제 배포는 별도 백그라운드 함수 `_execute_deployment()` 가 수행한다.

순서:

1. task status -> `Running`
2. Terraform `init`
3. Terraform workspace select/create
4. optional legacy state migration
5. Terraform `plan`
6. Terraform `apply`
7. Terraform output 에서 IP 추출
8. 조건이 맞으면 Ansible inventory 생성
9. Ansible playbook 실행
10. task status -> `Success` 또는 `Failed`

## 6. Task Board 반영

`TaskBoard.jsx` 는 두 경로를 같이 쓴다.

- 초기 목록: `GET /api/tasks`
- 실시간 업데이트: `GET /api/tasks/stream` SSE

그래서 사용자는 생성 직후 task card 를 보고, 이후 Terraform / Ansible 로그가 누적되는 것을 실시간으로 확인한다.

## 7. 성공 시 결과

성공한 배포의 흔적:

- task 상태 `Success`
- metadata 에 `terraform_workspace`, `vm_ip` 같은 값이 추가될 수 있음
- logs 에 Terraform / Ansible 실행 내역 축적

## 8. 실패 시 대표 원인

- Proxmox API 접근 실패
- 템플릿/스토리지/네트워크 조합 불일치
- Terraform CLI 실패
- guest agent 부재로 인한 IP 추출 실패
- SSH 키 주입 실패 또는 Ansible 접속 실패
- 패키지 저장소 또는 서비스 시작 실패에 따른 즉시 플레이북 실패

## 9. 현재 흐름에서 중요한 현실

- 생성 경로는 템플릿 선택을 전제로 고정돼 있다.
- destroy 흐름은 현재 사용자 메인 플로우에 없다.
- task 로그가 가장 신뢰도 높은 실행 근거다.
