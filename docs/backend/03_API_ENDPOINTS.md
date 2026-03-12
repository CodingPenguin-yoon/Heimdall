# API Endpoints

기준 파일은 `backend/app/main.py` 와 각 도메인 라우터다. 아래는 현재 실제로 활성화된 엔드포인트만 정리한 목록이다.

## 1. Root

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/` | 간단한 서비스 응답 |
| `GET` | `/health` | 헬스체크 |

## 2. Deploy

Prefix: `/api`

| Method | Path | 설명 |
| --- | --- | --- |
| `POST` | `/api/deploy` | Terraform + Ansible 배포 작업 시작 |

요청 주요 필드:

- `server_id`
- `template_id`
- `storage_id`
- `storage_type`
- `network_ids`
- `cpu_cores`
- `memory_gb`
- `disk_size_gb`
- `server_name`
- `vm_ip`
- `vm_gateway`
- `ansible_packages`
- `ansible_roles`
- `skip_terraform`
- `skip_ansible`

주의:

- `storage_type` 는 요청 모델에 있지만 현재 DeploymentService 에서 실질 사용 흔적이 약하다.

## 3. Task

Prefix: `/api`

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/api/status/{task_id}` | 작업 상태 조회 |
| `GET` | `/api/logs/{task_id}` | 작업 로그 조회 |
| `GET` | `/api/tasks` | 작업 목록 조회 |
| `GET` | `/api/tasks/stream` | SSE 이벤트 스트림 |
| `POST` | `/api/tasks/{task_id}/archive` | 아카이브 토글 |
| `GET` | `/api/tasks/{task_id}` | 작업 상세 조회 |

`/api/tasks` 쿼리 파라미터:

- `limit`
- `status`
- `q`
- `date_from`
- `date_to`
- `include_archived`

`/api/tasks/stream` 쿼리 파라미터:

- `include_archived`
- `last_event_id`

또는 `Last-Event-ID` 헤더를 받을 수 있다.

## 4. Proxmox / Network / Monitoring

Prefix: `/api`

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/api/servers` | 노드 목록 |
| `GET` | `/api/templates` | 템플릿 목록 |
| `GET` | `/api/vms` | VM 목록 |
| `GET` | `/api/instances` | VM 목록의 프론트 호환 래퍼 |
| `POST` | `/api/instances/terminate` | graceful shutdown 후 삭제 |
| `GET` | `/api/servers/{server_id}/storage` | 노드 스토리지 목록 |
| `GET` | `/api/servers/{server_id}/networks` | 노드 네트워크 브리지 목록 |
| `GET` | `/api/servers/{server_id}/vms` | 노드별 VM 목록 |
| `GET` | `/api/monitoring/nodes` | 전체 노드 모니터링 요약 |
| `GET` | `/api/monitoring/nodes/{node_id}` | 단일 노드 상세 |
| `GET` | `/api/monitoring/vms/{node_id}/{vmid}` | 단일 VM 상세 |
| `GET` | `/api/network/ip-pool/config` | IP 풀 설정 |
| `GET` | `/api/network/ip-pool/available` | 사용 가능 IP 목록 |
| `GET` | `/api/network/ip-pool/next` | 다음 사용 가능 IP |
| `GET` | `/api/network/ip-pool/check/{ip}` | 특정 IP 사용 가능 여부 |

`/api/network/ip-pool/available` 쿼리 파라미터:

- `limit`

`/api/instances/terminate` 요청 필드:

- `node`
- `vmid`
- `shutdown_timeout_seconds`
- `force_stop_timeout_seconds`

## 5. LLM

Prefix: `/api`

| Method | Path | 설명 |
| --- | --- | --- |
| `POST` | `/api/llm/chat` | 채팅 요청 처리 |
| `GET` | `/api/llm/session/{session_id}/messages` | 세션 메시지 조회 |
| `POST` | `/api/llm/session/{session_id}/messages` | 세션 메시지 조회 |
| `DELETE` | `/api/llm/session/{session_id}` | 세션 삭제 |
| `POST` | `/api/llm/execute-action` | LLM 액션 실행 |

### `/api/llm/chat`

요청 주요 필드:

- `session_id`
- `messages`
- `latest_message`
- `context`

응답 주요 필드:

- `session_id`
- `assistant_message`
- `actions`
- `data`

백엔드는 아래 read-only 액션을 자동 실행해 `data` 에 합칠 수 있다.

- `list_vms`
- `list_nodes`
- `get_vm_detail`
- `list_templates`
- `list_storages`
- `list_networks`

### `/api/llm/execute-action`

실행 가능한 액션 타입:

- `list_vms`
- `list_nodes`
- `get_vm_detail`
- `create_vm`
- `list_templates`
- `list_storages`
- `list_networks`

## 6. 현재 없는 엔드포인트

아래는 흔적은 있지만 현재 활성 라우트가 아니다.

- `POST /api/destroy`

프론트 API 헬퍼에는 남아 있지만 백엔드에 연결된 라우트가 없다.

## 7. 호환성 메모

현재는 GET 과 POST 둘 다 지원한다. 프론트는 GET 경로를 사용한다.
