# VM Creation Methods

이 문서는 현재 저장소가 실제로 제공하는 VM 생성 경로를 정리한다. UI 상 보이는 선택지와 백엔드/인프라 레이어의 실제 지원 범위는 완전히 같지 않다.

## 1. 결론 먼저

현재 안정적으로 지원되는 방식은 하나다.

- Proxmox 템플릿 클론 기반 생성

현재는 명시적으로 막아 둔 방식:

- ISO 기반 생성

현재 활성 경로가 아닌 것:

- `/destroy` API 기반 인프라 삭제

## 2. 지원 상태 표

| 방식 | 프론트 UI | 백엔드 요청 모델 | Terraform 반영 | 실사용 권장 여부 |
| --- | --- | --- | --- | --- |
| 템플릿 클론 | 있음 | 있음 | 있음 | 권장 |
| ISO 선택 | 숨김 | 없음 | 없음 | 비지원 |
| Skip Terraform / Skip Ansible | API 필드 있음 | 있음 | 부분 지원 | 운영자용 예외 경로 |
| Destroy 엔드포인트 | 활성 UI 없음 | 활성 라우트 없음 | 없음 | 사용 불가 |

## 3. 템플릿 클론 경로

실제 사용 흐름:

1. 프론트에서 `template_id` 선택
2. `POST /api/deploy`
3. DeploymentService 가 `template_id`, `server_id`, `storage_id`, `network_ids` 등으로 Terraform 변수 구성
4. Terraform 이 `proxmox_virtual_environment_vm` 에서 `clone` 블록을 사용해 VM 생성
5. 성공 시 output 에서 IP 추출
6. 가능하면 Ansible 후처리

이 경로는 현재 코드와 인프라 파일이 가장 잘 맞는다.

## 4. ISO 선택 경로

현재 애플리케이션 코드에서는 ISO 기반 생성 경로를 제거했다. 템플릿 선택 없이 새 VM 생성 요청은 허용되지 않는다.

## 5. Static IP / DHCP

생성 방식과 별개로 네트워크 모드는 두 가지다.

### DHCP

- `vm_ip` 를 비워 둔다
- Terraform guest agent 결과에 기대어 IP 를 읽는다
- 템플릿에 guest agent 가 없으면 Ansible 단계가 이어지지 않을 수 있다

### Static IP

- `vm_ip` 를 CIDR 형식으로 넘긴다
- `vm_gateway` 를 함께 넘긴다
- Terraform 출력은 CIDR 에서 주소 부분만 잘라 반환한다

## 6. Skip 플래그

`DeployRequest` 에는 아래 플래그가 있다.

- `skip_terraform`
- `skip_ansible`

의미:

- `skip_terraform=true`: 기존 VM 이 이미 있거나, Terraform 단계를 제외하고 운영자가 Ansible 만 돌리고 싶은 경우
- `skip_ansible=true`: VM 생성까지만 하고 후속 구성을 생략하고 싶은 경우

주의:

- 프론트 기본 UI 는 이 플래그를 적극적으로 노출하지 않는다.
- 일반 사용자 흐름보다 운영/디버깅용 경로에 가깝다.

## 7. 현재 설계 불일치

- 실제 인프라 레이어는 템플릿 클론 쪽만 열려 있다.
- 외부 클라이언트도 템플릿 기반 payload 기준으로 맞춰야 한다.

## 8. 운영 권장안

현재 기준 추천 순서:

1. 템플릿 클론만 표준 경로로 운영
2. ISO 경로는 문서상 “비지원”으로 명시
3. 필요하면 ISO 경로를 정말 구현하거나, 반대로 UI 에서 숨김 처리
4. 삭제 기능은 별도 API/UX 설계 후 다시 연결
