"""Home Assistant 客户端的数据模型。

【为什么单独拆一个 models.py】
客户端对外**只返回这里的类型**，调用方（Tools / Agent）完全不需要知道
HA 返回的 JSON 长什么样。将来 HA 改字段，只改这里的 ``from_payload``，
上层一行不动 —— 这就是"防腐层"的作用。

【统一的返回约定】
所有可能失败的操作都返回 ``HAResult[T]``，而不是抛异常。
理由：HA 挂掉、令牌失效、实体不存在都是**可预期的运行状态**，
上层要据此回复用户，而不是让整个请求 500。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class HAErrorCode:
    """结构化错误码。上层据此决定如何回复用户，而不是去猜字符串。"""

    NOT_CONFIGURED = "not_configured"  # 没配令牌
    UNAVAILABLE = "unavailable"  # 连不上 / 超时
    UNAUTHORIZED = "unauthorized"  # 令牌无效或权限不足
    NOT_FOUND = "not_found"  # 实体不存在
    TIMEOUT = "timeout"  # 请求超时
    SERVER_ERROR = "server_error"  # HA 返回 5xx
    BAD_RESPONSE = "bad_response"  # 返回体不是预期格式
    INVALID_REQUEST = "invalid_request"  # 调用方传参不合法
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HomeHealth:
    """HA 连通性与令牌有效性的探测结果。"""

    available: bool
    detail: str = ""
    latency_ms: float | None = None


@dataclass(frozen=True)
class EntityState:
    """一个 HA 实体的当前状态。

    只保留 JARVIS 真正用得上的字段，不追求把 HA 的完整状态对象搬过来。
    """

    entity_id: str
    state: str
    attributes: dict[str, Any] = field(default_factory=dict)
    last_changed: str | None = None
    last_updated: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> EntityState:
        """把 HA `/api/states/<id>` 的 JSON 转成强类型对象。"""
        return cls(
            entity_id=str(payload.get("entity_id", "")),
            state=str(payload.get("state", "")),
            attributes=dict(payload.get("attributes") or {}),
            last_changed=payload.get("last_changed"),
            last_updated=payload.get("last_updated"),
        )

    @property
    def domain(self) -> str:
        return self.entity_id.split(".", 1)[0] if "." in self.entity_id else ""

    @property
    def friendly_name(self) -> str:
        """HA 里用户可见的名字；没有则退回 entity_id。"""
        return str(self.attributes.get("friendly_name") or self.entity_id)

    @property
    def is_on(self) -> bool:
        """是否处于「开 / 开合 / 运行中」。

        仅用于状态展示。门锁这类语义特殊的设备（unlocked ≠ 通电）
        应由上层按 domain 单独判断，不要依赖这个属性。
        """
        return self.state.lower() in {"on", "open", "cleaning", "home"}


@dataclass(frozen=True)
class HAResult(Generic[T]):
    """所有 HA 操作的统一返回壳。

    - 成功：``ok=True`` + ``data``
    - 失败：``ok=False`` + ``error_code``（机器可读）+ ``message``（人话）
    """

    ok: bool
    data: T | None = None
    error_code: str = ""
    message: str = ""

    @classmethod
    def success(cls, data: T) -> HAResult[T]:
        return cls(ok=True, data=data)

    @classmethod
    def failure(cls, error_code: str, message: str) -> HAResult[T]:
        return cls(ok=False, error_code=error_code, message=message)
