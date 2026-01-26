"""
Proxmox API 연동 서비스 모듈

이 모듈은 Proxmox API와 통신하여 서버, 템플릿, 스토리지, 네트워크 정보를 조회합니다.
- Proxmox API 인증 및 요청 처리
- 노드(서버) 목록 조회
- 템플릿 목록 조회
- 스토리지 목록 조회
- 네트워크 목록 조회
"""

import os
import requests
from typing import List, Dict, Optional
from requests.auth import HTTPBasicAuth
import urllib3

# SSL 경고 비활성화 (자체 서명 인증서 사용 시)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ProxmoxService:
    """
    Proxmox API와 통신하는 서비스 클래스
    
    환경 변수에서 Proxmox API 인증 정보를 읽어서
    Proxmox API를 호출하고 결과를 반환합니다.
    """
    
    def __init__(self):
        """
        초기화: 환경 변수에서 Proxmox API 설정 읽기
        """
        self.api_url = os.getenv("PROXMOX_API_URL", "").rstrip('/')
        self.token_id = os.getenv("PROXMOX_API_TOKEN_ID", "")
        self.token_secret = os.getenv("PROXMOX_API_TOKEN_SECRET", "")
        self.tls_insecure = os.getenv("PROXMOX_TLS_INSECURE", "false").lower() == "true"
        
        # API URL이 없으면 빈 리스트 반환
        if not self.api_url:
            self.api_url = None
    
    def _make_request(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None) -> Dict:
        """
        Proxmox API 요청 실행 (내부 메서드)
        
        Args:
            endpoint: API 엔드포인트 (예: "/nodes")
            method: HTTP 메서드 (GET, POST 등)
            params: 쿼리 파라미터
            
        Returns:
            API 응답 데이터 딕셔너리
            
        Raises:
            Exception: API 요청 실패 시
        """
        if not self.api_url:
            return {"data": []}
        
        url = f"{self.api_url}{endpoint}"
        headers = {
            "Authorization": f"PVEAPIToken={self.token_id}={self.token_secret}"
        }
        
        try:
            if method == "GET":
                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    verify=not self.tls_insecure,
                    timeout=10
                )
            else:
                response = requests.request(
                    method,
                    url,
                    headers=headers,
                    json=params,
                    verify=not self.tls_insecure,
                    timeout=10
                )
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # API 연결 실패 시 빈 리스트 반환 (에러 로깅은 하지 않음)
            return {"data": []}
        except Exception as e:
            return {"data": []}
    
    def get_nodes(self) -> List[Dict]:
        """
        Proxmox 노드(서버) 목록 조회
        
        Returns:
            노드 정보 리스트
        """
        try:
            result = self._make_request("/nodes")
            nodes = result.get("data", [])
            
            # 노드 정보를 프론트엔드 형식으로 변환
            formatted_nodes = []
            for node in nodes:
                formatted_nodes.append({
                    "id": node.get("node"),
                    "server_id": node.get("node"),
                    "name": node.get("node"),
                    "server_name": node.get("node"),
                    "status": node.get("status", "unknown"),
                    "cpu": node.get("maxcpu", 0),
                    "memory": node.get("maxmem", 0),
                    "uptime": node.get("uptime", 0),
                })
            
            return formatted_nodes
        except Exception:
            return []
    
    def get_templates(self, node: Optional[str] = None) -> List[Dict]:
        """
        Proxmox 템플릿 목록 조회
        
        Args:
            node: 특정 노드에서만 조회 (None이면 모든 노드)
            
        Returns:
            템플릿 정보 리스트
        """
        try:
            templates = []
            
            # 노드 목록 가져오기
            if node:
                nodes = [{"node": node}]
            else:
                nodes_result = self._make_request("/nodes")
                nodes = nodes_result.get("data", [])
            
            # 각 노드에서 템플릿 조회
            for node_info in nodes:
                node_name = node_info.get("node")
                if not node_name:
                    continue
                
                # VM 목록 조회 (템플릿 포함)
                vms_result = self._make_request(f"/nodes/{node_name}/qemu")
                vms = vms_result.get("data", [])
                
                # 템플릿만 필터링 (template 속성이 1인 것)
                for vm in vms:
                    if vm.get("template") == 1:
                        templates.append({
                            "id": f"{node_name}/{vm.get('vmid')}",
                            "template_id": f"{node_name}/{vm.get('vmid')}",
                            "name": vm.get("name", f"template-{vm.get('vmid')}"),
                            "template_name": vm.get("name", f"template-{vm.get('vmid')}"),
                            "vmid": vm.get("vmid"),
                            "node": node_name,
                            "cpu_cores": vm.get("cpus", 0),
                            "memory_gb": round(vm.get("maxmem", 0) / 1024 / 1024 / 1024, 2) if vm.get("maxmem") else 0,
                        })
            
            return templates
        except Exception:
            return []
    
    def get_storages(self, node: Optional[str] = None) -> List[Dict]:
        """
        Proxmox 스토리지 목록 조회
        
        Args:
            node: 특정 노드에서만 조회 (None이면 첫 번째 노드)
            
        Returns:
            스토리지 정보 리스트
        """
        try:
            storages = []
            
            # 노드 선택
            if not node:
                nodes_result = self._make_request("/nodes")
                nodes = nodes_result.get("data", [])
                if nodes:
                    node = nodes[0].get("node")
            
            if not node:
                return []
            
            # 스토리지 목록 조회
            storages_result = self._make_request(f"/nodes/{node}/storage")
            storage_list = storages_result.get("data", [])
            
            # 스토리지 정보 변환
            for storage in storage_list:
                storage_info = storage.get("storage", "")
                if not storage_info:
                    continue
                
                # 스토리지 상세 정보 조회
                try:
                    detail_result = self._make_request(f"/storage/{storage_info}")
                    detail = detail_result.get("data", {})
                    
                    storages.append({
                        "id": storage_info,
                        "storage_id": storage_info,
                        "name": storage_info,
                        "storage_name": storage_info,
                        "type": detail.get("type", storage.get("type", "unknown")),
                        "content": detail.get("content", []),
                        "size_gb": round(detail.get("total", 0) / 1024 / 1024 / 1024, 2) if detail.get("total") else None,
                        "available_gb": round((detail.get("total", 0) - detail.get("used", 0)) / 1024 / 1024 / 1024, 2) if detail.get("total") else None,
                    })
                except Exception:
                    # 상세 정보 조회 실패 시 기본 정보만
                    storages.append({
                        "id": storage_info,
                        "storage_id": storage_info,
                        "name": storage_info,
                        "storage_name": storage_info,
                        "type": storage.get("type", "unknown"),
                    })
            
            return storages
        except Exception:
            return []
    
    def get_networks(self, node: Optional[str] = None) -> List[Dict]:
        """
        Proxmox 네트워크 목록 조회
        
        Args:
            node: 특정 노드에서만 조회 (None이면 첫 번째 노드)
            
        Returns:
            네트워크 정보 리스트
        """
        try:
            networks = []
            
            # 노드 선택
            if not node:
                nodes_result = self._make_request("/nodes")
                nodes = nodes_result.get("data", [])
                if nodes:
                    node = nodes[0].get("node")
            
            if not node:
                return []
            
            # 네트워크 목록 조회
            networks_result = self._make_request(f"/nodes/{node}/network")
            network_list = networks_result.get("data", [])
            
            # 네트워크 정보 변환
            for network in network_list:
                iface = network.get("iface", "")
                if not iface or iface.startswith("lo"):
                    continue
                
                networks.append({
                    "id": iface,
                    "network_id": iface,
                    "name": iface,
                    "network_name": iface,
                    "type": network.get("type", "bridge"),
                    "cidr": network.get("cidr", ""),
                    "gateway": network.get("gateway", ""),
                    "description": f"{network.get('type', 'bridge')} interface",
                })
            
            return networks
        except Exception:
            return []
