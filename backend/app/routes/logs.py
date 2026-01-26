"""
작업 로그 조회 API 라우트 모듈

이 모듈은 배포 작업의 실행 로그를 조회하는 API 엔드포인트를 제공합니다.
- GET /api/logs/{task_id}: 특정 작업의 누적 로그 반환
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.services.task_manager import task_manager

router = APIRouter()


class LogsResponse(BaseModel):
    """로그 응답 모델"""
    task_id: str
    logs: List[str]
    total_lines: int


@router.get("/logs/{task_id}", response_model=LogsResponse)
async def get_logs(task_id: str):
    """
    배포 작업 로그 조회
    
    task_id를 기반으로 현재까지 수집된 모든 로그를 반환합니다.
    로그는 실시간으로 업데이트되며, 타임스탬프가 포함됩니다.
    
    Args:
        task_id: 조회할 작업의 고유 식별자
        
    Returns:
        LogsResponse: 로그 라인 리스트 및 총 라인 수
        
    Raises:
        HTTPException: 작업을 찾을 수 없을 때 (404)
    """
    # 작업 존재 여부 확인
    task_info = task_manager.get_status(task_id)
    if task_info is None:
        raise HTTPException(
            status_code=404,
            detail=f"작업을 찾을 수 없습니다: {task_id}"
        )
    
    # 로그 조회
    logs = task_manager.get_logs(task_id)
    
    return LogsResponse(
        task_id=task_id,
        logs=logs,
        total_lines=len(logs)
    )
