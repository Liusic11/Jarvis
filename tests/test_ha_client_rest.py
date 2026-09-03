"""HomeAssistantClient 的 REST 能力测试（Phase 3）。

用 ``httpx.MockTransport`` 伪造 HA 的响应，**不需要真实的 HA 容器**。
健康检查相关的测试在 ``tests/test_ha_client.py``（Phase 1）。

重点验证三件事：
1. 成功路径能把 HA 的 JSON 转成强类型的 ``EntityState``
2. 各种失败（401 / 404 / 500 / 超时 / 没令牌）都映射成结构化错误码，不抛异常
3. **重试策略**：读操作可重试，写操作一次都不重试
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from jarvis.ha.client import HomeAssistantClient
from jarvis.ha.models import HAErrorCode

# (HTTP 方法, 路径) -> (状态码, 响应体)。字符串响应体按纯文本返回。
RouteTable = dict[tuple[str, str], tuple[int, Any]]


def state_payload(
    entity_id: str = "light.living_room_light",
    state: str = "on",
    **attributes: Any,
) -> dict[str, Any]:
    """构造一个 HA /api/states 风格的状态对象。"""
    return {
        "entity_id": entity_id,
        "state": state,
        "attributes": {"friendly_name": "客厅灯", **attributes},
        "last_changed": "2026-09-03T10:00:00+00:00",
        "last_updated": "2026-09-03T10:00:00+00:00",
    }


def make_handler(routes: RouteTable) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key not in routes:
            return httpx.Response(404, json={"message": "not found"})
        status, body = routes[key]
        if isinstance(body, str):
            return httpx.Response(status, text=body)
        return httpx.Response(status, json=body)

    return handler


# ── get_state ─────────────────────────────────────────────────
async def test_get_state_success(ha_client) -> None:
    routes = {("GET", "/api/states/light.living_room_light"): (200, state_payload())}

    async with ha_client(make_handler(routes)) as client:
        result = await client.get_state("light.living_room_light")

    assert result.ok is True
    assert result.data is not None
    assert result.data.entity_id == "light.living_room_light"
    assert result.data.state == "on"
    assert result.data.friendly_name == "客厅灯"
    assert result.data.domain == "light"
    assert result.data.is_on is True


async def test_get_state_not_found(ha_client) -> None:
    async with ha_client(make_handler({})) as client:
        result = await client.get_state("light.nope")

    assert result.ok is False
    assert result.error_code == HAErrorCode.NOT_FOUND
    assert "light.nope" in result.message


async def test_get_state_unauthorized(ha_client) -> None:
    routes = {
        ("GET", "/api/states/light.living_room_light"): (401, {"message": "Unauthorized"})
    }

    async with ha_client(make_handler(routes)) as client:
        result = await client.get_state("light.living_room_light")

    assert result.ok is False
    assert result.error_code == HAErrorCode.UNAUTHORIZED


async def test_get_state_without_token(ha_client) -> None:
    async with ha_client(make_handler({}), token="") as client:
        result = await client.get_state("light.living_room_light")

    assert result.ok is False
    assert result.error_code == HAErrorCode.NOT_CONFIGURED
    assert "JARVIS_HA_TOKEN" in result.message


async def test_get_state_maps_timeout(ha_client) -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("too slow", request=request)

    async with ha_client(slow) as client:
        result = await client.get_state("light.living_room_light")

    assert result.ok is False
    assert result.error_code == HAErrorCode.UNAVAILABLE
    assert "超时" in result.message


async def test_get_state_reports_server_error(ha_client) -> None:
    routes = {("GET", "/api/states/light.living_room_light"): (500, "boom")}

    async with ha_client(make_handler(routes)) as client:
        result = await client.get_state("light.living_room_light")

    assert result.ok is False
    assert result.error_code == HAErrorCode.UNAVAILABLE
    assert "500" in result.message


async def test_get_state_bad_json(ha_client) -> None:
    routes = {("GET", "/api/states/light.living_room_light"): (200, "not-json")}

    async with ha_client(make_handler(routes)) as client:
        result = await client.get_state("light.living_room_light")

    assert result.ok is False
    assert result.error_code == HAErrorCode.BAD_RESPONSE


# ── get_states ────────────────────────────────────────────────
async def test_get_states_returns_all(ha_client) -> None:
    routes = {
        ("GET", "/api/states"): (
            200,
            [state_payload(), state_payload("light.bedroom_light", "off")],
        )
    }

    async with ha_client(make_handler(routes)) as client:
        result = await client.get_states()

    assert result.ok is True
    assert result.data is not None
    assert len(result.data) == 2
    assert {s.entity_id for s in result.data} == {
        "light.living_room_light",
        "light.bedroom_light",
    }


async def test_get_states_without_token(ha_client) -> None:
    async with ha_client(make_handler({}), token="") as client:
        result = await client.get_states()

    assert result.ok is False
    assert result.error_code == HAErrorCode.NOT_CONFIGURED


# ── call_service ──────────────────────────────────────────────
async def test_call_service_success(ha_client) -> None:
    routes = {("POST", "/api/services/light/turn_on"): (200, [state_payload()])}

    async with ha_client(make_handler(routes)) as client:
        result = await client.call_service(
            "light", "turn_on", {"entity_id": "light.living_room_light"}
        )

    assert result.ok is True


async def test_call_service_unknown_service(ha_client) -> None:
    async with ha_client(make_handler({})) as client:
        result = await client.call_service("light", "nonexistent", {})

    assert result.ok is False
    assert result.error_code == HAErrorCode.NOT_FOUND


async def test_call_service_rejected_by_ha(ha_client) -> None:
    routes = {("POST", "/api/services/light/turn_on"): (400, "bad request")}

    async with ha_client(make_handler(routes)) as client:
        result = await client.call_service("light", "turn_on", {})

    assert result.ok is False
    assert result.error_code == HAErrorCode.INVALID_REQUEST


async def test_call_service_validates_args_before_sending(ha_client) -> None:
    """参数不合法时根本不该发出请求。"""
    sent = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        sent["n"] += 1
        return httpx.Response(200, json=[])

    async with ha_client(handler) as client:
        empty_domain = await client.call_service("", "turn_on", {})
        empty_service = await client.call_service("light", "", {})

    assert empty_domain.error_code == HAErrorCode.INVALID_REQUEST
    assert empty_service.error_code == HAErrorCode.INVALID_REQUEST
    assert sent["n"] == 0


async def test_call_service_does_not_retry(ha_client) -> None:
    """写操作一次都不重试。

    一次调用可能已经生效（灯其实开了），只是响应丢了；
    盲目重试会造成重复动作（比如连开两次锁）。
    """
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(500, text="boom")

    async with ha_client(handler) as client:
        result = await client.call_service(
            "light", "turn_on", {"entity_id": "light.living_room_light"}
        )

    assert attempts["n"] == 1, "写操作只允许发一次"
    assert result.ok is False
    assert result.error_code == HAErrorCode.UNAVAILABLE


# ── 重试策略：读操作可以重试 ──────────────────────────────────
async def test_read_retries_transient_failure_then_succeeds(ha_client) -> None:
    """读操作没有副作用，遇到瞬时故障可以重试。"""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise httpx.TimeoutException("transient", request=request)
        return httpx.Response(200, json=state_payload())

    async with ha_client(handler) as client:
        result = await client.get_state("light.living_room_light")

    assert attempts["n"] == 3
    assert result.ok is True


# ── 客户端本身 ────────────────────────────────────────────────
async def test_client_can_be_closed_without_any_call() -> None:
    """没发过任何请求就关闭，不应报错。"""
    client = HomeAssistantClient("http://127.0.0.1:9", "token", timeout=0.5)
    await client.aclose()
