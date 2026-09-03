"""健康检查接口的测试。

这里用假的客户端替换掉真实实现，专门验证「外部服务挂了也不能崩」。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from jarvis.config import Settings
from jarvis.ha.client import HomeHealth
from jarvis.llm.base import AssistantMessage, LLMProvider, Message, ProviderHealth, ToolSpec
from jarvis.main import create_app


class FakeHomeAssistant:
    def __init__(self, health: HomeHealth) -> None:
        self._health = health

    async def health_check(self) -> HomeHealth:
        return self._health

    async def aclose(self) -> None:
        return None


class FakeLLM:
    name = "fake"

    def __init__(self, health: ProviderHealth) -> None:
        self._health = health

    async def chat(
        self, messages: list[Message], tools: list[ToolSpec] | None = None
    ) -> AssistantMessage:
        raise AssertionError("健康检查不应触发模型调用")

    async def health_check(self) -> ProviderHealth:
        return self._health


def build_client(
    settings: Settings,
    ha_health: HomeHealth,
    llm_health: ProviderHealth,
) -> TestClient:
    """不触发 lifespan（否则会去连真实 HA），直接注入假的实现。"""
    app = create_app(settings)
    app.state.ha_client = FakeHomeAssistant(ha_health)
    app.state.llm_provider = FakeLLM(llm_health)
    assert isinstance(app.state.llm_provider, LLMProvider)
    return TestClient(app)


def test_health_reports_connected_services(settings: Settings) -> None:
    client = build_client(
        settings,
        HomeHealth(available=True, detail="ok", latency_ms=1.5),
        ProviderHealth(available=True, detail="ollama ready"),
    )

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["services"]["jarvis"]["status"] == "online"
    assert body["services"]["home_assistant"]["status"] == "connected"
    assert body["services"]["llm"]["status"] == "connected"


def test_health_degrades_when_home_assistant_is_down(settings: Settings) -> None:
    """HA 不可用时接口照常返回 200，只是把状态标成降级。"""
    client = build_client(
        settings,
        HomeHealth(available=False, detail="无法连接 Home Assistant"),
        ProviderHealth(available=True, detail="ollama ready"),
    )

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["services"]["home_assistant"]["status"] == "disconnected"
    assert "无法连接" in body["services"]["home_assistant"]["detail"]


def test_health_reports_unauthorized_home_assistant(settings: Settings) -> None:
    """令牌错误要能被明确识别，而不是笼统地报连不上。"""
    client = build_client(
        settings,
        HomeHealth(available=False, detail="令牌无效或权限不足（检查 JARVIS_HA_TOKEN）"),
        ProviderHealth(available=False, detail="stub provider：未连接任何模型"),
    )

    body = client.get("/api/health").json()

    assert body["status"] == "degraded"
    assert "令牌" in body["services"]["home_assistant"]["detail"]
    assert body["services"]["llm"]["status"] == "disconnected"


def test_health_response_carries_request_id(settings: Settings) -> None:
    client = build_client(
        settings,
        HomeHealth(available=True, detail="ok"),
        ProviderHealth(available=False),
    )

    response = client.get("/api/health", headers={"X-Request-ID": "abc123"})

    assert response.headers["X-Request-ID"] == "abc123"


def test_health_generates_request_id_when_absent(settings: Settings) -> None:
    client = build_client(
        settings,
        HomeHealth(available=True, detail="ok"),
        ProviderHealth(available=False),
    )

    response = client.get("/api/health")

    assert response.headers["X-Request-ID"]
