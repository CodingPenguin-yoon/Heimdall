"""
작업 상태 관리 모듈

이 모듈은 배포 작업의 상태와 로그를 메모리에 저장하고 관리합니다.
- task_id를 기반으로 작업 상태(Running, Success, Failed) 추적
- 실시간 로그 스트림 저장 및 조회 기능 제공
"""

from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime
import threading


class TaskStatus(str, Enum):
    """작업 상태 열거형"""
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCESS = "Success"
    FAILED = "Failed"


class TaskManager:
    """
    작업 상태 및 로그 관리 싱글톤 클래스
    
    배포 작업의 상태와 로그를 메모리에 저장하여 API를 통해 조회할 수 있도록 합니다.
    Thread-safe한 구조로 설계되어 동시 요청을 안전하게 처리합니다.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(TaskManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """초기화: 작업 상태 및 로그 저장소 생성"""
        if self._initialized:
            return
        
        self._tasks: Dict[str, Dict] = {}
        self._logs: Dict[str, List[str]] = {}
        self._lock = threading.Lock()
        self._initialized = True
    
    def create_task(self, task_id: str) -> None:
        """
        새로운 작업 생성
        
        Args:
            task_id: 고유 작업 식별자
        """
        with self._lock:
            self._tasks[task_id] = {
                "status": TaskStatus.PENDING,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            self._logs[task_id] = []
    
    def update_status(self, task_id: str, status: TaskStatus) -> None:
        """
        작업 상태 업데이트
        
        Args:
            task_id: 작업 식별자
            status: 새로운 상태
        """
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["status"] = status
                self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
    
    def get_status(self, task_id: str) -> Optional[Dict]:
        """
        작업 상태 조회
        
        Args:
            task_id: 작업 식별자
            
        Returns:
            작업 상태 정보 딕셔너리 또는 None
        """
        with self._lock:
            return self._tasks.get(task_id)
    
    def append_log(self, task_id: str, log_line: str) -> None:
        """
        작업 로그 추가
        
        Args:
            task_id: 작업 식별자
            log_line: 추가할 로그 라인
        """
        with self._lock:
            if task_id in self._logs:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._logs[task_id].append(f"[{timestamp}] {log_line}")
    
    def get_logs(self, task_id: str) -> List[str]:
        """
        작업 로그 조회
        
        Args:
            task_id: 작업 식별자
            
        Returns:
            로그 라인 리스트
        """
        with self._lock:
            return self._logs.get(task_id, [])
    
    def clear_task(self, task_id: str) -> None:
        """
        작업 데이터 삭제 (메모리 정리용)
        
        Args:
            task_id: 작업 식별자
        """
        with self._lock:
            self._tasks.pop(task_id, None)
            self._logs.pop(task_id, None)


# 전역 TaskManager 인스턴스
task_manager = TaskManager()
