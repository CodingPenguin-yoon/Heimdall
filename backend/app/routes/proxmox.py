"""
Proxmox 리소스 조회 API 라우트 모듈

이 모듈은 Proxmox에서 서버, 템플릿, 스토리지, 네트워크 정보를 조회하는 API 엔드포인트를 제공합니다.
- GET /api/servers: 노드(서버) 목록 조회
- GET /api/templates: 템플릿 목록 조회
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


@router.get("/servers", response_model=ServerResponse)
async def get_servers():
    """
    Proxmox 노드(서버) 목록 조회
    
    Returns:
        ServerResponse: 서버 목록
    """
    try:
        servers = proxmox_service.get_nodes()
        return ServerResponse(servers=servers)
    except Exception as e:
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
