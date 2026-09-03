"""Home Assistant 错误类型。

客户端把底层 HTTP 异常统一映射成这里的领域异常或结构化结果，
上层（Tool / Agent）只处理这些类型。
"""


class HomeAssistantError(Exception):
    """HA 相关错误的基类。"""


class HomeAssistantUnavailable(HomeAssistantError):
    """连不上 HA：超时、连接被拒、DNS 失败等。"""


class HomeAssistantAuthError(HomeAssistantError):
    """令牌无效或权限不足。"""
