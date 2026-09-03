"""测试替身：与真实客户端实现同一 Protocol，但不发起任何网络请求。

【为什么需要它】
如果单元测试依赖真实 HA 容器，测试就会变慢、变脆，而且必须先起 Docker。
用测试替身后，测试退化为纯内存操作：毫秒级、可离线、结果完全确定。

【它模拟到什么程度】
不是简单地"调用就返回成功"，而是**真的改变内存里的实体状态**：
灯被 turn_on 之后，再去 get_state 拿到的就是 "on"。
这样上层工具的逻辑才能被真正验证，而不是只验证"没抛异常"。

【刻意不模拟什么】
网络抖动、超时、鉴权失败等异常路径 —— 那些用 httpx.MockTransport
在 tests/test_ha_client.py 里覆盖更直接，不需要在替身里造开关。
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Any

from .models import HAErrorCode, EntityState, HAResult, HomeHealth

__all__ = ["MockHomeAssistantClient", "RecordedCall"]

# 各 domain 的 service → 目标状态。查不到的服务只记录、不改状态（仍算成功）。
_SERVICE_STATE: dict[str, dict[str, str]] = {
    "light": {"turn_on": "on", "turn_off": "off"},
    "switch": {"turn_on": "on", "turn_off": "off"},
    "input_boolean": {"turn_on": "on", "turn_off": "off"},
    "cover": {"open_cover": "open", "close_cover": "closed", "stop_cover": "open"},
    "lock": {"lock": "locked", "unlock": "unlocked"},
    # generic_thermostat 在 ac_mode 下，运行时状态是 cool，关机是 off
    "climate": {"turn_on": "cool", "turn_off": "off", "set_hvac_mode": "cool"},
    "vacuum": {
        "start": "cleaning",
        "stop": "idle",
        "pause": "paused",
        "return_to_base": "docked",
    },
}


@dataclass(frozen=True)
class RecordedCall:
    """一次被记录的服务调用，便于测试断言"到底发了什么"。"""

    domain: str
    service: str
    data: dict[str, Any] = field(default_factory=dict)


class MockHomeAssistantClient:
    """进程内的假 HA。接口与 ``HomeAssistantClient`` 完全一致。"""

    def __init__(
        self,
        states: Mapping[str, str] | None = None,
        *,
        available: bool = True,
        fail_services: Collection[str] = (),
        token_configured: bool = True,
    ) -> None:
        """
        states: 初始状态，形如 {"light.living_room_light": "off"}
        available: False 时所有调用都返回 UNAVAILABLE，用来测降级路径
        fail_services: 形如 {"light.turn_on"}，命中就返回 SERVER_ERROR
        token_configured: False 时所有调用返回 NOT_CONFIGURED
        """
        self._states: dict[str, EntityState] = {
            entity_id: EntityState(entity_id=entity_id, state=state)
            for entity_id, state in (states or {}).items()
        }
        self._available = available
        self._fail_services = set(fail_services)
        self._token_configured = token_configured
        self.calls: list[RecordedCall] = []

    # ── 测试辅助（真实客户端没有这些方法）────────────────────
    def set_state(self, entity_id: str, state: str, **attributes: Any) -> None:
        """直接塞一个状态，用于准备测试现场。"""
        self._states[entity_id] = EntityState(
            entity_id=entity_id, state=state, attributes=dict(attributes)
        )

    def state_of(self, entity_id: str) -> str | None:
        return self._states[entity_id].state if entity_id in self._states else None

    def clear_calls(self) -> None:
        self.calls.clear()

    # ── HomeAssistantProtocol 实现 ───────────────────────────
    async def health_check(self) -> HomeHealth:
        if not self._token_configured:
            return HomeHealth(False, "未配置 JARVIS_HA_TOKEN", 0.0)
        if not self._available:
            return HomeHealth(False, "模拟的 Home Assistant 不可用", 0.0)
        return HomeHealth(True, "ok", 0.0)

    async def get_state(self, entity_id: str) -> HAResult[EntityState]:
        guard = self._guard()
        if guard is not None:
            return guard
        entity_id = (entity_id or "").strip()
        if not entity_id:
            return HAResult.failure(HAErrorCode.INVALID_REQUEST, "entity_id 不能为空")
        state = self._states.get(entity_id)
        if state is None:
            return HAResult.failure(HAErrorCode.NOT_FOUND, f"实体不存在：{entity_id}")
        return HAResult.success(state)

    async def get_states(self) -> HAResult[list[EntityState]]:
        guard = self._guard()
        if guard is not None:
            return guard
        return HAResult.success(list(self._states.values()))

    async def call_service(
        self,
        domain: str,
        service: str,
        data: Mapping[str, Any] | None = None,
    ) -> HAResult[Any]:
        guard = self._guard()
        if guard is not None:
            return guard

        payload = dict(data or {})
        domain = (domain or "").strip()
        service = (service or "").strip()
        if not domain or not service:
            return HAResult.failure(HAErrorCode.INVALID_REQUEST, "domain 与 service 都不能为空")

        self.calls.append(RecordedCall(domain=domain, service=service, data=payload))

        if f"{domain}.{service}" in self._fail_services:
            return HAResult.failure(
                HAErrorCode.SERVER_ERROR, f"模拟失败的服务：{domain}.{service}"
            )

        changed = self._apply(domain, service, payload)
        # 与真实 HA 一致：返回受影响实体的状态数组（JSON 形态）
        return HAResult.success([_as_payload(state) for state in changed])

    async def aclose(self) -> None:
        return None

    # ── 内部 ────────────────────────────────────────────────
    def _guard(self) -> HAResult[Any] | None:
        """统一的前置检查。返回 None 表示可以继续。"""
        if not self._token_configured:
            return HAResult.failure(HAErrorCode.NOT_CONFIGURED, "未配置 JARVIS_HA_TOKEN")
        if not self._available:
            return HAResult.failure(HAErrorCode.UNAVAILABLE, "Home Assistant 不可用")
        return None

    def _apply(self, domain: str, service: str, payload: dict[str, Any]) -> list[EntityState]:
        """把服务调用落到内存状态上，返回受影响的实体。

        未收录的服务（比如某些自定义脚本）只记录调用、不改状态 ——
        这样上层不会因为我们没模拟就误判成失败。
        """
        entity_ids = _target_entity_ids(payload)
        if not entity_ids:
            return []

        target_state = _SERVICE_STATE.get(domain, {}).get(service)
        changed: list[EntityState] = []

        for entity_id in entity_ids:
            current = self._states.get(entity_id)
            if current is None:
                # 状态里没有这个实体也要放行：真实 HA 对未知实体只是无副作用
                continue
            attributes = dict(current.attributes)

            if service == "set_temperature" and "temperature" in payload:
                attributes["temperature"] = payload["temperature"]
                new_state = current.state if current.state != "off" else "cool"
            elif service == "set_value" and "value" in payload:
                new_state = str(payload["value"])
            elif target_state is not None:
                new_state = target_state
            else:
                continue

            updated = EntityState(
                entity_id=entity_id,
                state=new_state,
                attributes=attributes,
                last_changed=current.last_changed,
                last_updated=current.last_updated,
            )
            self._states[entity_id] = updated
            changed.append(updated)

        return changed


def _target_entity_ids(payload: Mapping[str, Any]) -> list[str]:
    """HA 的 target 可以是单个 entity_id 字符串，也可以是列表。"""
    raw = payload.get("entity_id")
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw else []
    if isinstance(raw, (list, tuple)):
        return [str(item) for item in raw if item]
    return []


def _as_payload(state: EntityState) -> dict[str, Any]:
    """还原成 HA REST 返回的样子，保证替身与真实的返回结构一致。"""
    payload: dict[str, Any] = {
        "entity_id": state.entity_id,
        "state": state.state,
        "attributes": dict(state.attributes),
    }
    if state.last_changed:
        payload["last_changed"] = state.last_changed
    if state.last_updated:
        payload["last_updated"] = state.last_updated
    return payload
