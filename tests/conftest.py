"""测试公共夹具。

注意：构造 Settings 时统一传 _env_file=None，
避免测试读到开发者本机的 .env 而产生环境相关的结果。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest

from jarvis.config import Settings
from jarvis.ha.client import HomeAssistantClient

HAHandler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, database_path=tmp_path / "test.db")


@pytest.fixture
def make_settings(tmp_path: Path) -> Callable[..., Settings]:
    """构造可覆盖字段的测试配置。"""

    def _make(**overrides: Any) -> Settings:
        overrides.setdefault("database_path", tmp_path / "test.db")
        return Settings(_env_file=None, **overrides)

    return _make


@pytest.fixture
def ha_client() -> Callable[..., Any]:
    """用 httpx.MockTransport 构造 HA 客户端，无需真实 HA 实例。"""

    @asynccontextmanager
    async def _factory(
        handler: HAHandler,
        token: str = "test-token",
    ) -> AsyncIterator[HomeAssistantClient]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            yield HomeAssistantClient("http://ha.test", token, 1.0, client=http)

    return _factory
