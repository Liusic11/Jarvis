"""Home Assistant 集成层。

- ``client`` 是**唯一的 HA 出口**（全系统只有它发 HTTP 请求）
- ``protocol`` 是它的接口契约，真实客户端与测试替身都实现它
- ``mock_client`` 是不联网的测试替身，用于单元测试
- ``models`` 是对外返回的数据结构
"""

from jarvis.ha.client import HomeAssistantClient, HomeHealth
from jarvis.ha.errors import (
    HomeAssistantAuthError,
    HomeAssistantError,
    HomeAssistantUnavailable,
)
from jarvis.ha.mock_client import MockHomeAssistantClient
from jarvis.ha.models import HAErrorCode, EntityState, HAResult
from jarvis.ha.protocol import HomeAssistantProtocol

__all__ = [
    "HAErrorCode",
    "EntityState",
    "HAResult",
    "HomeAssistantAuthError",
    "HomeAssistantClient",
    "HomeAssistantError",
    "HomeAssistantProtocol",
    "HomeAssistantUnavailable",
    "HomeHealth",
    "MockHomeAssistantClient",
]
