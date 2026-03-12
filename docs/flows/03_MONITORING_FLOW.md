# Flow 03: Monitoring

이 문서는 모니터링 화면이 어떤 API 를 호출하고, 백엔드가 어떤 데이터를 조합해서 반환하는지 정리한다.

기준 파일:

- `frontend/src/components/MonitoringDashboard.jsx`
- `frontend/src/services/api.js`
- `backend/app/domains/proxmox/router.py`
- `backend/app/services/proxmox/__init__.py`

## 1. 프론트 호출 방식

모니터링 화면 `/monitoring` 은 현재 단일 API 만 주기적으로 호출한다.

```text
GET /api/monitoring/nodes
```

주기:

- 최초 마운트 시 1회
- 이후 30초마다 자동 새로고침
- 수동 Refresh 버튼으로 즉시 재호출 가능

## 2. 프론트가 실제로 쓰는 데이터

`MonitoringDashboard.jsx` 는 응답의 `nodes` 배열을 카드로 그린다.

주로 쓰는 필드:

- `name`
- `node`
- `status`
- `uptime`
- `cpu_usage_percent`
- `cpu_total`
- `memory_usage_percent`
- `memory_used_gb`
- `memory_total_gb`
- `storages`
- `load_avg`

현재 화면은 개별 노드 상세 API 나 개별 VM 모니터링 API 를 사용하지 않는다.

## 3. 백엔드 처리

라우터:

```text
GET /api/monitoring/nodes
```

핸들러는 `ProxmoxService.get_all_nodes_monitoring()` 결과를 그대로 `{ "nodes": ... }` 형태로 반환한다.

## 4. ProxmoxService 내부 의미

이 서비스는 노드별로 대략 아래 정보를 모은다.

- 노드 상태
- RRD 데이터
- CPU / 메모리 사용률
- storage 별 사용량
- load average

즉 프론트는 이미 집계된 데이터를 받는 구조다.

## 5. 현재 있지만 UI 에서 안 쓰는 API

- `GET /api/monitoring/nodes/{node_id}`
- `GET /api/monitoring/vms/{node_id}/{vmid}`

이 둘은 현재 `MonitoringDashboard` 에 연결되어 있지 않다.

## 6. 이 흐름의 장점

- 프론트가 단순하다
- 노드 단위 overview 를 빠르게 보여 줄 수 있다
- 폴링 주기가 명확하다

## 7. 이 흐름의 한계

- 개별 VM drill-down 이 없다
- 최근 시계열을 프론트에서 적극적으로 활용하지 않는다
- 전체 노드 집계를 매 30초마다 한 번에 다시 가져온다
- Proxmox API 가 느리면 모니터링 화면 체감도 바로 떨어진다

## 8. 운영 시 확인 포인트

- 노드 수가 늘어날수록 `/api/monitoring/nodes` 응답 시간
- storage metric 집계 비용
- 프론트 30초 폴링이 충분한지
- 개별 노드/VM 상세 뷰 추가 필요성
