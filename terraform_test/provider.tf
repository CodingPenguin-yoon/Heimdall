# 1. Terraform 설정: Proxmox 플러그인을 다운로드합니다.
terraform {
  required_providers {
    proxmox = {
      source  = "telmate/proxmox"
      version = "3.0.2-rc04"
    }
  }
}

# 2. Proxmox 접속 설정: variables.tf와 terraform.tfvars에서 값을 가져옵니다.
provider "proxmox" {
  pm_api_url          = var.proxmox_api_url
  pm_api_token_id     = var.proxmox_token_id
  pm_api_token_secret = var.proxmox_token_secret
  
  pm_tls_insecure = true
  pm_debug        = true
}

