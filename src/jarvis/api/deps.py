"""FastAPI 依赖注入。

路由通过这里拿到配置、HA 客户端与 LLM provider，
不直接读写 app.state，便于测试时整体替换。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from ..config import Settings
from ..ha.client import HomeAssistantClient
from ..llm.base import LLMProvider


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_ha_client(request: Request) -> HomeAssistantClient:
    return request.app.state.ha_client  # type: ignore[no-any-return]


def get_llm_provider(request: Request) -> LLMProvider:
    return request.app.state.llm_provider  # type: ignore[no-any-return]


SettingsDep = Annotated[Settings, Depends(get_settings)]
HomeAssistantClientDep = Annotated[HomeAssistantClient, Depends(get_ha_client)]
LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]
