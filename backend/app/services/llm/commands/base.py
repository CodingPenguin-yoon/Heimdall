from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

from fastapi import BackgroundTasks


class LlmInfraCommand(ABC):
    """
    LLM이 제안한 인프라 액션을 실제 서비스 호출로 연결하는 커맨드 베이스 클래스.

    각 커맨드는:
    - params 딕셔너리를 받아
    - (result_message, raw_result) 튜플을 반환합니다.
    """

    @abstractmethod
    def execute(
        self,
        params: Dict[str, Any],
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Tuple[str, Any]:
        raise NotImplementedError

