"""桩 LLM Provider —— 不调用任何模型。

用途：
1. 在没有 GPU 的机器上做开发，把模型的不确定性完全隔离掉
2. 测试中确定性复现模型的输出

它刻意把 health_check 报为不可用：桩不是真模型，
UI 应显示 LLM: DISCONNECTED，这正是需要验证的降级路径。
"""

from __future__ import annotations

from collections.abc import Sequence

from ..logging import get_logger
from .base import AssistantMessage, Message, ProviderHealth, ToolSpec

logger = get_logger(__name__)

DEFAULT_REPLY = (
    "当前未接入真实模型（JARVIS_LLM_PROVIDER=stub）。"
    "确定性规则可以处理的指令已正常执行；其余语句需要接入模型后才能理解。"
)


class StubProvider:
    """按预设队列返回固定回复；队列空了就返回默认文本。"""

    name = "stub"

    def __init__(
        self,
        responses: Sequence[AssistantMessage] | None = None,
        *,
        default_reply: str = DEFAULT_REPLY,
    ) -> None:
        self._queue: list[AssistantMessage] = list(responses or [])
        self._default_reply = default_reply

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AssistantMessage:
        logger.debug("stub chat：收到 %d 条消息，%d 个工具", len(messages), len(tools or []))
        if self._queue:
            return self._queue.pop(0)
        return AssistantMessage(content=self._default_reply)

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(available=False, detail="stub provider：未连接任何模型")

    # ── 测试辅助 ────────────────────────────────────────────
    def enqueue(self, response: AssistantMessage) -> None:
        """追加一个预设回复，供测试编排多轮对话。"""
        self._queue.append(response)
