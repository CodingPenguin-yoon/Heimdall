"""
배포 작업 상태/로그 조회 API 라우트 (task 도메인)

기존 `app.routes.status`, `app.routes.logs` 라우터를 도메인 구조로 옮긴 구현입니다.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.task.manager import task_manager


router = APIRouter()


class StatusResponse(BaseModel):
    """상태 응답 모델"""

    task_id: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class LogsResponse(BaseModel):
    """로그 응답 모델"""

    task_id: str
    logs: List[str]
    total_lines: int


@router.get("/status/{task_id}", response_model=StatusResponse)
async def get_status(task_id: str):
    """
    배포 작업 상태 조회
    """
    task_info = task_manager.get_status(task_id)

    if task_info is None:
        raise HTTPException(
            status_code=404,
            detail=f"작업을 찾을 수 없습니다: {task_id}",
        )

    return StatusResponse(
        task_id=task_id,
        status=task_info["status"],
        created_at=task_info.get("created_at"),
        updated_at=task_info.get("updated_at"),
    )


@router.get("/logs/{task_id}", response_model=LogsResponse)
async def get_logs(task_id: str):
    """
    배포 작업 로그 조회
    """
    task_info = task_manager.get_status(task_id)
    if task_info is None:
        raise HTTPException(
            status_code=404,
            detail=f"작업을 찾을 수 없습니다: {task_id}",
        )

    logs = task_manager.get_logs(task_id)

    return LogsResponse(
        task_id=task_id,
        logs=logs,
        total_lines=len(logs),
    )


__all__ = ["router"]

