"""Home Assistant 客户端 —— 全系统唯一的 HA 出口。

架构约束：除本模块外，任何地方都不得直接向 HA 发起 HTTP 请求。
Agent 与 Tools 只能通过这里暴露的结构化方法操作家庭设备。
虚拟设备将来换成真实设备时，只需要保证 HA 侧实体不变，
本模块的上层调用方一行都不用改。

Phase 1 只实现健康检查；状态读取与服务调用在 Phase 3 补齐。
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from ..logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HomeHealth:
    available: bool
    detail: str = ""
    latency_ms: float | None = None


class HomeAssistantClient:
    """封装与 HA 的全部通信。

    设计要点：
    - 所有外部调用都有超时，绝不无限等待
    - health_check 遇到任何失败都返回结构化结果，绝不向上抛异常
    """

    def __init__(
        self,
        base_url: str,
        token: str = "",
        timeout: float = 5.0,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    # ── 内部 ────────────────────────────────────────────────
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    # ── 对外 ────────────────────────────────────────────────
    async def health_check(self) -> HomeHealth:
        """探测 HA 是否可用，并顺带校验令牌。

        先打 /api/（不需要鉴权）确认进程活着，
        再打 /api/config（需要鉴权）确认令牌有效。
        """
        started = time.perf_counter()

        try:
            client = await self._get_client()
            response = await client.get(f"{self._base_url}/api/")
        except httpx.TimeoutException:
            return HomeHealth(False, f"请求超时（>{self._timeout}s）")
        except httpx.HTTPError as exc:
            return HomeHealth(False, f"无法连接 Home Assistant：{type(exc).__name__}")

        latency = (time.perf_counter() - started) * 1000

        if not response.is_success:
            return HomeHealth(False, f"Home Assistant 返回 HTTP {response.status_code}", latency)

        if not self._token:
            return HomeHealth(False, "未配置 JARVIS_HA_TOKEN", latency)

        try:
            authed = await client.get(
                f"{self._base_url}/api/config", headers=self._auth_headers()
            )
        except httpx.TimeoutException:
            return HomeHealth(False, f"鉴权请求超时（>{self._timeout}s）")
        except httpx.HTTPError as exc:
            return HomeHealth(False, f"鉴权请求失败：{type(exc).__name__}")

        latency = (time.perf_counter() - started) * 1000

        if authed.status_code in (401, 403):
            return HomeHealth(
                False, "令牌无效或权限不足（检查 JARVIS_HA_TOKEN）", latency
            )
        if not authed.is_success:
            return HomeHealth(False, f"Home Assistant 返回 HTTP {authed.status_code}", latency)

        return HomeHealth(True, "ok", latency)

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None
