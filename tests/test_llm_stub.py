"""StubProvider 的测试。"""

from __future__ import annotations

from jarvis.llm.base import AssistantMessage, Message, ToolCall
from jarvis.llm.stub_provider import DEFAULT_REPLY, StubProvider


async def test_returns_default_reply_when_queue_is_empty() -> None:
    provider = StubProvider()

    result = await provider.chat([Message(role="user", content="打开客厅灯")])

    assert result.content == DEFAULT_REPLY
    assert result.tool_calls == []


async def test_returns_scripted_responses_in_order() -> None:
    provider = StubProvider(
        [
            AssistantMessage(content="first"),
            AssistantMessage(
                content="",
                tool_calls=[ToolCall(name="turn_on_light", arguments={"room": "living_room"})],
            ),
        ]
    )

    first = await provider.chat([Message(role="user", content="hi")])
    second = await provider.chat([Message(role="user", content="开灯")])
    third = await provider.chat([Message(role="user", content="再来")])

    assert first.content == "first"
    assert second.tool_calls[0].name == "turn_on_light"
    assert second.tool_calls[0].arguments == {"room": "living_room"}
    assert third.content == DEFAULT_REPLY


def test_enqueue_appends_response() -> None:
    provider = StubProvider()
    provider.enqueue(AssistantMessage(content="later"))

    assert len(provider._queue) == 1  # noqa: SLF001


async def test_health_check_reports_unavailable() -> None:
    """桩不是真模型，必须如实报不可用，好让 UI 走降级显示。"""
    provider = StubProvider()

    health = await provider.health_check()

    assert health.available is False
    assert health.detail
