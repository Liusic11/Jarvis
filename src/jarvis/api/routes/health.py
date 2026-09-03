"""健康检查。

外部服务不可用时必须照常返回结构化结果，绝不抛异常 —— 这是
「任何外部服务故障都不能让整个应用崩溃」的第一道验证点。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ... import __version__
from ..deps import HomeAssistantClientDep, LLMProviderDep, SettingsDep

router = APIRouter(tags=["health"])


class ServiceStatus(BaseModel):
    status: str
    detail: str = ""
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    status: str
    env: str
    version: str
    services: dict[str, ServiceStatus]


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: SettingsDep,
    ha: HomeAssistantClientDep,
    llm: LLMProviderDep,
) -> HealthResponse:
    ha_health = await ha.health_check()
    llm_health = await llm.health_check()

    return HealthResponse(
        # HA 不可用意味着没法控制设备，整体算降级；LLM 不可用可由规则路由接管
        status="ok" if ha_health.available else "degraded",
        env=settings.env,
        version=__version__,
        services={
            "jarvis": ServiceStatus(status="online", detail="running"),
            "home_assistant": ServiceStatus(
                status="connected" if ha_health.available else "disconnected",
                detail=ha_health.detail,
                latency_ms=ha_health.latency_ms,
            ),
            "llm": ServiceStatus(
                status="connected" if llm_health.available else "disconnected",
                detail=llm_health.detail,
            ),
        },
    )
