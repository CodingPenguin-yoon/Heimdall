# Template Preparation

현재 안정적으로 지원되는 VM 생성 방식은 `Proxmox 템플릿 클론 + cloud-init + 후속 Ansible` 이다.

기준 경로:

- `backend/app/domains/deploy/service.py`
- `backend/app/integrations/terraform/__init__.py`
- `infra/terraform/main.tf`

## 템플릿에 꼭 있어야 하는 것

### cloud-init

Terraform 이 SSH 사용자, 공개키, IP 설정을 넘기므로 템플릿은 cloud-init 이 동작해야 한다.

### SSH 서버

Ansible 은 Terraform 뒤에 SSH 로 붙는다. 템플릿에 SSH 서버가 있어야 한다.

### guest agent

DHCP 배포에서 VM IP 자동 감지를 안정적으로 하려면 `qemu-guest-agent` 가 필요하다.

## 권장 준비 절차

1. 기본 OS 이미지 생성
2. `cloud-init` 설치
3. `qemu-guest-agent` 설치 및 enable
4. `openssh-server` 설치 및 enable
5. 업데이트 및 기본 정리
6. Proxmox 템플릿으로 변환

Ubuntu 계열 예시:

```bash
sudo apt-get update
sudo apt-get install -y cloud-init qemu-guest-agent openssh-server
sudo systemctl enable --now qemu-guest-agent
sudo systemctl enable --now ssh
```

## 네트워크 메모

### DHCP

- guest agent 가 있어야 IP 감지가 안정적이다
- DHCP 환경에서도 Ansible 까지 이어질 수 있지만 템플릿 품질이 중요하다

### Static IP

- 입력은 CIDR 형식이어야 한다
  - 예: `192.168.2.120/24`
- 게이트웨이는 별도로 전달한다

## 체크리스트

- Proxmox 에서 템플릿으로 보이는가
- cloud-init 이 활성화돼 있는가
- SSH 서버가 동작하는가
- `qemu-guest-agent` 가 설치돼 있는가
- clone 후 정상 부팅하는가
- 대상 bridge / storage 와 호환되는가
