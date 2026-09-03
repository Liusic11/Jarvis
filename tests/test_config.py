"""配置加载的测试。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from jarvis.config import PROJECT_ROOT, Settings


def test_defaults_are_environment_independent(settings: Settings) -> None:
    """默认值必须与具体机器无关。"""
    assert settings.env == "dev"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.ha_url == "http://localhost:8123"
    assert settings.ha_token == ""
    assert settings.llm_provider == "stub"
    assert settings.confirm_high_risk is False


def test_env_prefix_is_applied(
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """所有变量都带 JARVIS_ 前缀，避免与系统环境变量冲突。"""
    monkeypatch.setenv("JARVIS_HA_URL", "http://ha.example:8123")
    monkeypatch.setenv("JARVIS_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("JARVIS_PORT", "9001")

    s = make_settings()

    assert s.ha_url == "http://ha.example:8123"
    assert s.llm_provider == "ollama"
    assert s.port == 9001


def test_relative_database_path_resolves_against_project_root(
    make_settings: Callable[..., Settings],
) -> None:
    """相对路径以项目根目录为基准，不依赖启动时的当前工作目录。"""
    s = make_settings(database_path=Path("data/jarvis.db"))

    assert s.database_path.is_absolute()
    assert s.database_path == (PROJECT_ROOT / "data" / "jarvis.db")


def test_ha_url_trailing_slash_is_normalized(
    make_settings: Callable[..., Settings],
) -> None:
    s = make_settings(ha_url="http://localhost:8123/")
    assert s.ha_url_normalized == "http://localhost:8123"


def test_invalid_port_is_rejected(make_settings: Callable[..., Settings]) -> None:
    with pytest.raises(ValidationError):
        make_settings(port=99999)


def test_settings_are_frozen(settings: Settings) -> None:
    """配置在启动后不应被随意改写。"""
    with pytest.raises(ValidationError):
        settings.ha_url = "http://changed"  # type: ignore[misc]


def test_ensure_data_dir_creates_parent(
    make_settings: Callable[..., Settings],
    tmp_path: Path,
) -> None:
    s = make_settings(database_path=tmp_path / "nested" / "dir" / "jarvis.db")
    s.ensure_data_dir()
    assert (tmp_path / "nested" / "dir").is_dir()
