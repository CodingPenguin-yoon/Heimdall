# Template Preparation

현재 저장소에서 안정적으로 지원되는 VM 생성 방식은 “Proxmox 템플릿 클론 + cloud-init + 후속 Ansible 구성”이다. 이 문서는 그 경로가 실제로 동작하기 위해 템플릿 쪽에서 준비해야 할 조건을 정리한다.

기준 파일:

- `infra/terraform/main.tf`
- `backend/app/services/deployment/service.py`

## 1. 왜 템플릿 준비가 중요한가

현재 Terraform 리소스는 `template_id` 기반 clone 경로를 실제로 사용한다.

즉 현재 운영 기준:

- 템플릿 클론: 지원
- ISO 직접 설치: 현재 애플리케이션 경로에서 지원하지 않음

## 2. 템플릿에 꼭 있어야 하는 것

### Cloud-init 지원

Terraform 이 `initialization` 블록으로 아래를 주입한다.

- SSH 사용자
- SSH 공개키
- IP 설정

따라서 템플릿은 cloud-init 이 동작하는 이미지여야 한다.

### SSH 접속 가능 상태

Ansible 은 Terraform 이후 SSH 로 붙는다. 템플릿 안에 SSH 서버가 살아 있어야 한다.

### Guest agent

DHCP 모드에서 Terraform 출력으로 VM IP 를 읽으려면 `qemu-guest-agent` 가 사실상 필요하다.

고정 IP 모드면 Terraform 출력이 `var.vm_ip` 에서 직접 계산되므로 덜 중요하지만, 운영 가시성 측면에서는 넣는 편이 낫다.

## 3. 권장 템플릿 준비 절차

1. 기본 OS 이미지를 만든다.
2. cloud-init 패키지를 설치한다.
3. `qemu-guest-agent` 를 설치하고 활성화한다.
4. SSH 서버를 설치하고 부팅 시 자동 시작되게 한다.
5. 업데이트와 기본 패키지 정리를 마친다.
6. Proxmox 에서 템플릿으로 변환한다.

Ubuntu 계열 예시:

```bash
sudo apt-get update
sudo apt-get install -y cloud-init qemu-guest-agent openssh-server
sudo systemctl enable --now qemu-guest-agent
sudo systemctl enable --now ssh
```

## 4. Terraform 이 기대하는 값

`infra/terraform/main.tf` 기준 주요 입력:

- `vm_name`
- `target_node`
- `template_id`
- `storage_id`
- `network_ids`
- `ssh_public_key`
- `ssh_user`
- `vm_ip`
- `vm_gateway`

`template_id` 는 보통 `node/vmid` 형식이다.

## 5. 네트워크 준비

프론트는 노드별 브리지 목록만 보여 준다. 백엔드 `get_networks()` 도 `vmbr*` 인터페이스만 반환한다.

따라서 템플릿 준비와 별개로 아래도 맞아야 한다.

- 대상 노드에 사용할 bridge 가 존재
- 템플릿 NIC 가 virtio 모델로 붙어도 문제없는 guest OS
- 고정 IP 사용 시 게이트웨이와 subnet 이 실제 네트워크와 일치

## 6. SSH 키 주입 방식

DeploymentService 는 다음 순서로 공개키를 찾는다.

1. `ANSIBLE_SSH_PUBLIC_KEY_FILE`
2. `~/.ssh/id_rsa.pub`
3. `~/.ssh/id_ed25519.pub`

찾은 공개키를 Terraform 변수 `ssh_public_key` 로 전달하고, cloud-init `user_account.keys` 로 주입한다.

즉 템플릿에 키를 미리 bake-in 할 필요는 없지만, cloud-init 이 이를 적용할 수 있어야 한다.

## 7. 고정 IP 와 DHCP 차이

### DHCP

- Terraform `agent.enabled = true`
- VM IP 는 guest agent 조회 결과에 기대는 편이다
- guest agent 가 없으면 Ansible 단계가 건너뛰기 쉬워진다

### Static IP

- 프론트 입력은 `192.168.x.x/24` 형식 CIDR 이어야 한다
- 게이트웨이는 별도 값으로 전달한다
- Terraform 출력 `vm_ip` 는 CIDR 에서 IP 부분만 잘라 반환한다

## 8. 템플릿 검증 체크리스트

- Proxmox 에서 템플릿으로 보이는가
- cloud-init 이 활성화돼 있는가
- SSH 서버가 동작하는가
- `qemu-guest-agent` 가 설치돼 있는가
- 클론 후 부팅이 정상인가
- 선택한 스토리지로 디스크 이동/복제가 가능한가

## 9. 현재 구현상 주의점

- 템플릿 clone timeout 은 길게 잡혀 있다. 느린 NFS 환경을 고려한 값이다.
- Terraform 리소스에 `ignore_changes = [disk, network_device]` 가 있어 이후 drift 해석에 주의가 필요하다.
- 템플릿 생성 자체를 자동화하는 코드는 현재 없다. 이 문서는 수동 준비 절차를 전제로 한다.
