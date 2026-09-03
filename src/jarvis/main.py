"""JARVIS 应用入口。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from . import __version__
from .api.routes import health
from .config import Settings, get_settings
from .ha.client import HomeAssistantClient
from .llm.base import LLMError
from .llm.factory import create_llm_provider
from .llm.stub_provider import StubProvider
from .logging import bind_request_id, get_logger, setup_logging

logger = get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个请求分配 request_id，并回写到响应头，便于串联日志。"""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        with bind_request_id(request_id):
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    setup_logging(settings.log_level, json_output=(settings.env == "prod"))
    settings.ensure_data_dir()

    app.state.ha_client = HomeAssistantClient(
        settings.ha_url_normalized,
        settings.ha_token,
        settings.ha_timeout_seconds,
    )

    # LLM 初始化失败不允许拖垮启动：回落到 stub，靠规则路由继续工作
    try:
        app.state.llm_provider = create_llm_provider(settings)
    except LLMError as exc:
        logger.warning("LLM provider 初始化失败，回落到 stub：%s", exc)
        app.state.llm_provider = StubProvider()

    logger.info(
        "JARVIS 启动 | version=%s env=%s ha=%s llm=%s",
        __version__,
        settings.env,
        settings.ha_url_normalized,
        app.state.llm_provider.name,
    )

    try:
        yield
    finally:
        await app.state.ha_client.aclose()
        logger.info("JARVIS 已停止")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title="JARVIS",
        version=__version__,
        description="本地优先的个人家庭 AI 助手原型",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router, prefix="/api")
    return app


# uvicorn jarvis.main:app
app = create_app()


def run() -> None:
    """命令行入口：python -m jarvis.main"""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "jarvis.main:app",
        host=settings.host,
        port=settings.port,
        reload=(settings.env == "dev"),
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
