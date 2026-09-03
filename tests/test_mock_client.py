"""MockHomeAssistantClient 的行为测试（Phase 3）。

它存在的意义是让上层测试不依赖 HA 容器。
因此这里要验证它**真的会改变内存状态**，而不只是"调用返回成功"——
否则上层的工具逻辑根本没被真正验证到。
"""

from __future__ import annotations

from jarvis.ha.client import HomeAssistantClient
from jarvis.ha.mock_client import MockHomeAssistantClient
from jarvis.ha.models import HAErrorCode
from jarvis.ha.protocol import HomeAssistantProtocol


def test_real_client_satisfies_protocol() -> None:
    """真实客户端符合接口契约。"""
    assert isinstance(HomeAssistantClient("http://ha.test", "t"), HomeAssistantProtocol)


def test_mock_client_satisfies_protocol() -> None:
    """测试替身也符合同一份契约 —— 这是它能顶替真实客户端的前提。"""
    assert isinstance(MockHomeAssistantClient(), HomeAssistantProtocol)


async def test_health_check_ok_by_default() -> None:
    health = await MockHomeAssistantClient().health_check()
    assert health.available is True
    assert health.detail == "ok"


async def test_call_service_changes_state() -> None:
    client = MockHomeAssistantClient({"light.living_room_light": "off"})

    result = await client.call_service(
        "light", "turn_on", {"entity_id": "light.living_room_light"}
    )

    assert result.ok is True
    assert client.state_of("light.living_room_light") == "on"


async def test_state_change_is_visible_through_get_state() -> None:
    client = MockHomeAssistantClient({"light.living_room_light": "off"})
    await client.call_service("light", "turn_on", {"entity_id": "light.living_room_light"})

    result = await client.get_state("light.living_room_light")

    assert result.ok is True
    assert result.data is not None
    assert result.data.state == "on"
    assert result.data.is_on is True


async def test_calls_are_recorded_for_assertions() -> None:
    client = MockHomeAssistantClient({"light.living_room_light": "off"})
    await client.call_service("light", "turn_on", {"entity_id": "light.living_room_light"})
    await client.call_service("light", "turn_off", {"entity_id": "light.living_room_light"})

    assert [(c.domain, c.service) for c in client.calls] == [
        ("light", "turn_on"),
        ("light", "turn_off"),
    ]
    assert client.calls[0].data == {"entity_id": "light.living_room_light"}


async def test_get_state_not_found() -> None:
    result = await MockHomeAssistantClient().get_state("light.nope")

    assert result.ok is False
    assert result.error_code == HAErrorCode.NOT_FOUND


async def test_turn_off_after_turn_on() -> None:
    client = MockHomeAssistantClient({"light.living_room_light": "on"})
    await client.call_service("light", "turn_off", {"entity_id": "light.living_room_light"})
    assert client.state_of("light.living_room_light") == "off"


async def test_unavailable_mode_fails_every_operation() -> None:
    client = MockHomeAssistantClient({"light.living_room_light": "off"}, available=False)

    assert (await client.health_check()).available is False
    assert (
        await client.get_state("light.living_room_light")
    ).error_code == HAErrorCode.UNAVAILABLE
    assert (await client.get_states()).error_code == HAErrorCode.UNAVAILABLE
    failed = await client.call_service(
        "light", "turn_on", {"entity_id": "light.living_room_light"}
    )
    assert failed.error_code == HAErrorCode.UNAVAILABLE


async def test_missing_token_mode() -> None:
    client = MockHomeAssistantClient(token_configured=False)

    result = await client.call_service("light", "turn_on", {})

    assert result.error_code == HAErrorCode.NOT_CONFIGURED


async def test_only_configured_service_fails() -> None:
    client = MockHomeAssistantClient(
        {"light.living_room_light": "off", "light.bedroom_light": "off"},
        fail_services={"light.turn_on"},
    )

    failed = await client.call_service(
        "light", "turn_on", {"entity_id": "light.living_room_light"}
    )
    succeeded = await client.call_service(
        "light", "turn_off", {"entity_id": "light.bedroom_light"}
    )

    assert failed.ok is False
    assert failed.error_code == HAErrorCode.SERVER_ERROR
    assert succeeded.ok is True


async def test_set_temperature_updates_attribute() -> None:
    client = MockHomeAssistantClient({"climate.living_room_ac": "cool"})

    await client.call_service(
        "climate",
        "set_temperature",
        {"entity_id": "climate.living_room_ac", "temperature": 24},
    )
    result = await client.get_state("climate.living_room_ac")

    assert result.ok is True
    assert result.data is not None
    assert result.data.attributes["temperature"] == 24


async def test_cover_and_lock_state_transitions() -> None:
    client = MockHomeAssistantClient(
        {"cover.living_room_curtain": "closed", "lock.front_door": "locked"}
    )

    await client.call_service("cover", "open_cover", {"entity_id": "cover.living_room_curtain"})
    await client.call_service("lock", "unlock", {"entity_id": "lock.front_door"})

    assert client.state_of("cover.living_room_curtain") == "open"
    assert client.state_of("lock.front_door") == "unlocked"


async def test_unknown_service_is_allowed() -> None:
    """没模拟到的服务也要放行 —— 不能因为我们没覆盖就让上层误判失败。"""
    client = MockHomeAssistantClient({"lock.front_door": "locked"})

    result = await client.call_service("lock", "open", {"entity_id": "lock.front_door"})

    assert result.ok is True


async def test_multiple_entity_ids_in_one_call() -> None:
    client = MockHomeAssistantClient(
        {"light.living_room_light": "off", "light.bedroom_light": "off"}
    )

    await client.call_service(
        "light",
        "turn_on",
        {"entity_id": ["light.living_room_light", "light.bedroom_light"]},
    )

    assert client.state_of("light.living_room_light") == "on"
    assert client.state_of("light.bedroom_light") == "on"
