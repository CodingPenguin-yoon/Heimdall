# VM 출력 정의 (for_each를 사용한 동적 출력)

output "vm_ip_addresses" {
  description = "생성된 모든 VM의 IP 주소 목록"
  value = {
    for k, vm in proxmox_vm_qemu.vms : k => vm.default_ipv4_address
  }
}

output "vm_details" {
  description = "생성된 모든 VM의 상세 정보"
  value = {
    for k, vm in proxmox_vm_qemu.vms : k => {
      name    = vm.name
      ip      = vm.default_ipv4_address
      vmid    = vm.vmid
      node    = vm.target_node
    }
  }
}
