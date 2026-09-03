"""家庭拓扑：逻辑语义层与 entity_id 的唯一映射。

【这一层解决什么问题】
用户和 LLM 说的是「客厅的灯」，Home Assistant 认识的是 ``light.living_room_light``。
这两者之间的翻译，**全系统只在这一个模块里发生**。

【为什么值得单独做一层】
- 解耦：将来虚拟设备换成真实设备，entity_id 必然变化。
  有这一层就只改 ``config/home_topology.yaml``，Tools / Agent / 场景一行都不用动。
- 可校验：启动时能逐个确认 entity_id 真的存在于 HA，
  避免「代码写着能开灯、实际实体不存在」这种到运行才暴露的问题。
- 语义集中：房间/设备的中文别名都在这张表里，规则路由直接查表，
  不用在代码里散落一堆 ``if "客厅" in text``。

【设计取舍：什么时候抛异常、什么时候返回值】
- ``resolve()`` **返回 Resolution，不抛异常**——用户说了一个不存在的房间，
  这是正常的业务结果（要回复他"没有这个房间"），不是程序错误。
- ``load_topology()`` / ``parse_topology()`` **抛 TopologyError**——
  YAML 写错属于配置缺陷，必须在启动阶段就炸掉，绝不能带病运行。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..config import PROJECT_ROOT

DEFAULT_TOPOLOGY_PATH = PROJECT_ROOT / "config" / "home_topology.yaml"

# entity_id 的合法形态：<小写域名>.<小写对象名>
ENTITY_ID_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z0-9_]+$")

VALID_CAPABILITIES = frozenset(
    {
        "on_off",  # 可开 / 可关
        "brightness",  # 可调亮度
        "set_temperature",  # 可设目标温度
        "open_close",  # 可开合（窗帘）
        "lock_unlock",  # 可上锁 / 解锁（高危，需二次确认）
        "start_stop",  # 可启停 / 回充（扫地机）
        "read_only",  # 只读（传感器）
    }
)


class TopologyError(Exception):
    """拓扑文件缺失或格式非法。

    这是**配置缺陷**，调用方应当让它直接把应用启动失败，
    而不是捕获后继续运行（否则会带着错误的设备映射跑起来）。
    """


class TopologyErrorCode:
    """resolve 失败时的结构化错误码，供上层判断如何回复用户。"""

    UNKNOWN_ROOM = "unknown_room"
    UNKNOWN_DEVICE = "unknown_device"


@dataclass(frozen=True)
class Device:
    """一个具体设备（灯 / 空调 / 窗帘 …）。"""

    key: str  # 逻辑键，如 "light"
    name: str  # 中文名，如 "客厅灯"
    entity_id: str  # HA 实体 id，如 "light.living_room_light"
    domain: str  # HA 域名，如 "light"
    capabilities: tuple[str, ...]
    aliases: tuple[str, ...] = ()

    @property
    def is_read_only(self) -> bool:
        return "read_only" in self.capabilities

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities


@dataclass(frozen=True)
class Room:
    """一个房间（或"全屋"这类逻辑区域），内含若干设备。"""

    key: str
    name: str
    aliases: tuple[str, ...] = ()
    devices: Mapping[str, Device] = field(default_factory=dict)

    def get(self, device_key: str) -> Device | None:
        return self.devices.get(device_key)

    @property
    def device_keys(self) -> tuple[str, ...]:
        return tuple(self.devices.keys())


@dataclass(frozen=True)
class Resolution:
    """``resolve()`` 的返回值。

    刻意设计成"结果对象"而不是抛异常：查不到房间/设备是要回复用户的正常情况，
    调用方不需要写 try/except，只要看 ``ok``。
    """

    ok: bool
    entity_id: str = ""
    device: Device | None = None
    error: str = ""  # 结构化错误码，见 TopologyErrorCode
    message: str = ""  # 可以直接说给用户听的人话

    @classmethod
    def success(cls, device: Device) -> Resolution:
        return cls(ok=True, entity_id=device.entity_id, device=device)

    @classmethod
    def failure(cls, error: str, message: str) -> Resolution:
        return cls(ok=False, error=error, message=message)


@dataclass(frozen=True)
class Topology:
    """整张家庭拓扑。"""

    version: int = 1
    rooms: Mapping[str, Room] = field(default_factory=dict)
    source: str = ""

    # ── 精确解析 ──────────────────────────────────────────────
    def resolve(self, room_key: str, device_key: str) -> Resolution:
        """把 (房间, 设备) 翻译成 entity_id。

        永不抛异常：查不到时返回 ok=False 与结构化错误码。
        """
        room = self.rooms.get((room_key or "").strip())
        if room is None:
            return Resolution.failure(
                TopologyErrorCode.UNKNOWN_ROOM, f"没有「{room_key}」这个房间"
            )

        device = room.get((device_key or "").strip())
        if device is None:
            available = "、".join(room.device_keys)
            return Resolution.failure(
                TopologyErrorCode.UNKNOWN_DEVICE,
                f"「{room.name}」里没有「{device_key}」这个设备"
                + (f"（这里有：{available}）" if available else ""),
            )

        return Resolution.success(device)

    # ── 模糊查找（给规则路由用）───────────────────────────────
    def find_room(self, text: str) -> str | None:
        """从一句中文里找出房间 key。先精确匹配，再退回包含匹配。

        例："打开客厅灯" → "living_room"
        """
        return _match(
            text,
            [(key, (room.name, *room.aliases), key) for key, room in self.rooms.items()],
        )

    def find_device(self, room_key: str, text: str) -> str | None:
        """在指定房间里，从一句中文里找出设备 key。"""
        room = self.rooms.get((room_key or "").strip())
        if room is None:
            return None
        return _match(
            text,
            [
                (key, (device.name, *device.aliases), key)
                for key, device in room.devices.items()
            ],
        )

    # ── 遍历 ──────────────────────────────────────────────────
    def all_devices(self) -> list[Device]:
        return [device for room in self.rooms.values() for device in room.devices.values()]

    def all_entity_ids(self) -> list[str]:
        return [device.entity_id for device in self.all_devices()]

    def devices_of(self, room_key: str) -> tuple[Device, ...]:
        room = self.rooms.get(room_key)
        return tuple(room.devices.values()) if room else ()


def _match(
    text: str,
    candidates: list[tuple[str, tuple[str, ...], str]],
) -> str | None:
    """两轮匹配：先完全相等（忽略大小写），再子串包含。

    candidates: [(精确键, 别名元组, 命中时返回值)]
    """
    raw = (text or "").strip()
    if not raw:
        return None
    lowered = raw.lower()

    for key, aliases, result in candidates:
        if lowered == key.lower() or any(lowered == a.lower() for a in aliases if a):
            return result

    for _key, aliases, result in candidates:
        for alias in aliases:
            if alias and alias in raw:
                return result
    return None


# ── 加载与校验 ────────────────────────────────────────────────
def load_topology(path: Path | str | None = None) -> Topology:
    """从 YAML 加载拓扑。文件缺失或格式非法时抛 TopologyError。"""
    target = Path(path) if path is not None else DEFAULT_TOPOLOGY_PATH
    if not target.exists():
        raise TopologyError(f"拓扑文件不存在：{target}")

    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TopologyError(f"拓扑文件不是合法 YAML：{target} —— {exc}") from exc

    return parse_topology(raw or {}, source=str(target))


def parse_topology(raw: Mapping[str, Any], *, source: str = "<memory>") -> Topology:
    """解析并**严格校验**拓扑数据。任何不合法之处都抛 TopologyError。

    校验项：结构完整、entity_id 形态合法、domain 与 entity_id 域名一致、
    capability 取值合法、entity_id 全局不重复。
    """
    if not isinstance(raw, Mapping):
        raise TopologyError(f"拓扑根节点必须是键值映射，实际是 {type(raw).__name__}")

    rooms_raw = raw.get("rooms")
    if not isinstance(rooms_raw, Mapping) or not rooms_raw:
        raise TopologyError("拓扑缺少 rooms，或 rooms 为空")

    version = raw.get("version", 1)
    if not isinstance(version, int):
        raise TopologyError("拓扑的 version 必须是整数")

    rooms: dict[str, Room] = {}
    seen_entity_ids: dict[str, str] = {}

    for room_key, room_raw in rooms_raw.items():
        room_key = str(room_key)
        if not isinstance(room_raw, Mapping):
            raise TopologyError(f"房间 {room_key} 的定义必须是键值映射")

        room_name = room_raw.get("name")
        if not isinstance(room_name, str) or not room_name.strip():
            raise TopologyError(f"房间 {room_key} 缺少 name")

        devices_raw = room_raw.get("devices")
        if not isinstance(devices_raw, Mapping) or not devices_raw:
            raise TopologyError(f"房间 {room_key} 缺少 devices，或 devices 为空")

        devices: dict[str, Device] = {}
        for device_key, device_raw in devices_raw.items():
            device_key = str(device_key)
            device = _parse_device(room_key, device_key, device_raw)

            if device.entity_id in seen_entity_ids:
                raise TopologyError(
                    f"entity_id 重复：{device.entity_id}"
                    f"（同时出现在 {seen_entity_ids[device.entity_id]} 与 {room_key}.{device_key}）"
                )
            seen_entity_ids[device.entity_id] = f"{room_key}.{device_key}"
            devices[device_key] = device

        rooms[room_key] = Room(
            key=room_key,
            name=room_name.strip(),
            aliases=_parse_str_tuple(room_raw.get("aliases"), where=f"房间 {room_key}.aliases"),
            devices=devices,
        )

    return Topology(version=version, rooms=rooms, source=source)


def _parse_device(room_key: str, device_key: str, raw: Any) -> Device:
    where = f"设备 {room_key}.{device_key}"
    if not isinstance(raw, Mapping):
        raise TopologyError(f"{where} 的定义必须是键值映射")

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise TopologyError(f"{where} 缺少 name")

    entity_id = raw.get("entity_id")
    if not isinstance(entity_id, str) or not entity_id.strip():
        raise TopologyError(f"{where} 缺少 entity_id")
    entity_id = entity_id.strip()
    if not ENTITY_ID_RE.match(entity_id):
        raise TopologyError(
            f"{where} 的 entity_id 不合法：{entity_id}"
            "（必须是「小写域名.小写对象名」，例如 light.living_room_light）"
        )

    domain = raw.get("domain")
    if not isinstance(domain, str) or not domain.strip():
        raise TopologyError(f"{where} 缺少 domain")
    domain = domain.strip()

    entity_domain = entity_id.split(".", 1)[0]
    if domain != entity_domain:
        raise TopologyError(
            f"{where} 的 domain={domain} 与 entity_id={entity_id} 的域名不一致"
        )

    capabilities = _parse_str_tuple(raw.get("capabilities"), where=f"{where}.capabilities")
    if not capabilities:
        raise TopologyError(f"{where}.capabilities 不能为空")
    unknown = [c for c in capabilities if c not in VALID_CAPABILITIES]
    if unknown:
        raise TopologyError(
            f"{where} 含未知 capability：{unknown}；合法值：{sorted(VALID_CAPABILITIES)}"
        )

    aliases = _parse_str_tuple(raw.get("aliases"), where=f"{where}.aliases")

    return Device(
        key=device_key,
        name=name.strip(),
        entity_id=entity_id,
        domain=domain,
        capabilities=capabilities,
        aliases=aliases,
    )


def _parse_str_tuple(value: Any, *, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise TopologyError(f"{where} 必须是列表")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise TopologyError(f"{where} 含非法项 {item!r}（必须是非空字符串）")
        items.append(item.strip())
    return tuple(items)
