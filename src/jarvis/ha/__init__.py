"""Home Assistant 集成层。

client 是唯一的 HA 出口。详见 client.py 顶部说明。
"""

from jarvis.ha.client import HomeAssistantClient, HomeHealth
from jarvis.ha.errors import (
    HomeAssistantAuthError,
    HomeAssistantError,
    HomeAssistantUnavailable,
)

__all__ = [
    "HomeAssistantAuthError",
    "HomeAssistantClient",
    "HomeAssistantError",
    "HomeAssistantUnavailable",
    "HomeHealth",
]
