"""
LLM (Gemini) 연동 서비스 도메인 래퍼.

배경/의도/목적:
- 기존 구현(`app.services.llm.llm_core`)은 그대로 두고,
  도메인 구조(`app.domains.llm.service`)에서 LLM 관련 타입과 서비스를
  한 곳에서 import 할 수 있도록 얇은 래퍼를 제공한다.
- 점진적으로 도메인 중심 구조로 옮기되, 기존 경로와의 하위 호환성을 유지한다.
"""

from __future__ import annotations

from app.services.llm.llm_core import (
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

