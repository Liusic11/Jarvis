"""Home Assistant 客户端 —— 全系统唯一的 HA 出口。

架构约束：除本模块外，任何地方都不得直接向 HA 发起 HTTP 请求。
Agent 与 Tools 只能通过这里暴露的结构化方法操作家庭设备。
虚拟设备将来换成真实设备时，只需要保证 HA 侧实体不变，
本模块的上层调用方一行都不用改。

能力
- ``health_check``：连通性与令牌探测（Phase 1）
- ``get_state`` / ``get_states``：读取实体状态（Phase 3）
- ``call_service``：调用 HA 服务，例如 ``light.turn_on``（Phase 3）

设计要点
- 所有外部调用都有超时，绝不无限等待
- **对外方法永不抛异常**：一律返回结构化结果（HAResult / HomeHealth），
  因为 HA 挂掉、令牌失效都是可预期的运行状态，上层要据此回复用户
- 内部用 ``ha/errors.py`` 的领域异常承载失败，在模块边界统一翻译成错误码
- **重试区分读写**：读操作可重试，写操作一律不重试（见 ``call_service`` 注释）
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any

import httpx

from ..logging import get_logger
from .errors import HomeAssistantAuthError, HomeAssistantError, HomeAssistantUnavailable
from .models import HAErrorCode, EntityState, HAResult, HomeHealth

__all__ = ["HomeAssistantClient", "HomeHealth"]

logger = get_logger(__name__)


class HomeAssistantClient:
    """封装与 Home Assistant 的全部通信。"""

    def __init__(
        self,
        base_url: str,
        token: str = "",
        timeout: float = 5.0,
        *,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 2,
        retry_backoff: float = 0.2,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None
        self._max_retries = max(0, max_retries)
        self._retry_backoff = retry_backoff

    # ── 内部 ────────────────────────────────────────────────
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        attempts: int = 1,
        retry_on_server_error: bool = False,
    ) -> httpx.Response:
        """发起一次 HA 请求，失败时抛 ``ha.errors`` 里的领域异常。

        本方法**故意不吞异常**："重试几次、什么算失败"属于传输策略，
        不该污染业务方法；由各公开方法在边界上翻译成结构化结果。

        attempts: 总共尝试几次（1 表示不重试）
        retry_on_server_error: 遇到 5xx 是否重试（读操作 yes，写操作 no）
        """
        client = await self._get_client()
        url = f"{self._base_url}{path}"
        last_error: Exception | None = None
        last_status: int | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = await client.request(
                    method, url, json=payload, headers=self._auth_headers()
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("HA 请求超时（第 %s/%s 次）：%s %s", attempt, attempts, method, path)
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "HA 连接失败（第 %s/%s 次）：%s %s —— %s",
                    attempt,
                    attempts,
                    method,
                    path,
                    type(exc).__name__,
                )
            else:
                status = response.status_code
                # 401/403 是鉴权问题，重试毫无意义，立刻抛出
                if status in (401, 403):
                    raise HomeAssistantAuthError(f"令牌无效或权限不足（HTTP {status}）")
                if status >= 500:
                    last_status = status
                    if retry_on_server_error and attempt < attempts:
                        logger.warning(
                            "HA 返回 %s（第 %s/%s 次），准备重试", status, attempt, attempts
                        )
                    else:
                        raise HomeAssistantUnavailable(f"Home Assistant 返回 HTTP {status}")
                else:
                    return response  # 2xx / 3xx / 404 / 400 都交给调用方判断

            if attempt < attempts:
                await asyncio.sleep(self._retry_backoff * attempt)

        if last_status is not None:
            # 重试全部用尽仍然是 5xx
            raise HomeAssistantUnavailable(
                f"Home Assistant 返回 HTTP {last_status}（已重试 {attempts} 次）"
            )
        if isinstance(last_error, httpx.TimeoutException):
            raise HomeAssistantUnavailable(f"请求超时（>{self._timeout}s）")
        raise HomeAssistantUnavailable(
            f"无法连接 Home Assistant：{type(last_error).__name__ if last_error else '未知原因'}"
        )

    # ── 对外：连通性 ────────────────────────────────────────
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

    # ── 对外：读状态 ────────────────────────────────────────
    async def get_state(self, entity_id: str) -> HAResult[EntityState]:
        """读取单个实体状态。实体不存在时返回 NOT_FOUND，不抛异常。"""
        entity_id = (entity_id or "").strip()
        if not entity_id:
            return HAResult.failure(HAErrorCode.INVALID_REQUEST, "entity_id 不能为空")
        if not self._token:
            return HAResult.failure(HAErrorCode.NOT_CONFIGURED, "未配置 JARVIS_HA_TOKEN")

        try:
            response = await self._request(
                "GET",
                f"/api/states/{entity_id}",
                attempts=self._max_retries + 1,
                retry_on_server_error=True,
            )
        except HomeAssistantAuthError as exc:
            return HAResult.failure(HAErrorCode.UNAUTHORIZED, str(exc))
        except HomeAssistantUnavailable as exc:
            return HAResult.failure(HAErrorCode.UNAVAILABLE, str(exc))
        except HomeAssistantError as exc:
            return HAResult.failure(HAErrorCode.UNKNOWN, str(exc))

        if response.status_code == 404:
            return HAResult.failure(HAErrorCode.NOT_FOUND, f"实体不存在：{entity_id}")
        if not response.is_success:
            return HAResult.failure(
                HAErrorCode.SERVER_ERROR, f"Home Assistant 返回 HTTP {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError:
            return HAResult.failure(HAErrorCode.BAD_RESPONSE, "Home Assistant 返回的不是合法 JSON")
        if not isinstance(payload, Mapping):
            return HAResult.failure(HAErrorCode.BAD_RESPONSE, "Home Assistant 返回的结构不是对象")

        return HAResult.success(EntityState.from_payload(payload))

    async def get_states(self) -> HAResult[list[EntityState]]:
        """读取全部实体状态。"""
        if not self._token:
            return HAResult.failure(HAErrorCode.NOT_CONFIGURED, "未配置 JARVIS_HA_TOKEN")

        try:
            response = await self._request(
                "GET",
                "/api/states",
                attempts=self._max_retries + 1,
                retry_on_server_error=True,
            )
        except HomeAssistantAuthError as exc:
            return HAResult.failure(HAErrorCode.UNAUTHORIZED, str(exc))
        except HomeAssistantUnavailable as exc:
            return HAResult.failure(HAErrorCode.UNAVAILABLE, str(exc))
        except HomeAssistantError as exc:
            return HAResult.failure(HAErrorCode.UNKNOWN, str(exc))

        if not response.is_success:
            return HAResult.failure(
                HAErrorCode.SERVER_ERROR, f"Home Assistant 返回 HTTP {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError:
            return HAResult.failure(HAErrorCode.BAD_RESPONSE, "Home Assistant 返回的不是合法 JSON")
        if not isinstance(payload, list):
            return HAResult.failure(HAErrorCode.BAD_RESPONSE, "Home Assistant 返回的不是数组")

        states = [
            EntityState.from_payload(item) for item in payload if isinstance(item, Mapping)
        ]
        return HAResult.success(states)

    # ── 对外：调服务 ────────────────────────────────────────
    async def call_service(
        self,
        domain: str,
        service: str,
        data: Mapping[str, Any] | None = None,
    ) -> HAResult[Any]:
        """调用 HA 服务，例如 domain="light"、service="turn_on"。

        **写操作一律不重试**：一次调用可能已经生效（灯其实已经开了），
        只是响应丢了或超时。盲目重试会造成重复动作（比如连开两次锁）。
        读操作没有副作用，才允许重试 —— 这就是"幂等性"的考量。
        """
        domain = (domain or "").strip()
        service = (service or "").strip()
        if not domain or not service:
            return HAResult.failure(HAErrorCode.INVALID_REQUEST, "domain 与 service 都不能为空")
        if not self._token:
            return HAResult.failure(HAErrorCode.NOT_CONFIGURED, "未配置 JARVIS_HA_TOKEN")

        try:
            response = await self._request(
                "POST",
                f"/api/services/{domain}/{service}",
                payload=dict(data or {}),
                attempts=1,  # 写操作不重试
                retry_on_server_error=False,
            )
        except HomeAssistantAuthError as exc:
            return HAResult.failure(HAErrorCode.UNAUTHORIZED, str(exc))
        except HomeAssistantUnavailable as exc:
            return HAResult.failure(HAErrorCode.UNAVAILABLE, str(exc))
        except HomeAssistantError as exc:
            return HAResult.failure(HAErrorCode.UNKNOWN, str(exc))

        if response.status_code == 404:
            return HAResult.failure(HAErrorCode.NOT_FOUND, f"服务不存在：{domain}.{service}")
        if response.status_code == 400:
            detail = response.text[:200] if response.text else ""
            return HAResult.failure(
                HAErrorCode.INVALID_REQUEST,
                f"Home Assistant 拒绝了这次调用：{domain}.{service} {detail}".strip(),
            )
        if not response.is_success:
            return HAResult.failure(
                HAErrorCode.SERVER_ERROR, f"Home Assistant 返回 HTTP {response.status_code}"
            )

        try:
            return HAResult.success(response.json())
        except ValueError:
            # 有些服务调用成功但没有返回体，这依然算成功
            return HAResult.success(None)

    # ── 生命周期 ────────────────────────────────────────────
    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None
