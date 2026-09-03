"""校验拓扑里声明的每一个 entity_id，都真实存在于 Home Assistant。

用法（在项目根目录执行）：
    python scripts/validate_topology.py

它会读 .env 里的 JARVIS_HA_TOKEN，连到 HA 拉一次全量状态，再逐个核对。

这是 Phase 3 的验收项之一：
    「拓扑 YAML 中引用的每个 entity_id 都能在真实 HA 中存在」

为什么值得单独做个脚本而不是写进单元测试：
单元测试必须能在**没有 HA 容器**的环境下跑（离线、秒级）；
这个校验恰恰需要真实 HA，所以做成可手动执行的脚本。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 允许直接 `python scripts/validate_topology.py` 运行，不依赖包是否已安装
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jarvis.config import get_settings  # noqa: E402
from jarvis.ha.client import HomeAssistantClient  # noqa: E402
from jarvis.home.topology import load_topology  # noqa: E402


async def main() -> int:
    settings = get_settings()
    if not settings.ha_token:
        print("✗ 未配置 JARVIS_HA_TOKEN —— 请先在 .env 里填入 HA 长期令牌")
        return 1

    topology = load_topology()
    print(f"拓扑文件：{topology.source}")
    print(f"HA 地址：{settings.ha_url_normalized}")
    print(f"房间/区域：{len(topology.rooms)} 个，设备：{len(topology.all_entity_ids())} 个")
    print()

    client = HomeAssistantClient(
        settings.ha_url_normalized,
        settings.ha_token,
        settings.ha_timeout_seconds,
    )
    try:
        result = await client.get_states()
    finally:
        await client.aclose()

    if not result.ok:
        print(f"✗ 读取 HA 状态失败：[{result.error_code}] {result.message}")
        print("  排查：HA 容器起来了吗？令牌过期了吗？")
        return 1

    states = result.data or []
    existing = {state.entity_id for state in states}

    missing: list[str] = []
    for room_key, room in topology.rooms.items():
        for device_key, device in room.devices.items():
            found = device.entity_id in existing
            print(f"  {'✓' if found else '✗'} {room.name} / {device.name:<10} {device.entity_id}")
            if not found:
                missing.append(f"{room_key}.{device_key} -> {device.entity_id}")

    print()
    if missing:
        print(f"✗ 有 {len(missing)} 个 entity_id 在 HA 中不存在：")
        for item in missing:
            print(f"    - {item}")
        return 1

    print(f"✓ 全部 {len(topology.all_entity_ids())} 个 entity_id 都在 HA 中存在")
    print(f"  （HA 当前共有 {len(existing)} 个实体，含 HA 自带的系统实体）")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
