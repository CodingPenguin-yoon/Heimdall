# VM 리소스 정의 (for_each를 사용하여 변수 기반으로 생성)
# Helm의 templates/처럼 "형식"만 정의하고, 실제 값은 terraform.tfvars에서 가져옵니다.

resource "proxmox_vm_qemu" "vms" {
  # for_each: terraform.tfvars의 vms 맵을 순회하며 VM 생성
  for_each = var.vms

  # ============================================
  # 기본 설정
  # ============================================
  name        = each.value.name
  target_node = coalesce(each.value.target_node, var.common_settings.target_node)
  clone       = coalesce(each.value.template, var.common_settings.template)
  clone_wait  = var.common_settings.clone_wait
  os_type     = "cloud-init"

  # ============================================
  # CPU 설정
  # ============================================
  cpu {
    cores   = each.value.cores
    sockets = var.common_settings.cpu_sockets
    type    = var.common_settings.cpu_type
  }

  # ============================================
  # 메모리 설정
  # ============================================
  memory = each.value.memory

  # ============================================
  # 디스크 설정
  # ============================================
  disks {
    # Cloud-init 드라이브
    ide {
      ide3 {
        cloudinit {
          storage = coalesce(each.value.disk_storage, var.common_settings.disk_storage)
        }
      }
    }

    # 데이터 디스크
    scsi {
      scsi0 {
        disk {
          size    = each.value.disk_size
          storage = coalesce(each.value.disk_storage, var.common_settings.disk_storage)
        }
      }
    }
  }

  # ============================================
  # 네트워크 설정
  # ============================================
  network {
    id     = 0
    model  = "virtio"
    bridge = var.common_settings.network_bridge
  }

  # ============================================
  # Cloud-init 설정
  # ============================================
  # 사용자 설정 (선택사항)
  # SSH 공개키: terraform.tfvars의 ssh_public_key_path에서 읽어서 사용
  ciuser     = coalesce(each.value.ciuser, "yoon")
  cipassword = each.value.cipassword
  sshkeys    = coalesce(each.value.sshkeys, try(file(var.ssh_public_key_path), ""))

  # 네트워크 설정
  ipconfig0  = "ip=${each.value.ip}/24,gw=${var.common_settings.gateway}"
  nameserver = var.common_settings.nameserver

  # 기타 설정
  ci_wait          = var.common_settings.ci_wait
  agent            = 1
  automatic_reboot = true
  boot             = var.common_settings.boot_order
}
