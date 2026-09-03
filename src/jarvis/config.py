"""应用配置。

所有配置项都来自环境变量或 .env 文件，源码中不含任何机器专属信息。
每个字段都通过 JARVIS_ 前缀读取环境变量，避免与系统里其他变量冲突。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/jarvis/config.py -> 上三级即项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env",),
        env_file_encoding="utf-8",
        env_prefix="JARVIS_",
        extra="ignore",
        frozen=True,
    )

    # ── 应用 ──────────────────────────────────────────────
    env: Literal["dev", "prod"] = "dev"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "DEBUG"

    # ── Home Assistant ───────────────────────────────────
    ha_url: str = "http://localhost:8123"
    ha_token: str = ""
    ha_timeout_seconds: float = Field(default=5.0, gt=0)

    # ── LLM ──────────────────────────────────────────────
    llm_provider: Literal["stub", "ollama"] = "stub"
    ollama_url: str = "http://localhost:11434"
    model_name: str = "qwen2.5:7b-instruct"
    llm_timeout_seconds: float = Field(default=120.0, gt=0)

    # ── 存储 ─────────────────────────────────────────────
    database_path: Path = PROJECT_ROOT / "data" / "jarvis.db"

    # ── 安全 ─────────────────────────────────────────────
    confirm_high_risk: bool = False

    @model_validator(mode="after")
    def _resolve_paths(self) -> Settings:
        # 相对路径一律以项目根目录为基准，避免依赖启动时的当前工作目录
        if not self.database_path.is_absolute():
            object.__setattr__(self, "database_path", PROJECT_ROOT / self.database_path)
        return self

    @property
    def ha_url_normalized(self) -> str:
        """去掉结尾斜杠，便于拼接路径。"""
        return self.ha_url.rstrip("/")

    def ensure_data_dir(self) -> None:
        """确保数据目录存在。"""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取配置单例。测试中用 Settings(...) 直接构造以绕过缓存。"""
    return Settings()
