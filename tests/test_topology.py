"""家庭拓扑的测试（Phase 3）。

拓扑本质上是一张"映射表"，纯内存可测，**不需要 HA 容器**。

重点验证两件事：
1. ``resolve()`` 能正确把 (房间, 设备) 翻译成 entity_id
2. 查不到时返回结构化错误（ok=False + 错误码），**绝不抛异常**
"""

from __future__ import annotations

from typing import Any

import pytest

from jarvis.home.topology import (
    DEFAULT_TOPOLOGY_PATH,
    TopologyError,
    TopologyErrorCode,
    load_topology,
    parse_topology,
)


@pytest.fixture(scope="module")
def topology():
    """直接加载仓库里那份真实的拓扑配置。"""
    return load_topology()


def _room(**devices: Any) -> dict[str, Any]:
    """构造一个最小合法的拓扑，供校验类测试改写。"""
    return {
        "version": 1,
        "rooms": {"test": {"name": "测试间", "devices": devices}},
    }


# ── 解析 ──────────────────────────────────────────────────────
def test_default_topology_file_exists() -> None:
    assert DEFAULT_TOPOLOGY_PATH.exists(), "仓库里应当存在 config/home_topology.yaml"


def test_resolve_returns_entity_id(topology) -> None:
    result = topology.resolve("living_room", "light")

    assert result.ok is True
    assert result.entity_id == "light.living_room_light"
    assert result.device is not None
    assert result.device.name == "客厅灯"
    assert result.device.domain == "light"


def test_resolve_works_for_every_declared_device(topology) -> None:
    """拓扑里声明的每个设备都必须能解析回它自己的 entity_id。"""
    for room_key, room in topology.rooms.items():
        for device_key, device in room.devices.items():
            result = topology.resolve(room_key, device_key)
            assert result.ok, f"{room_key}.{device_key} 应当可解析"
            assert result.entity_id == device.entity_id


def test_resolve_unknown_room_returns_structured_error(topology) -> None:
    result = topology.resolve("nonexistent_room", "light")

    assert result.ok is False
    assert result.error == TopologyErrorCode.UNKNOWN_ROOM
    assert result.entity_id == ""
    assert "nonexistent_room" in result.message


def test_resolve_unknown_device_returns_structured_error(topology) -> None:
    result = topology.resolve("living_room", "nonexistent_device")

    assert result.ok is False
    assert result.error == TopologyErrorCode.UNKNOWN_DEVICE
    assert result.message, "失败时也要给出能直接回复用户的话"


def test_resolve_never_raises_on_weird_input(topology) -> None:
    """任何离谱输入都必须返回结果对象，绝不能抛异常。"""
    for room, device in [("", ""), (None, None), ("客厅", "灯"), ("LIVING_ROOM", "LIGHT")]:
        result = topology.resolve(room, device)  # type: ignore[arg-type]
        assert result.ok is False


# ── 数据完整性 ────────────────────────────────────────────────
def test_all_entity_ids_are_unique(topology) -> None:
    entity_ids = topology.all_entity_ids()
    assert entity_ids, "拓扑不应为空"
    assert len(entity_ids) == len(set(entity_ids)), "entity_id 不允许重复"


def test_entity_id_domain_matches_declared_domain(topology) -> None:
    for device in topology.all_devices():
        assert device.entity_id.startswith(f"{device.domain}."), device.entity_id


def test_capabilities_are_declared(topology) -> None:
    for device in topology.all_devices():
        assert device.capabilities, f"{device.entity_id} 未声明 capabilities"


# ── 中文别名查找（给 Phase 7 规则路由用）──────────────────────
def test_find_room_by_chinese_alias(topology) -> None:
    assert topology.find_room("打开客厅灯") == "living_room"
    assert topology.find_room("卧室") == "bedroom"
    assert topology.find_room("书房") == "study"
    assert topology.find_room("厨房") == "kitchen"
    assert topology.find_room("门口") == "entrance"
    assert topology.find_room("全屋") == "household"


def test_find_device_by_chinese_alias(topology) -> None:
    assert topology.find_device("living_room", "把客厅灯打开") == "light"
    assert topology.find_device("living_room", "客厅空调调到 26 度") == "ac"
    assert topology.find_device("living_room", "客厅现在几度") == "temperature"
    assert topology.find_device("living_room", "打开窗帘") == "curtain"


def test_find_room_returns_none_when_unknown(topology) -> None:
    assert topology.find_room("火星") is None
    assert topology.find_room("") is None


def test_find_device_returns_none_for_unknown_room(topology) -> None:
    assert topology.find_device("nonexistent_room", "灯") is None


# ── 加载与校验（这些是配置缺陷，必须抛异常）──────────────────
def test_load_missing_file_raises(tmp_path) -> None:
    with pytest.raises(TopologyError):
        load_topology(tmp_path / "does_not_exist.yaml")


def test_parse_rejects_missing_rooms() -> None:
    with pytest.raises(TopologyError, match="rooms"):
        parse_topology({"version": 1})


def test_parse_rejects_malformed_entity_id() -> None:
    raw = _room(d={"name": "灯", "entity_id": "BAD ID", "domain": "light", "capabilities": ["on_off"]})
    with pytest.raises(TopologyError, match="entity_id"):
        parse_topology(raw)


def test_parse_rejects_domain_mismatch() -> None:
    raw = _room(
        d={"name": "灯", "entity_id": "light.living_room_light", "domain": "switch", "capabilities": ["on_off"]}
    )
    with pytest.raises(TopologyError, match="不一致"):
        parse_topology(raw)


def test_parse_rejects_unknown_capability() -> None:
    raw = _room(
        d={"name": "灯", "entity_id": "light.test", "domain": "light", "capabilities": ["fly"]}
    )
    with pytest.raises(TopologyError, match="未知 capability"):
        parse_topology(raw)


def test_parse_rejects_duplicate_entity_id() -> None:
    raw = {
        "version": 1,
        "rooms": {
            "a": {
                "name": "A",
                "devices": {
                    "light": {
                        "name": "灯",
                        "entity_id": "light.dup",
                        "domain": "light",
                        "capabilities": ["on_off"],
                    }
                },
            },
            "b": {
                "name": "B",
                "devices": {
                    "light": {
                        "name": "灯",
                        "entity_id": "light.dup",
                        "domain": "light",
                        "capabilities": ["on_off"],
                    }
                },
            },
        },
    }
    with pytest.raises(TopologyError, match="重复"):
        parse_topology(raw)


def test_parse_rejects_device_without_name() -> None:
    raw = _room(d={"entity_id": "light.test", "domain": "light", "capabilities": ["on_off"]})
    with pytest.raises(TopologyError, match="name"):
        parse_topology(raw)
