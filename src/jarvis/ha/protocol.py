"""HA 客户端的接口契约（Protocol）。

【为什么要有这么一个"接口"，而不是直接依赖 HomeAssistantClient 这个类】
Protocol 是 Python 的"结构化类型"：只要一个对象**长得像**这个接口
（有这些方法、签名一致），它就被认为是这个接口的实例，不需要继承。

带来的好处：
- 测试替身 ``MockHomeAssistantClient`` 只要实现同样的方法就能顶上，
  单元测试因此完全不需要真的起 HA 容器（快、稳、可离线跑）。
- 上层（Tools / Agent）只依赖这个协议，不依赖具体实现。
  将来加缓存层、换 HTTP 库、甚至换成别的智能家居中枢，
  调用方一行都不用改。

这是软件工程里"依赖倒置"最轻量、最 Pythonic 的做法。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from .models import EntityState, HAResult, HomeHealth


@runtime_checkable
class HomeAssistantProtocol(Protocol):
    """全系统操作 Home Assistant 的唯一入口契约。"""

    async def health_check(self) -> HomeHealth:
        """探测 HA 是否可用，并顺带校验令牌。任何失败都返回结果，不抛异常。"""
        ...

    async def get_state(self, entity_id: str) -> HAResult[EntityState]:
        """读取单个实体状态。"""
        ...

    async def get_states(self) -> HAResult[list[EntityState]]:
        """读取全部实体状态。"""
        ...

    async def call_service(
        self,
        domain: str,
        service: str,
        data: Mapping[str, Any] | None = None,
    ) -> HAResult[Any]:
        """调用 HA 服务，例如 domain="light", service="turn_on"。"""
        ...

    async def aclose(self) -> None:
        """释放底层连接。"""
        ...
