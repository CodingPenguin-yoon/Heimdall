"""
작업 상태 조회 API 라우트 모듈

이 모듈은 배포 작업의 현재 상태를 조회하는 API 엔드포인트를 제공합니다.
- GET /api/status/{task_id}: 특정 작업의 상태 정보 반환
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.task_manager import task_manager

router = APIRouter()


class StatusResponse(BaseModel):
    """상태 응답 모델"""
    task_id: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@router.get("/status/{task_id}", response_model=StatusResponse)
async def get_status(task_id: str):
    """
    배포 작업 상태 조회
    
    task_id를 기반으로 현재 배포 작업의 상태를 반환합니다.
    가능한 상태: Pending, Running, Success, Failed
    
    Args:
        task_id: 조회할 작업의 고유 식별자
        
    Returns:
        StatusResponse: 작업 상태 정보
        
    Raises:
        HTTPException: 작업을 찾을 수 없을 때 (404)
    """
    task_info = task_manager.get_status(task_id)
    
    if task_info is None:
        raise HTTPException(
            status_code=404,
            detail=f"작업을 찾을 수 없습니다: {task_id}"
        )
    
    return StatusResponse(
        task_id=task_id,
        status=task_info["status"],
        created_at=task_info.get("created_at"),
        updated_at=task_info.get("updated_at")
    )
