"""
Proxmox 리소스 조회 API 라우트 모듈 (조회 전용)

이 모듈은 Proxmox에서 리소스 정보를 조회하는 API 엔드포인트를 제공합니다.
**중요**: 모든 엔드포인트는 GET 메서드만 사용하며, 리소스 생성/수정/삭제는 Terraform을 통해 수행합니다.

아키텍처 원칙:
- 조회(Read): Proxmox API 직접 호출
- 제어(Create/Update/Delete): Terraform 사용 (POST /api/deploy)

API 엔드포인트:
- GET /api/servers: 노드(서버) 목록 조회
- GET /api/templates: 템플릿 목록 조회
- GET /api/vms: VM 목록 조회 (템플릿 제외)
- GET /api/servers/{server_id}/storage: 서버의 스토리지 목록 조회
- GET /api/servers/{server_id}/networks: 서버의 네트워크 목록 조회
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.proxmox_service import ProxmoxService

router = APIRouter()
proxmox_service = ProxmoxService()


class ServerResponse(BaseModel):
    """서버 응답 모델"""
    servers: List[dict]


class TemplateResponse(BaseModel):
    """템플릿 응답 모델"""
    templates: List[dict]


class StorageResponse(BaseModel):
    """스토리지 응답 모델"""
    storages: List[dict]


class NetworkResponse(BaseModel):
    """네트워크 응답 모델"""
    networks: List[dict]


class VMResponse(BaseModel):
    """VM 응답 모델"""
    vms: List[dict]


class ISOResponse(BaseModel):
    """ISO 이미지 응답 모델"""
    iso_images: List[dict]


@router.get("/servers", response_model=ServerResponse)
async def get_servers():
    """
    Proxmox 노드(서버) 목록 조회
    
    Returns:
        ServerResponse: 서버 목록
    """
    try:
        servers = proxmox_service.get_nodes()
        # 디버깅: 서버 목록 확인
        if not servers:
            print("경고: 서버 목록이 비어있습니다. Proxmox 연결을 확인하세요.")
        return ServerResponse(servers=servers)
    except Exception as e:
        print(f"서버 목록 조회 중 예외 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"서버 목록 조회 실패: {str(e)}"
        )


@router.get("/templates", response_model=TemplateResponse)
async def get_templates():
    """
    Proxmox 템플릿 목록 조회
    
    Returns:
        TemplateResponse: 템플릿 목록
    """
    try:
        templates = proxmox_service.get_templates()
        return TemplateResponse(templates=templates)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"템플릿 목록 조회 실패: {str(e)}"
        )


@router.get("/vms", response_model=VMResponse)
async def get_vms():
    """
    Proxmox VM 목록 조회 (템플릿 제외)
    
    Returns:
        VMResponse: VM 목록
    """
    try:
        vms = proxmox_service.get_vms()
        return VMResponse(vms=vms)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"VM 목록 조회 실패: {str(e)}"
        )


@router.get("/instances")
async def get_instances():
    """
    인스턴스 목록 조회 (VM 목록과 동일)
    
    프론트엔드 호환성을 위해 제공되는 엔드포인트입니다.
    /api/vms와 동일한 데이터를 반환하지만, 응답 형식을 인스턴스 형식으로 변환합니다.
    
    Returns:
        인스턴스 목록 (VM 정보를 인스턴스 형식으로 변환)
    """
    try:
        vms = proxmox_service.get_vms()
        
        # VM 정보를 인스턴스 형식으로 변환
        instances = []
        for vm in vms:
            instances.append({
                "id": vm.get("id") or vm.get("vm_id"),
                "server_name": vm.get("name"),
                "name": vm.get("name"),
                "status": vm.get("status", "unknown"),
                "cpu_cores": vm.get("cpu_cores", 0),
                "memory_gb": vm.get("memory_gb", 0),
                "memory": vm.get("memory_gb", 0),
                "cpu": vm.get("cpu_cores", 0),
                "region": vm.get("node", ""),
                "vmid": vm.get("vmid"),
                "node": vm.get("node"),
                "disk_gb": vm.get("disk_gb", 0),  # 총 디스크 크기
                "disks": vm.get("disks", []),  # 디스크 목록
            })
        
        return {"instances": instances}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"인스턴스 목록 조회 실패: {str(e)}"
        )


@router.get("/servers/{server_id}/storage", response_model=StorageResponse)
async def get_server_storage(server_id: str):
    """
    특정 서버의 스토리지 목록 조회
    
    Args:
        server_id: 서버(노드) ID
        
    Returns:
        StorageResponse: 스토리지 목록
    """
    try:
        storages = proxmox_service.get_storages(node=server_id)
        return StorageResponse(storages=storages)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"스토리지 목록 조회 실패: {str(e)}"
        )


@router.get("/servers/{server_id}/networks", response_model=NetworkResponse)
async def get_server_networks(server_id: str):
    """
    특정 서버의 네트워크 목록 조회
    
    Args:
        server_id: 서버(노드) ID
        
    Returns:
        NetworkResponse: 네트워크 목록
    """
    try:
        networks = proxmox_service.get_networks(node=server_id)
        return NetworkResponse(networks=networks)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"네트워크 목록 조회 실패: {str(e)}"
        )


@router.get("/servers/{server_id}/vms", response_model=VMResponse)
async def get_server_vms(server_id: str):
    """
    특정 서버의 VM 목록 조회 (템플릿 제외)
    
    Args:
        server_id: 서버(노드) ID
        
    Returns:
        VMResponse: VM 목록
    """
    try:
        vms = proxmox_service.get_vms(node=server_id)
        return VMResponse(vms=vms)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"VM 목록 조회 실패: {str(e)}"
        )


@router.get("/monitoring/nodes")
async def get_nodes_monitoring():
    """
    모든 노드의 모니터링 정보 조회
    
    Returns:
        노드 모니터링 정보 리스트
    """
    try:
        monitoring_data = proxmox_service.get_all_nodes_monitoring()
        return {"nodes": monitoring_data}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"노드 모니터링 정보 조회 실패: {str(e)}"
        )


@router.get("/monitoring/nodes/{node_id}")
async def get_node_monitoring(node_id: str):
    """
    특정 노드의 상세 모니터링 정보 조회
    
    Args:
        node_id: 노드 ID
        
    Returns:
        노드 상세 모니터링 정보
    """
    try:
        status = proxmox_service.get_node_status(node_id)
        rrd_data = proxmox_service.get_node_rrddata(node_id, timeframe="hour")
        
        return {
            "node": node_id,
            "status": status,
            "rrd_data": rrd_data,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"노드 모니터링 정보 조회 실패: {str(e)}"
        )


@router.get("/monitoring/vms/{node_id}/{vmid}")
async def get_vm_monitoring(node_id: str, vmid: int):
    """
    특정 VM의 모니터링 정보 조회
    
    Args:
        node_id: 노드 ID
        vmid: VM ID
        
    Returns:
        VM 모니터링 정보
    """
    try:
        status = proxmox_service.get_vm_status(node_id, vmid)
        rrd_data = proxmox_service.get_vm_rrddata(node_id, vmid, timeframe="hour")
        
        return {
            "node": node_id,
            "vmid": vmid,
            "status": status,
            "rrd_data": rrd_data,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"VM 모니터링 정보 조회 실패: {str(e)}"
        )


@router.get("/servers/{server_id}/iso-images", response_model=ISOResponse)
async def get_server_iso_images(server_id: str):
    """
    특정 서버의 ISO 이미지 목록 조회
    
    Args:
        server_id: 서버(노드) ID
        
    Returns:
        ISOResponse: ISO 이미지 목록
    """
    try:
        iso_images = proxmox_service.get_iso_images(node=server_id)
        return ISOResponse(iso_images=iso_images)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"ISO 이미지 목록 조회 실패: {str(e)}"
        )
