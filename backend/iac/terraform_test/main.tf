terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.38"
    }
  }
}

provider "proxmox" {
  endpoint  = "https://192.168.2.11:8006/"
  api_token = "root@pam!terraform=f5042070-a28f-404b-b5e4-ecee0fce7d8e"
  insecure  = true
}

resource "proxmox_virtual_environment_vm" "test_vm" {
  name      = "test-vm-001"
  node_name = "yoonmanserver"

  clone {
    vm_id = 118
  }

  cpu {
    cores = 2
    type  = "host"
  }

  memory {
    dedicated = 4096
  }

  disk {
    datastore_id = "machine-mainnode"
    interface    = "scsi0"
    size         = 50
  }

  network_device {
    bridge = "vmbr0"
    model  = "virtio"
  }

  initialization {
    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }
  }
}
