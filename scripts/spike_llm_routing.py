"""模型冒烟测试（一次性脚本）：小模型对着我们的工具，能选得多准。

目的：在写工具层代码之前，先量出 qwen 系列小模型的路由准确率。
    结果决定两件事：工具的命名和描述要不要改，评测门槛要不要调。

用法（在项目根目录执行，需要 Ollama 可达）：
    python scripts/spike_llm_routing.py
    python scripts/spike_llm_routing.py --models qwen2.5:7b-instruct

它做四件事：
    1. 读 evals/cases.yaml
    2. 逐句发给 Ollama 的 /api/chat（温度 0，关闭思考）
    3. 期望是开灯/关灯的用例，真的去调 HA，再读回灯的状态核对
    4. 打印每个模型的「工具名正确率」「工具名+参数」「负例未误调」「中位延迟」

门槛：至少一个模型 工具名 ≥ 90%，工具名+参数 ≥ 80%，负例 6 条至少 5 条不误调。
HA 连不上时不影响评分，只是跳过真执行那一步。跑完会把灯恢复成开跑前的状态。

原始输出写到系统临时目录的 jarvis-spike/ 下，不入库。
本脚本在 Phase 7 改造成 run_evals.py 后删除。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# 允许直接 `python scripts/spike_llm_routing.py` 运行，不依赖包是否已安装
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

import httpx  # noqa: E402
import yaml  # noqa: E402

from jarvis.config import get_settings  # noqa: E402
from jarvis.ha.client import HomeAssistantClient  # noqa: E402
from jarvis.home.topology import Topology, load_topology  # noqa: E402

CASES_PATH = PROJECT_ROOT / "evals" / "cases.yaml"

# 门槛：按 30 条正例定的初始值，冒烟后可以调
GATE_TOOL_NAME = 0.90
GATE_TOOL_AND_ARGS = 0.80
GATE_NEGATIVES = 5

DEFAULT_MODELS = ["qwen2.5:7b-instruct", "qwen3:8b"]

ROOMS_WITH_LIGHT = "房间名，可选：客厅、卧室、书房、厨房"
ROOMS_WITH_CURTAIN = "房间名，可选：客厅、卧室"
ROOMS_WITH_TEMPERATURE = "房间名，可选：客厅、卧室、书房、厨房"
ROOMS_WITH_PRESENCE = "房间名，可选：客厅、卧室、书房、厨房、门口"
ROOMS_WITH_STATE = "房间名，可选：客厅、卧室、书房、厨房、门口"


def _schema(properties: dict[str, Any] | None = None) -> dict[str, Any]:
    properties = properties or {}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
    }


def _room(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


# 手写的工具描述（中文）。Phase 4 的工具层会以这份为准落地。
# unlock_front_door 故意不在这里：高危工具不进模型可见的工具清单。
TOOLS: dict[str, dict[str, Any]] = {
    "get_home_state": {
        "description": "查询全屋所有设备的状态汇总。",
        "parameters": _schema(),
    },
    "get_room_state": {
        "description": "查询某个房间里所有设备的状态。",
        "parameters": _schema({"room": _room(ROOMS_WITH_STATE)}),
    },
    "turn_on_light": {
        "description": "打开某个房间的灯。",
        "parameters": _schema({"room": _room(ROOMS_WITH_LIGHT)}),
    },
    "turn_off_light": {
        "description": "关闭某个房间的灯。",
        "parameters": _schema({"room": _room(ROOMS_WITH_LIGHT)}),
    },
    "set_light_brightness": {
        "description": "把某个房间的灯调到指定亮度百分比。",
        "parameters": _schema(
            {
                "room": _room(ROOMS_WITH_LIGHT),
                "brightness": {
                    "type": "integer",
                    "description": "亮度百分比，1 到 100",
                    "minimum": 1,
                    "maximum": 100,
                },
            }
        ),
    },
    "turn_on_ac": {
        "description": "打开某个房间的空调（制冷）。",
        "parameters": _schema({"room": _room(ROOMS_WITH_LIGHT)}),
    },
    "set_ac": {
        "description": "把某个房间的空调设到指定温度（摄氏度）。",
        "parameters": _schema(
            {
                "room": _room(ROOMS_WITH_LIGHT),
                "temperature": {
                    "type": "number",
                    "description": "目标温度，单位摄氏度，16 到 30",
                    "minimum": 16,
                    "maximum": 30,
                },
            }
        ),
    },
    "turn_off_ac": {
        "description": "关闭某个房间的空调。",
        "parameters": _schema({"room": _room(ROOMS_WITH_LIGHT)}),
    },
    "open_curtain": {
        "description": "打开某个房间的窗帘。",
        "parameters": _schema({"room": _room(ROOMS_WITH_CURTAIN)}),
    },
    "close_curtain": {
        "description": "关闭某个房间的窗帘。",
        "parameters": _schema({"room": _room(ROOMS_WITH_CURTAIN)}),
    },
    "turn_on_tv": {
        "description": "打开客厅电视。",
        "parameters": _schema(),
    },
    "turn_off_tv": {
        "description": "关闭客厅电视。",
        "parameters": _schema(),
    },
    "lock_front_door": {
        "description": "把大门上锁。",
        "parameters": _schema(),
    },
    "get_temperature": {
        "description": "查询某个房间当前的温度。",
        "parameters": _schema({"room": _room(ROOMS_WITH_TEMPERATURE)}),
    },
    "get_presence": {
        "description": "查询某个房间当前是否有人。",
        "parameters": _schema({"room": _room(ROOMS_WITH_PRESENCE)}),
    },
    "vacuum_start": {
        "description": "让扫地机器人开始打扫。",
        "parameters": _schema(),
    },
    "vacuum_stop": {
        "description": "让扫地机器人停止打扫。",
        "parameters": _schema(),
    },
    "vacuum_return_to_dock": {
        "description": "让扫地机器人返回充电座。",
        "parameters": _schema(),
    },
}

SYSTEM_PROMPT = (
    "你是家庭助手。用户想控制设备或查询家里状态时，调用对应的工具，每次最多调用一个工具；"
    "其他情况直接简短回复，不要调用工具。"
)

LIGHT_TOOLS = ("turn_on_light", "turn_off_light")

# 连续失败这么多次就不再问这个模型了（多半是地址不通），避免白等几十个超时
MAX_CONSECUTIVE_ERRORS = 3


# ── 评测集 ────────────────────────────────────────────────
def load_cases() -> list[dict[str, Any]]:
    with CASES_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["cases"]


def is_negative(case: dict[str, Any]) -> bool:
    return case["expect"]["tool"] is None


# ── 调模型 ────────────────────────────────────────────────
def build_tool_definitions() -> list[dict[str, Any]]:
    return [
        {"type": "function", "function": {"name": name, **spec}} for name, spec in TOOLS.items()
    ]


def parse_tool_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """取出模型回复里的工具调用。arguments 一般是对象，个别版本会给字符串。"""
    message = payload.get("message") or {}
    calls: list[dict[str, Any]] = []
    for raw in message.get("tool_calls") or []:
        function = raw.get("function") or {}
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError:
                arguments = None
        calls.append(
            {
                "name": function.get("name") or "",
                "args": arguments if isinstance(arguments, dict) else {},
            }
        )
    return calls


async def ask_model(
    client: httpx.AsyncClient, base_url: str, model: str, text: str, timeout: float
) -> tuple[list[dict[str, Any]] | None, float, str]:
    """返回（工具调用列表, 耗时秒, 错误信息）。请求失败时工具调用列表为 None。"""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "tools": build_tool_definitions(),
        "stream": False,
        "think": False,
        "options": {"temperature": 0},
    }
    started = time.perf_counter()
    try:
        response = await client.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        return None, time.perf_counter() - started, f"{type(exc).__name__}: {exc}"
    except ValueError as exc:
        return None, time.perf_counter() - started, f"返回的不是合法 JSON：{exc}"
    return parse_tool_calls(data), time.perf_counter() - started, ""


# ── 评分 ──────────────────────────────────────────────────
def normalize(text: Any) -> str:
    return re.sub(r"[\s，。！？,.!?]", "", str(text))


def room_key_of(value: Any, topology: Topology) -> str | None:
    """模型写房间 key、中文名或拓扑里的任一别名，都认得出是哪个房间。"""
    wanted = normalize(value)
    for key, room in topology.rooms.items():
        if wanted in {normalize(room.name), key, *map(normalize, room.aliases)}:
            return key
    return None


def args_match(expected: dict[str, Any], actual: dict[str, Any], topology: Topology) -> bool:
    if set(actual) != set(expected):
        return False
    for key, want in expected.items():
        got = actual[key]
        if key == "room":
            if room_key_of(want, topology) != room_key_of(got, topology):
                return False
        else:
            try:
                if float(got) != float(want):
                    return False
            except (TypeError, ValueError):
                return False
    return True


def tool_name_ok(case: dict[str, Any], calls: list[dict[str, Any]]) -> bool:
    if is_negative(case):
        return not calls
    return len(calls) == 1 and calls[0]["name"] == case["expect"]["tool"]


def tool_and_args_ok(case: dict[str, Any], calls: list[dict[str, Any]], topology: Topology) -> bool:
    return tool_name_ok(case, calls) and (
        is_negative(case) or args_match(case["expect"]["args"], calls[0]["args"], topology)
    )


def format_calls(calls: list[dict[str, Any]] | None) -> str:
    if calls is None:
        return "请求失败"
    if not calls:
        return "（不调用工具）"
    return " | ".join(
        f"{call['name']}({json.dumps(call['args'], ensure_ascii=False)})" for call in calls
    )


# ── 真执行：灯 ────────────────────────────────────────────
async def read_light_states(ha: HomeAssistantClient, topology: Topology) -> dict[str, str] | None:
    """读回所有灯的当前状态。任何一盏读不到就返回 None。"""
    states: dict[str, str] = {}
    for device in topology.all_devices():
        if device.domain != "light":
            continue
        result = await ha.get_state(device.entity_id)
        if not result.ok or result.data is None:
            return None
        states[device.entity_id] = result.data.state
    return states


async def restore_lights(ha: HomeAssistantClient, initial: dict[str, str]) -> list[str]:
    """把灯恢复成开跑前的状态，返回恢复失败的实体。"""
    failed: list[str] = []
    for entity_id, state in initial.items():
        service = "turn_on" if state == "on" else "turn_off"
        result = await ha.call_service("light", service, {"entity_id": entity_id})
        if not result.ok:
            failed.append(entity_id)
    return failed


async def execute_light(ha: HomeAssistantClient, call: dict[str, Any], topology: Topology) -> str:
    """按模型的调用真的去开灯/关灯，再读回状态核对。"""
    room_key = room_key_of(call["args"].get("room", ""), topology)
    if room_key is None:
        return f"✗ 模型给的房间识别不了：{call['args'].get('room')!r}"

    resolution = topology.resolve(room_key, "light")
    if not resolution.ok or resolution.entity_id is None:
        return f"✗ 拓扑里查不到这盏灯：{resolution.message}"

    entity_id = resolution.entity_id
    service = "turn_on" if call["name"] == "turn_on_light" else "turn_off"
    result = await ha.call_service("light", service, {"entity_id": entity_id})
    if not result.ok:
        return f"✗ HA 调用失败 [{result.error_code}] {result.message}"

    await asyncio.sleep(0.5)
    state = await ha.get_state(entity_id)
    if not state.ok or state.data is None:
        return f"✗ 读不回灯的状态 [{state.error_code}] {state.message}"

    expected = "on" if service == "turn_on" else "off"
    mark = "✓" if state.data.state == expected else "✗"
    return (
        f"{mark} 真执行 {entity_id} -> {service}，"
        f"读回 state={state.data.state}（期望 {expected}）"
    )


# ── 跑一个模型 ────────────────────────────────────────────
async def run_model(
    client: httpx.AsyncClient,
    model: str,
    cases: list[dict[str, Any]],
    settings: Any,
    ha: HomeAssistantClient | None,
    topology: Topology,
) -> dict[str, Any]:
    print(f"\n===== {model} =====")
    stats: dict[str, Any] = {
        "model": model,
        "name_ok": 0,
        "args_ok": 0,
        "negative_ok": 0,
        "latencies": [],
        "errors": [],
        "failures": [],
        "aborted": "",
    }
    consecutive_errors = 0

    for index, case in enumerate(cases, start=1):
        calls, latency, error = await ask_model(
            client, settings.ollama_url, model, case["text"], settings.llm_timeout_seconds
        )
        if calls is None:
            consecutive_errors += 1
            stats["errors"].append(f"{case['id']}：{error}")
            print(f"  [{index}/{len(cases)}] ✗ {case['id']} 请求失败（{latency:.1f}s）：{error}")
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                stats["aborted"] = f"连续 {consecutive_errors} 次请求失败，已中止"
                print(f"  ✗ {stats['aborted']}。排查 JARVIS_OLLAMA_URL、OLLAMA_HOST 和防火墙。")
                break
            continue
        consecutive_errors = 0
        stats["latencies"].append(latency)

        name_ok = tool_name_ok(case, calls)
        args_ok = tool_and_args_ok(case, calls, topology)
        if is_negative(case):
            if args_ok:
                stats["negative_ok"] += 1
        elif name_ok:
            stats["name_ok"] += 1
            if args_ok:
                stats["args_ok"] += 1

        mark = "✓" if args_ok else "✗"
        progress = f"[{index}/{len(cases)}]"
        print(f"  {progress} {mark} {case['id']}  {format_calls(calls)}  {latency:.1f}s")
        if not args_ok:
            stats["failures"].append(
                {
                    "id": case["id"],
                    "text": case["text"],
                    "expect": case["expect"],
                    "got": calls,
                }
            )
            print(
                f"        期望：{case['expect']['tool']}"
                f"({json.dumps(case['expect']['args'], ensure_ascii=False)})"
            )

        # 真执行：只要模型调的是开灯/关灯（不管选没选对），都真的去动一下 HA
        if ha is not None and calls and calls[0]["name"] in LIGHT_TOOLS:
            print(f"        {await execute_light(ha, calls[0], topology)}")

    return stats


# ── 汇总 ──────────────────────────────────────────────────
def passes_gate(stats: dict[str, Any], positive_total: int) -> bool:
    if positive_total == 0:
        return False
    name_rate = stats["name_ok"] / positive_total
    args_rate = stats["args_ok"] / positive_total
    return (
        not stats["aborted"]
        and name_rate >= GATE_TOOL_NAME
        and args_rate >= GATE_TOOL_AND_ARGS
        and stats["negative_ok"] >= GATE_NEGATIVES
    )


def print_summary(
    results: list[dict[str, Any]], cases: list[dict[str, Any]], raw_dir: Path
) -> None:
    positive_total = sum(1 for case in cases if not is_negative(case))
    negative_total = len(cases) - positive_total

    print("\n================ 汇总 ================")
    print(f"{'模型':<20}{'工具名正确率':<16}{'工具名+参数':<16}{'负例未误调':<12}{'中位延迟':<10}门槛")
    for stats in results:
        median = f"{statistics.median(stats['latencies']):.1f}s" if stats["latencies"] else "-"
        verdict = "通过" if passes_gate(stats, positive_total) else "未通过"
        name_cell = f"{stats['name_ok']}/{positive_total}"
        args_cell = f"{stats['args_ok']}/{positive_total}"
        negative_cell = f"{stats['negative_ok']}/{negative_total}"
        print(
            f"{stats['model']:<20}{name_cell:<16}{args_cell:<14}"
            f"{negative_cell:<12}{median:<10}{verdict}"
        )

    print(
        f"\n门槛：工具名 ≥ {GATE_TOOL_NAME:.0%}，工具名+参数 ≥ {GATE_TOOL_AND_ARGS:.0%}，"
        f"负例至少 {GATE_NEGATIVES} 条不误调。"
    )
    overall = "✓ 至少一个模型达标，可以进入 Phase 4" if any(
        passes_gate(stats, positive_total) for stats in results
    ) else "✗ 没有模型达标：先改工具描述和命名（最便宜），最多两轮，再看要不要合并工具或换模型"
    print(overall)

    for stats in results:
        if not stats["failures"]:
            continue
        print(f"\n{stats['model']} 的错题：")
        for item in stats["failures"]:
            print(f"  - {item['text']}")
            print(
                f"    期望 {item['expect']['tool']}"
                f"({json.dumps(item['expect']['args'], ensure_ascii=False)})"
            )
            print(f"    实际 {format_calls(item['got'])}")
        if stats["errors"]:
            print(f"  另有 {len(stats['errors'])} 条请求失败：")
            for line in stats["errors"]:
                print(f"    - {line}")

    print(f"\n原始输出：{raw_dir}")


def safe_name(model: str) -> str:
    """模型名里的冒号在 Windows 上不能当文件名。"""
    return re.sub(r"[^A-Za-z0-9._-]", "_", model)


# ── 入口 ──────────────────────────────────────────────────
async def main() -> int:
    parser = argparse.ArgumentParser(description="模型路由冒烟测试")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS, help="要测的模型")
    args = parser.parse_args()

    settings = get_settings()
    cases = load_cases()
    topology = load_topology()
    positive_total = sum(1 for case in cases if not is_negative(case))
    print(f"Ollama 地址：{settings.ollama_url}")
    print(f"用例：{len(cases)} 条（正例 {positive_total}，负例 {len(cases) - positive_total}），"
          f"给模型看的工具 {len(TOOLS)} 个")
    print(f"HA 地址：{settings.ha_url_normalized}")

    ha = HomeAssistantClient(
        settings.ha_url_normalized, settings.ha_token, settings.ha_timeout_seconds
    )
    initial_lights = await read_light_states(ha, topology)
    if initial_lights is None:
        print("⚠ HA 连不上或读不到灯的状态：跳过真执行，只评模型选得对不对")
        await ha.aclose()

    try:
        async with httpx.AsyncClient() as client:
            # HA 不可用时传 None，跳过真执行
            runner = ha if initial_lights is not None else None
            results = [
                await run_model(client, model, cases, settings, runner, topology)
                for model in args.models
            ]
    finally:
        if initial_lights is not None:
            failed = await restore_lights(ha, initial_lights)
            await ha.aclose()
            if failed:
                print(f"\n⚠ 有 {len(failed)} 盏灯没恢复成开跑前的状态：{', '.join(failed)}")
            else:
                print("\n灯已恢复成开跑前的状态")

    raw_dir = Path(tempfile.gettempdir()) / "jarvis-spike"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for stats in results:
        path = raw_dir / f"{safe_name(stats['model'])}.json"
        path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    print_summary(results, cases, raw_dir)
    return 0 if any(passes_gate(stats, positive_total) for stats in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
