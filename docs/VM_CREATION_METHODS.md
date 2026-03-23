# VM Creation and Instance Management

현재 저장소의 VM 생성 범위와 기존 인스턴스 관리 범위를 정리한 문서다.

## 생성

현재 지원:

- Proxmox 템플릿 클론 기반 생성
- Terraform + Ansible 연동

현재 미지원:

- ISO 직접 설치 기반 생성

즉 VM 생성의 표준 경로는 항상 `template_id` 기반이다.

## 생성 시 설정 가능한 것

- target server
- template
- storage
- network
- server name
- CPU
- memory
- DHCP 또는 static IP
- Ansible packages
- Ansible roles

## 기존 인스턴스 관리

현재는 이미 생성된 인스턴스에 대해 아래 기능이 있다.

- `terminate`
- `start`
- `shutdown`
- `stop`
- `reboot`
- CPU / memory resize

리사이즈는 stopped 상태에서 수행하는 것이 기준이다.

## 네트워크 메모

### DHCP

- guest agent 가 있으면 IP 자동 감지가 안정적이다
- DHCP 환경에서도 Ansible 까지 자동으로 이어질 수 있다

### Static IP

- CIDR 형식이 필요하다
  - 예: `192.168.2.120/24`

## 정리

- 생성 경로는 template clone only
- ISO 경로는 현재 없다
- 생성 이후 운영 액션과 resize 는 현재 이미 구현돼 있다
