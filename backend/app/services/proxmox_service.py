"""
Proxmox API 연동 서비스 모듈 (조회 전용)

이 모듈은 Proxmox API와 통신하여 리소스 정보를 조회합니다.
**중요**: 이 서비스는 조회(Read)만 담당하며, 리소스 생성/수정/삭제는 Terraform을 통해 수행합니다.

아키텍처 원칙:
- 조회(Read): Proxmox API 직접 호출 (빠르고 실시간)
- 제어(Create/Update/Delete): Terraform 사용 (IaC의 이점, 안전성, 추적 가능성)

기능:
- 노드(서버) 목록 조회
- 템플릿 목록 조회
- VM 목록 조회 (템플릿 제외)
- 스토리지 목록 조회
- 네트워크 목록 조회
"""

import os
import requests
from typing import List, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv
import urllib3

# SSL 경고 비활성화 (자체 서명 인증서 사용 시)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 환경 변수 로드 (ProxmoxService가 import될 때 실행)
# main.py의 load_dotenv보다 먼저 실행될 수 있으므로 여기서도 로드
project_root = Path(__file__).resolve().parent.parent.parent.parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)


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
        
        # 디버깅: 설정 확인
        if not self.api_url:
            print("경고: PROXMOX_API_URL이 설정되지 않았습니다.")
            self.api_url = None
        if not self.token_id:
            print("경고: PROXMOX_API_TOKEN_ID가 설정되지 않았습니다.")
        if not self.token_secret:
            print("경고: PROXMOX_API_TOKEN_SECRET이 설정되지 않았습니다.")
        
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
            # API 연결 실패 시 에러 정보 포함하여 반환 (디버깅용)
            print(f"Proxmox API 요청 실패: {url}")
            print(f"에러: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"응답 상태 코드: {e.response.status_code}")
                print(f"응답 내용: {e.response.text[:200]}")
            return {"data": [], "error": str(e)}
        except Exception as e:
            print(f"Proxmox API 예외 발생: {url}")
            print(f"에러: {str(e)}")
            return {"data": [], "error": str(e)}
    
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
    
    def get_vms(self, node: Optional[str] = None) -> List[Dict]:
        """
        Proxmox VM 목록 조회 (템플릿 제외)
        
        Args:
            node: 특정 노드에서만 조회 (None이면 모든 노드)
            
        Returns:
            VM 정보 리스트
        """
        try:
            vms = []
            
            # 노드 목록 가져오기
            if node:
                nodes = [{"node": node}]
            else:
                nodes_result = self._make_request("/nodes")
                nodes = nodes_result.get("data", [])
            
            # 각 노드에서 VM 조회
            for node_info in nodes:
                node_name = node_info.get("node")
                if not node_name:
                    continue
                
                # VM 목록 조회
                vms_result = self._make_request(f"/nodes/{node_name}/qemu")
                vm_list = vms_result.get("data", [])
                
                # 템플릿이 아닌 VM만 필터링
                for vm in vm_list:
                    if vm.get("template") != 1:  # 템플릿이 아닌 것만
                        vmid = vm.get("vmid")
                        
                        # VM 상세 설정 조회 (디스크 정보 포함)
                        disks = []
                        total_disk_gb = 0
                        try:
                            config_result = self._make_request(f"/nodes/{node_name}/qemu/{vmid}/config")
                            config_data = config_result.get("data", {})
                            
                            # 디스크 필드 파싱 (scsi0, scsi1, virtio0, ide0, sata0 등)
                            for key, value in config_data.items():
                                if any(key.startswith(prefix) for prefix in ["scsi", "virtio", "ide", "sata"]):
                                    # value 형식: "storage:vm-xxx-disk-0,size=50G" 또는 "storage:iso/image.iso,media=cdrom"
                                    if isinstance(value, str) and "media=cdrom" not in value:
                                        # size 파라미터 추출
                                        size_str = None
                                        for param in value.split(","):
                                            if param.startswith("size="):
                                                size_str = param.split("=")[1]
                                                break
                                        
                                        if size_str:
                                            # GB로 변환 (G, M, K 단위 지원)
                                            size_gb = 0
                                            if size_str.endswith("G"):
                                                size_gb = float(size_str[:-1])
                                            elif size_str.endswith("M"):
                                                size_gb = float(size_str[:-1]) / 1024
                                            elif size_str.endswith("K"):
                                                size_gb = float(size_str[:-1]) / 1024 / 1024
                                            else:
                                                # 숫자만 있으면 바이트로 가정하고 GB로 변환
                                                try:
                                                    size_gb = float(size_str) / 1024 / 1024 / 1024
                                                except:
                                                    pass
                                            
                                            if size_gb > 0:
                                                disks.append({
                                                    "device": key,
                                                    "size_gb": round(size_gb, 2),
                                                    "storage": value.split(":")[0] if ":" in value else "unknown"
                                                })
                                                total_disk_gb += size_gb
                        except Exception:
                            # 상세 정보 조회 실패 시 기본값 사용
                            pass
                        
                        # 디스크 정보가 없으면 maxdisk 사용
                        if not disks:
                            maxdisk_gb = round(vm.get("maxdisk", 0) / 1024 / 1024 / 1024, 2) if vm.get("maxdisk") else 0
                            if maxdisk_gb > 0:
                                disks.append({
                                    "device": "unknown",
                                    "size_gb": maxdisk_gb,
                                    "storage": "unknown"
                                })
                                total_disk_gb = maxdisk_gb
                        
                        vms.append({
                            "id": f"{node_name}/{vmid}",
                            "vm_id": f"{node_name}/{vmid}",
                            "vmid": vmid,
                            "name": vm.get("name", f"vm-{vmid}"),
                            "node": node_name,
                            "status": vm.get("status", "unknown"),
                            "cpu_cores": vm.get("cpus", 0),
                            "memory_gb": round(vm.get("maxmem", 0) / 1024 / 1024 / 1024, 2) if vm.get("maxmem") else 0,
                            "disk_gb": round(total_disk_gb, 2),  # 총 디스크 크기
                            "disks": disks,  # 디스크 목록
                            "uptime": vm.get("uptime", 0),
                        })
            
            return vms
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
    
    def get_iso_images(self, node: Optional[str] = None) -> List[Dict]:
        """
        Proxmox ISO 이미지 목록 조회
        
        Args:
            node: 특정 노드에서만 조회 (None이면 첫 번째 노드)
            
        Returns:
            ISO 이미지 정보 리스트
        """
        try:
            iso_images = []
            
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
            
            # 각 스토리지에서 ISO 이미지 조회
            for storage in storage_list:
                storage_name = storage.get("storage", "")
                if not storage_name:
                    continue
                
                # 스토리지 콘텐츠 조회
                try:
                    content_result = self._make_request(f"/storage/{storage_name}/content")
                    content_list = content_result.get("data", [])
                    
                    # ISO 이미지만 필터링
                    for item in content_list:
                        if item.get("content") == "iso":
                            volid = item.get("volid", "")
                            if volid:
                                # volid 형식: storage:iso/filename.iso
                                iso_images.append({
                                    "id": volid,
                                    "iso_id": volid,
                                    "name": volid.split("/")[-1] if "/" in volid else volid,
                                    "iso_name": volid.split("/")[-1] if "/" in volid else volid,
                                    "storage": storage_name,
                                    "size": item.get("size", 0),
                                    "size_gb": round(item.get("size", 0) / 1024 / 1024 / 1024, 2) if item.get("size") else 0,
                                })
                except Exception:
                    # 스토리지 콘텐츠 조회 실패 시 스킵
                    continue
            
            return iso_images
        except Exception:
            return []
    
    def get_node_status(self, node: str) -> Optional[Dict]:
        """
        노드 상태 정보 조회
        
        Args:
            node: 노드 이름
            
        Returns:
            노드 상태 정보
        """
        try:
            result = self._make_request(f"/nodes/{node}/status")
            return result.get("data", {})
        except Exception:
            return None
    
    def get_node_rrddata(self, node: str, timeframe: str = "hour", cf: str = "AVERAGE") -> List[Dict]:
        """
        노드 RRD 데이터 조회 (CPU, 메모리, 네트워크 등)
        
        Args:
            node: 노드 이름
            timeframe: 시간 범위 (hour, day, week, month, year)
            cf: 통계 함수 (AVERAGE, MAX)
            
        Returns:
            RRD 데이터 리스트
        """
        try:
            result = self._make_request(f"/nodes/{node}/rrddata", params={"timeframe": timeframe, "cf": cf})
            return result.get("data", [])
        except Exception:
            return []
    
    def get_vm_status(self, node: str, vmid: int) -> Optional[Dict]:
        """
        VM 현재 상태 조회
        
        Args:
            node: 노드 이름
            vmid: VM ID
            
        Returns:
            VM 상태 정보
        """
        try:
            result = self._make_request(f"/nodes/{node}/qemu/{vmid}/status/current")
            return result.get("data", {})
        except Exception:
            return None
    
    def get_vm_rrddata(self, node: str, vmid: int, timeframe: str = "hour", cf: str = "AVERAGE") -> List[Dict]:
        """
        VM RRD 데이터 조회 (CPU, 메모리, 네트워크 등)
        
        Args:
            node: 노드 이름
            vmid: VM ID
            timeframe: 시간 범위 (hour, day, week, month, year)
            cf: 통계 함수 (AVERAGE, MAX)
            
        Returns:
            RRD 데이터 리스트
        """
        try:
            result = self._make_request(f"/nodes/{node}/qemu/{vmid}/rrddata", params={"timeframe": timeframe, "cf": cf})
            return result.get("data", [])
        except Exception:
            return []
    
    def get_all_nodes_monitoring(self) -> List[Dict]:
        """
        모든 노드의 모니터링 정보 조회
        
        Returns:
            노드 모니터링 정보 리스트
        """
        try:
            nodes = self.get_nodes()
            monitoring_data = []
            
            for node_info in nodes:
                node_name = node_info.get("id") or node_info.get("server_id")
                if not node_name:
                    continue
                
                # 노드 상태
                status = self.get_node_status(node_name)
                # 최근 RRD 데이터 (1시간)
                rrd_data = self.get_node_rrddata(node_name, timeframe="hour")
                
                # RRD 데이터에서 최신 값 추출
                latest_rrd = rrd_data[-1] if rrd_data else {}
                
                # CPU 필드가 있는 최신 데이터 포인트 찾기 (일부 포인트에는 cpu 필드가 없을 수 있음)
                cpu_usage_raw = None
                if rrd_data:
                    # 역순으로 검색하여 cpu 필드가 있는 최신 데이터 찾기
                    for rrd_point in reversed(rrd_data):
                        if "cpu" in rrd_point and rrd_point.get("cpu") is not None:
                            cpu_usage_raw = rrd_point.get("cpu")
                            break
                
                # 노드 상태 판단 (uptime이 있으면 online)
                node_status = "online" if status and status.get("uptime", 0) > 0 else "unknown"
                
                # CPU 사용률 (RRD의 cpu는 0-1 범위이므로 100을 곱함)
                # cpu_usage_raw가 None이면 0으로 처리
                cpu_usage_percent = float(cpu_usage_raw) * 100 if cpu_usage_raw is not None else 0
                
                # 메모리 정보 (RRD 데이터에서 가져오거나 status에서 가져오기)
                memory_total = latest_rrd.get("memtotal") if latest_rrd and latest_rrd.get("memtotal") else (status.get("memory", {}).get("total", 0) if status else 0)
                memory_used = latest_rrd.get("memused") if latest_rrd and latest_rrd.get("memused") else (status.get("memory", {}).get("used", 0) if status else 0)
                memory_usage_percent = (memory_used / memory_total * 100) if memory_total > 0 else 0
                
                # Load average (RRD 데이터에서 가져오거나 status에서 가져오기)
                load_avg_raw = latest_rrd.get("loadavg") if latest_rrd and latest_rrd.get("loadavg") else None
                if load_avg_raw is None:
                    load_avg_raw = status.get("loadavg", [0, 0, 0]) if status else [0, 0, 0]
                
                # Load average를 숫자 배열로 변환
                load_avg = []
                if isinstance(load_avg_raw, (list, tuple)):
                    for load in load_avg_raw:
                        try:
                            load_avg.append(float(load) if isinstance(load, str) else load)
                        except (ValueError, TypeError):
                            load_avg.append(0.0)
                elif isinstance(load_avg_raw, (int, float)):
                    # 단일 값인 경우 (RRD 데이터)
                    load_avg = [float(load_avg_raw), float(load_avg_raw), float(load_avg_raw)]
                else:
                    load_avg = [0.0, 0.0, 0.0]
                
                # 디스크 정보 조회 (각 노드의 모든 스토리지 개별 정보)
                # /nodes/{node}/storage 엔드포인트는 이미 total, used, avail 정보를 포함함
                storages = []
                disk_total = 0
                disk_used = 0
                try:
                    storages_result = self._make_request(f"/nodes/{node_name}/storage")
                    storage_list = storages_result.get("data", [])
                    
                    for storage in storage_list:
                        storage_name = storage.get("storage", "")
                        if not storage_name:
                            continue
                        
                        # /nodes/{node}/storage 응답에 이미 total, used, avail 정보가 포함되어 있음
                        storage_total = storage.get("total", 0)
                        storage_used = storage.get("used", 0)
                        storage_avail = storage.get("avail", 0)
                        storage_type = storage.get("type", "unknown")
                        storage_enabled = storage.get("enabled", 0)
                        storage_active = storage.get("active", 0)
                        
                        # 용량 정보가 있고 활성화된 스토리지만 추가
                        if storage_total and storage_total > 0 and storage_enabled:
                            storage_total_gb = round(storage_total / 1024 / 1024 / 1024, 2)
                            storage_used_gb = round(storage_used / 1024 / 1024 / 1024, 2)
                            
                            # avail이 있으면 사용, 없으면 계산
                            if storage_avail and storage_avail > 0:
                                storage_available_gb = round(storage_avail / 1024 / 1024 / 1024, 2)
                            else:
                                storage_available_gb = round((storage_total - storage_used) / 1024 / 1024 / 1024, 2)
                            
                            storage_usage_percent = (storage_used / storage_total * 100) if storage_total > 0 else 0
                            
                            storages.append({
                                "name": storage_name,
                                "type": storage_type,
                                "total_gb": storage_total_gb,
                                "used_gb": storage_used_gb,
                                "available_gb": storage_available_gb,
                                "usage_percent": round(storage_usage_percent, 2),
                                "active": bool(storage_active),
                            })
                            
                            disk_total += storage_total
                            disk_used += storage_used
                    
                    # 스토리지 목록을 정렬 (NFS 타입은 맨 마지막에)
                    # 정렬 키: (NFS 여부, 이름) - NFS가 아닌 것들이 먼저, 그 다음 NFS가 이름순으로
                    storages.sort(key=lambda x: (x["type"] == "nfs", x["name"].lower()))
                except Exception as e:
                    # 스토리지 목록 조회 실패 시 기본값 유지 (에러 로깅)
                    print(f"스토리지 목록 조회 실패 ({node_name}): {str(e)}")
                    pass
                
                disk_total_gb = round(disk_total / 1024 / 1024 / 1024, 2) if disk_total else 0
                disk_used_gb = round(disk_used / 1024 / 1024 / 1024, 2) if disk_used else 0
                disk_usage_percent = (disk_used / disk_total * 100) if disk_total > 0 else 0
                
                monitoring_data.append({
                    "node": node_name,
                    "name": node_info.get("name", node_name),
                    "status": node_status,
                    "cpu_total": status.get("cpuinfo", {}).get("cpus", 0) if status else 0,
                    "cpu_usage_percent": round(cpu_usage_percent, 2),
                    "memory_total_gb": round(memory_total / 1024 / 1024 / 1024, 2) if memory_total else 0,
                    "memory_used_gb": round(memory_used / 1024 / 1024 / 1024, 2) if memory_used else 0,
                    "memory_usage_percent": round(memory_usage_percent, 2),
                    "disk_total_gb": disk_total_gb,
                    "disk_used_gb": disk_used_gb,
                    "disk_usage_percent": round(disk_usage_percent, 2),
                    "storages": storages,  # 개별 스토리지 목록
                    "uptime": status.get("uptime", 0) if status else 0,
                    "load_avg": load_avg,
                })
            
            return monitoring_data
        except Exception:
            return []
