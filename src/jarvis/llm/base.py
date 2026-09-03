"""LLM 抽象层。

Agent 只依赖 LLMProvider 协议，不关心底层是 Ollama、桩实现还是别的东西。
这样换模型、换推理后端都不需要改动 Agent 与工具层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(slots=True)
class ToolSpec:
    """供 LLM 使用的工具描述。由 Tool 层生成，避免两处维护。"""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass(slots=True)
class ToolCall:
    """模型请求调用的工具。"""

    name: str
    arguments: dict[str, Any]
    call_id: str | None = None


@dataclass(slots=True)
class Message:
    """对话消息。role 为 tool 时，tool_call_id 指明对应的调用。"""

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass(slots=True)
class AssistantMessage:
    """模型的回复：可能是一段文本，也可能是若干工具调用。"""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(slots=True)
class ProviderHealth:
    available: bool
    detail: str = ""


class LLMError(Exception):
    """LLM 调用失败。调用方应捕获后降级，不应让整个请求崩溃。"""


@runtime_checkable
class LLMProvider(Protocol):
    """所有 LLM 后端都要实现这个协议。"""

    name: str

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AssistantMessage:
        """发起一次对话，返回文本或工具调用。"""
        ...

    async def health_check(self) -> ProviderHealth:
        """探测后端是否可用。失败时返回 available=False，不抛异常。"""
        ...
