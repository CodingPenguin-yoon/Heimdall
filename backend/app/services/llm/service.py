"""
LLM (Gemini) 연동 서비스 모듈 (llm 도메인)

기존 app.services.llm_service 모듈을
도메인 기준으로 정리하여 이 위치로 이동했습니다.
"""

from .llm_core import (
    LLMActionDict,
    LLMChatResult,
    LLMConfig,
    LLMMessage,
    LLMService,
)

__all__ = [
    "LLMService",
    "LLMMessage",
    "LLMActionDict",
    "LLMChatResult",
    "LLMConfig",
]

