"""按配置创建 LLM Provider。

这是「换模型 / 换后端」的唯一入口。Agent 永远只拿到 LLMProvider，
不关心背后是什么。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging import get_logger
from .base import LLMError, LLMProvider
from .stub_provider import StubProvider

if TYPE_CHECKING:
    from ..config import Settings

logger = get_logger(__name__)


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "stub":
        logger.info("使用 stub LLM provider（不调用任何模型）")
        return StubProvider()

    if settings.llm_provider == "ollama":
        # Phase 8 接入真实模型。先抛明确错误，避免静默退化成桩。
        raise LLMError("OllamaProvider 尚未实现，将在 Phase 8 提供")

    raise LLMError(f"未知的 LLM provider：{settings.llm_provider!r}")
