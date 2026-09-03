"""HomeAssistantClient 的测试。

重点验证：外部服务出任何状况时，客户端都返回结构化结果而不是抛异常。
这些测试不需要真实的 HA 实例。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from jarvis.ha.client import HomeAssistantClient


def make_handler(*, root_status: int = 200, config_status: int = 200) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/":
            return httpx.Response(root_status, json={"message": "API running."})
        if request.url.path == "/api/config":
            return httpx.Response(config_status, json={"version": "2026.1.0"})
        return httpx.Response(404)

    return handler


async def test_health_check_reports_ok(ha_client: Callable[..., Any]) -> None:
    async with ha_client(make_handler()) as client:
        result = await client.health_check()

    assert result.available is True
    assert result.detail == "ok"
    assert result.latency_ms is not None and result.latency_ms >= 0


async def test_health_check_reports_missing_token(ha_client: Callable[..., Any]) -> None:
    async with ha_client(make_handler(), token="") as client:
        result = await client.health_check()

    assert result.available is False
    assert "JARVIS_HA_TOKEN" in result.detail


async def test_health_check_reports_unauthorized(ha_client: Callable[..., Any]) -> None:
    """令牌错误时明确报未授权，而不是笼统地报连不上。"""
    async with ha_client(make_handler(config_status=401)) as client:
        result = await client.health_check()

    assert result.available is False
    assert "令牌" in result.detail


async def test_health_check_reports_server_error(ha_client: Callable[..., Any]) -> None:
    async with ha_client(make_handler(root_status=500)) as client:
        result = await client.health_check()

    assert result.available is False
    assert "500" in result.detail


async def test_health_check_never_raises_when_unreachable() -> None:
    """HA 根本没起时，必须返回结构化结果，绝不能把异常抛给上层。"""
    client = HomeAssistantClient("http://127.0.0.1:9", "token", timeout=0.5)
    try:
        result = await client.health_check()
    finally:
        await client.aclose()

    assert result.available is False
    assert result.detail


async def test_health_check_reports_timeout(ha_client: Callable[..., Any]) -> None:
    def slow_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("too slow", request=request)

    async with ha_client(slow_handler) as client:
        result = await client.health_check()

    assert result.available is False
    assert "超时" in result.detail
