# JARVIS 架构设计

本文档记录 JARVIS 的架构决策与理由。实现前先读这份文档。

---

## 1. 目标与非目标

### 目标

1. 证明「自然语言 → 本地 LLM → 工具调用 → Home Assistant → 虚拟设备」这条链路可靠
2. 虚拟设备可无感知替换为真实设备（Agent / Tool 层不重写）
3. 完全本地运行，不依赖云端 LLM
4. 单一仓库可跨机器、跨平台复现
5. 每一步都可观测、可调试

### 非目标

- 不做语音（麦克风 / 唤醒词 / Whisper / TTS）
- 不做真实硬件接入（Zigbee / Matter / 摄像头 / 真扫地机）
- 不做 RAG / 向量数据库
- 不做分布式、微服务、Kubernetes
- 不追求 UI 视觉效果

---

## 2. 系统分层

```
┌────────────────────────────────────────────┐
│  Web UI（静态资源，由 FastAPI 提供）         │
│  聊天 · 家庭状态 · 事件日志 · 系统状态        │
└───────────────────┬────────────────────────┘
                    │ HTTP / SSE
┌───────────────────▼────────────────────────┐
│  Agent                                     │
│  ├─ IntentRouter                           │
│  │   ├─ RuleStrategy   确定性规则，优先     │
│  │   └─ LLMStrategy    LLM 兜底            │
│  └─ Runner            执行循环 + trace      │
└──────┬──────────────────────────┬──────────┘
       │                          │
┌──────▼───────────┐   ┌──────────▼──────────┐
│  Tools           │   │  LLMProvider (ABC)  │
│  · JSON Schema   │   │  ├─ StubProvider    │
│  · 参数校验       │   │  └─ OllamaProvider  │
│  · 风险分级       │   └──────────┬──────────┘
│  · 结构化返回     │              │ OLLAMA_URL
└──────┬───────────┘              ▼
       │                    Ollama（本机服务）
┌──────▼───────────────────┐
│  HomeAssistantClient     │
│  ▸ 唯一的 HA 出口          │
│  ▸ 超时 / 重试 / 错误映射  │
└──────┬───────────────────┘
       │ REST / WebSocket
┌──────▼───────────────────┐
│  Home Assistant          │
│  虚拟家庭（纯 YAML 定义）  │
└──────────────────────────┘

旁路：SQLite（trace / 会话 / 事件）· home_topology.yaml（设备映射）
```

### 不可违反的约束

**LLM 永远不能直接向 Home Assistant 发任意 HTTP 请求。**
所有 HA 通信必须经由 `HomeAssistantClient`。Agent 只认识结构化工具（`turn_on_light(room="living_room")`），不认识 URL。

---

## 3. 核心设计决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 虚拟设备用 **YAML template 实体** | 纯配置、可提交、零 UI 操作、fresh clone 可复现。靠 UI 或 WebSocket API 建的实体存在 `.storage/` 里，不可复现 |
| D2 | **`home_topology.yaml` 是设备映射的唯一真相** | Agent/Tools 只认逻辑语义（`living_room` + `light`），由此文件翻译成 entity_id。换真实设备只改这一个文件 |
| D3 | 意图路由 **规则优先 + LLM 兜底** | 无 GPU 时只能用 CPU 小模型，其 tool calling 可靠性差（参数填错、幻觉房间名、该调工具却闲聊）。规则吃掉高频固定句式；顺带满足「LLM 不可用时系统仍可用」的降级要求 |
| D4 | **LLM 抽象在 Phase 1 就位**，配 `StubProvider` | 否则 Phase 2–7 完全无法端到端测试 |
| D5 | `HomeAssistantClient` 定义为 **Protocol + MockClient** | 测试不依赖 HA 容器，CI 也能跑 |
| D6 | 实现顺序 **确定性优先，LLM 最后接** | 每个阶段结束时都有一个可运行、可测试的系统，而不是长期处于「做了一半没法验证」 |
| D7 | HA 配置用 **named volume**，不用 Windows bind mount | WSL2 跨文件系统小文件 I/O 慢，HA 重度读写 SQLite，有性能与损坏风险。可复现性改由 export/import 脚本保证 |
| D8 | 代码在**本机跑**，Docker 只装 HA | Windows 容器内 `uvicorn --reload` 的文件监听慢且易失效，断点调试困难 |
| D9 | **无 GPU 开发机不装 Ollama**，用 `StubProvider` | 开发专注确定性逻辑；真模型在带 GPU 的机器上验证。同时避免在资源受限的机器上跑大模型 |
| D10 | 数据库**不跨机器同步** | 最简单、无冲突，也避免私人对话进入 Git |
| D11 | `.gitattributes` 强制 `*.sh` 用 LF | Windows 下 CRLF 会让脚本进容器后直接失败 |
| D12 | 每个 Tool 带 `risk_level` | 高危操作（开门锁）走确认接口；MVP 用配置关闭，但接口保留 |

---

## 4. 模块设计

### 4.1 `llm/` — 大模型抽象

```
LLMProvider (Protocol)
├── StubProvider      确定性返回预置 tool_call，用于开发与测试
└── OllamaProvider    调用 Ollama /api/chat
```

- Agent 只依赖 `LLMProvider` 协议，不知道底层是 Ollama 还是别的东西
- 接口形态：`chat(messages, tools) -> AssistantMessage(content | tool_calls)`
- `OllamaProvider` 需要处理两件事：
  1. 模型是否支持原生 tool calling（支持的走原生，不支持的降级为「提示词约束 + 结构化输出 + Pydantic 校验 + 有限重试」）
  2. 若使用带 thinking 的模型，必须关闭思考模式，否则会污染结构化输出

### 4.2 `ha/` — Home Assistant 客户端

- `HomeAssistantClient` 是**唯一**的 HA 出口，封装 REST 与 WebSocket
- 职责：`get_state` / `call_service` / `health_check` / 超时 / 重试 / 错误映射为领域异常
- 所有请求带 `request_id` 便于追踪
- **禁止**在 Tool 或 Agent 中出现裸 HTTP 调用

### 4.3 `home/` — 拓扑与实体映射

`config/home_topology.yaml` 结构示意：

```yaml
rooms:
  living_room:
    display_name: 客厅
    devices:
      light:
        entity_id: light.living_room
        capabilities: [on_off, brightness]
      ac:
        entity_id: climate.living_room
        capabilities: [on_off, target_temperature]
      curtain: { entity_id: cover.living_room }
      tv:      { entity_id: media_player.living_room_tv }
      presence:    { entity_id: binary_sensor.living_room_presence }
      temperature: { entity_id: sensor.living_room_temperature }
  # bedroom / study / kitchen / entrance ...
home:
  vacuum: { entity_id: vacuum.robot_vacuum }
```

- `topology.py` 负责加载、校验、提供 `resolve(room, device)` 与「房间有哪些设备」查询
- **这是未来替换真实设备的唯一改动点**

### 4.4 `tools/` — 工具层

每个工具是一个显式注册的对象，包含：

- `name`、`description`
- `parameters`：JSON Schema（供 LLM 使用）
- `risk_level`：`SAFE` | `CONFIRM_REQUIRED`
- `execute(**kwargs) -> ToolResult`

`ToolResult` 统一为结构化结果：

```python
{ "ok": bool, "data": {...}, "error": None | {"code", "message"}, "meta": {...} }
```

约束：

- 必须校验房间与设备是否存在（非法输入返回结构化错误，不抛裸异常）
- 必须处理 HA 调用失败（超时、连接失败、服务不存在）
- **不得包含任何原始 HTTP 逻辑**，只调用 `HomeAssistantClient`
- 返回结构化结果，不返回自然语言句子（自然语言由 Agent 组织）

计划实现的工具：`get_home_state` / `get_room_state` / `turn_on_light` / `turn_off_light` / `set_light_brightness` / `set_ac` / `turn_off_ac` / `open_curtain` / `close_curtain` / `turn_on_tv` / `turn_off_tv` / `lock_front_door` / `unlock_front_door` / `get_temperature` / `get_presence` / `vacuum_start` / `vacuum_stop` / `vacuum_return_to_dock` / `activate_scene`

### 4.5 `agent/` — 意图路由与执行

```
IntentRouter
├── RuleStrategy    正则 / 关键词匹配高频固定句式，命中率高且零延迟
└── LLMStrategy     未命中时交给 LLM 做工具选择
```

- `Runner` 负责执行循环：路由 → 参数校验 → 权限检查 → 执行 → 结果 → 组织回复 → 写 trace
- **不暴露模型的思维链**，只暴露结构化信息（intent / tool / arguments / result）
- 支持多轮工具调用（先查状态再决策），但 MVP 限制最大轮数防止死循环

### 4.6 `memory/` — 记忆

SQLite（`data/jarvis.db`，WAL 模式，单写者）。表：

| 表 | 内容 |
|---|---|
| `conversations` | 会话 |
| `messages` | 消息 |
| `tool_calls` | 工具调用记录（含参数与结果） |
| `events` | 事件日志（系统级与用户级） |
| `scene_executions` | 场景执行记录 |
| `traces` | 单次请求的完整链路 |

**不做** RAG、向量检索、Milvus。MVP 的记忆只用于「记住最近的交互与事件」。

### 4.7 `api/` 与 `web/`

- `api/`：FastAPI 路由 —— 聊天、家庭状态、事件日志、健康检查
- `web/`：静态单页（HTML + 原生 JS），由 FastAPI 提供，**无构建步骤**
  - 考虑过 Vite + React，但 MVP 目标是验证架构而非 UI，无构建步骤更简单、换机零成本
  - 若后续 UI 变复杂再迁移不迟

UI 四个区块：聊天 / 当前家庭状态 / 事件日志 / 系统状态（JARVIS、Ollama、HA 的连接状态）。

---

## 5. 虚拟家庭

全部定义在 `homeassistant/config/packages/virtual_home.yaml`，由 `input_boolean` / `input_number` 作为状态载体，`template:` 平台派生出带真实 domain 的实体。

| 房间 | 设备 |
|---|---|
| 客厅 | 灯、空调、窗帘、电视、存在传感器、温度传感器 |
| 卧室 | 灯、空调、窗帘、存在传感器、温度传感器 |
| 书房 | 灯、空调、存在传感器、温度传感器 |
| 厨房 | 灯、存在传感器、温度传感器 |
| 玄关 | 前门锁、存在传感器 |
| 全屋 | 扫地机器人 |

关键点：

- 保留**真实的 domain**（`light` / `climate` / `cover` / `media_player` / `lock` / `vacuum` / `sensor`），而不是全用 `switch`。这样换真实设备时 service 调用形态不变
- `cover` / `lock` / `vacuum` 的 template 平台需要配合 `script` 与 `value_template`，是本阶段主要工作量
- **不提交** HA 的 `.storage/`、数据库、日志

---

## 6. 场景

场景**必须是确定性的**，由 `config/scenes.yaml` 定义，由应用代码执行。

内置场景：`HOME` / `MOVIE` / `SLEEP` / `MORNING` / `AWAY`。

**LLM 的工作只是：识别用户想触发哪个场景 → 调用 `activate_scene(name=...)`。**
绝不允许 LLM 为某个场景即兴编造动作序列。

---

## 7. 可观测性

每个请求生成 `request_id` 并贯穿全链路。可查看：

```
用户请求 → 识别到的意图 → 调用的工具 → 参数 → 执行结果 → 最终回复
```

- 链路写入 `traces` 表，并可通过 SSE 实时推给 UI
- 结构化日志（含 `request_id`）
- **不记录、不展示模型的思维链**

---

## 8. 错误处理与降级

| 故障 | 表现 | 要求 |
|---|---|---|
| HA 不可用 | 系统状态显示 `Home Assistant: DISCONNECTED` | JARVIS 继续运行，工具返回结构化错误 |
| Ollama 不可用 | 系统状态显示 `LLM: DISCONNECTED` | 自动回落到 `RuleStrategy`，基础指令仍然可用 |
| 非法房间/设备 | 返回结构化错误 | 不抛异常，不崩溃 |
| 模型输出非法参数 | Pydantic 校验失败 | 有限重试，仍失败则返回友好错误 |

原则：**任何外部服务故障都不能让整个应用崩溃。** 所有外部调用必须有超时。

---

## 9. 安全

- 源码中不含任何密钥、令牌、密码；`.env` 不提交
- HA 令牌通过环境变量注入
- 高危工具（如 `unlock_front_door`）标记 `CONFIRM_REQUIRED`，走确认接口
  - MVP 通过 `CONFIRM_HIGH_RISK=false` 关闭确认，但**接口与调用路径完整保留**
- 不提交：`.env`、数据库、日志、缓存、模型文件、Docker volume、`__pycache__`

---

## 10. 配置与可移植性

### 环境变量

| 变量 | 说明 | 无 GPU 开发机 | 带 GPU 机器 |
|---|---|---|---|
| `JARVIS_ENV` | `dev` / `prod` | `dev` | `dev` |
| `JARVIS_HOST` / `JARVIS_PORT` | 服务监听 | `127.0.0.1` / `8000` | 同左 |
| `HA_URL` | HA 地址 | `http://localhost:8123` | 同左 |
| `HA_TOKEN` | HA 长期访问令牌 | 各自生成，**不提交** | 各自生成，**不提交** |
| `LLM_PROVIDER` | `stub` / `ollama` | **`stub`** | `ollama` |
| `OLLAMA_URL` | Ollama 地址 | 未使用 | `http://localhost:11434` |
| `MODEL_NAME` | 模型名 | 未使用 | 例如 `qwen2.5:7b-instruct` |
| `DATABASE_URL` | SQLite 路径 | `sqlite:///./data/jarvis.db` | 同左（相对路径） |
| `CONFIRM_HIGH_RISK` | 高危操作确认开关 | `false` | `false` |
| `LOG_LEVEL` | 日志级别 | `DEBUG` | `INFO` |

### 禁止硬编码

文件系统绝对路径、用户名、IP 地址、机器专属配置、GPU 假设、API key、密码、HA token —— 全部走环境变量或配置文件。

### 换机初始化

```bash
git clone <repo>
cd jarvis
./scripts/setup.sh          # 建 venv、装依赖、生成 .env
docker compose up -d        # 起 Home Assistant
# 浏览器打开 HA，创建长期访问令牌，填入 .env 的 HA_TOKEN
uv run uvicorn jarvis.main:app --reload
```

Ollama 为可选项：需要真模型时安装本机 Ollama 并 `./scripts/pull_model.sh`，然后把 `LLM_PROVIDER` 改成 `ollama`。

### 跨平台注意

| 问题 | 处理 |
|---|---|
| Shell 脚本换行符 | `.gitattributes` 强制 `*.sh` 为 LF |
| Windows 路径 | 全部使用 `pathlib` 与相对路径 |
| HA 在 Windows | 只能跑在容器里；配置用 named volume 而非 bind mount |
| Docker GPU 直通 | Compose 中用 profile + 可选 device reservation，无 GPU 机器不启用 |

---

## 11. 决策记录（摘要）

| 编号 | 主题 | 结论 |
|---|---|---|
| D1 | 虚拟设备实现 | YAML template 实体（非 MQTT 模拟器、非 UI 手建） |
| D2 | 设备映射 | `home_topology.yaml` 单一真相 |
| D3 | 意图路由 | 规则优先 + LLM 兜底 |
| D4 | LLM 抽象时机 | Phase 1，配 StubProvider |
| D6 | 实现顺序 | 确定性优先，LLM 最后接 |
| D8 | 开发运行方式 | 代码本机跑，Docker 只装 HA |
| D9 | 无 GPU 机器的 Ollama | 不装，用 StubProvider |
| D10 | 记忆同步 | 不同步，各机器独立 |
| — | 前端 | 静态单页 + 原生 JS，无构建步骤 |
| — | 依赖管理 | `uv` + `uv.lock`，同时导出 `requirements.txt` 作为退路 |

---

## 12. 风险登记

| 风险 | 等级 | 缓解措施 |
|---|---|---|
| CPU-only 小模型 tool calling 不可靠 | **高** | 双路由（规则兜底）+ Pydantic 校验重试 + provider 接口预留未来换更好的模型 |
| 无 GPU 机器上推理极慢 | 中 | 该机器用 `stub` 开发；真模型只在带 GPU 机器上验证 |
| HA template 的 `cover`/`lock`/`vacuum` 有坑 | 中 | 需要 `script` + `value_template` 配合；预留充足调试时间 |
| HA 在 WSL2 下 SQLite 性能/损坏 | 中 | 用 named volume，不用 bind mount |
| HA 首次启动慢（1–3 分钟）、镜像约 1.5GB | 低 | 文档中说明；健康检查加长超时 |
| Ollama 冷启动首 token 10–30 秒 | 低 | UI 做流式状态提示 |
| Docker Desktop 商业授权 | 低（需确认） | 有顾虑时改用 WSL2 内免费 Docker Engine |
| SQLite 并发写 | 低 | WAL + 单写者 |
| 带 thinking 的模型污染结构化输出 | 中 | 调用时显式关闭思考模式 |

---

## 13. 未来扩展路径

架构需保证以下替换**不需要重写 Agent 与 Tool 层**：

| 现在 | 将来 | 改动点 |
|---|---|---|
| 虚拟灯（template） | 真实智能灯 | `home_topology.yaml` + HA 配对 |
| 虚拟传感器 | 真实传感器 | 同上 |
| Web 聊天 | 成品音箱（Siri 快捷指令 / 小爱）作为输入适配器 | 文字进、一句回复出的对话接口（Phase 10），Agent 接口不变 |
| 本机 PC | 专用 AI 服务器 / GPU 服务器 | `OLLAMA_URL` + `MODEL_NAME` |
| 虚拟扫地机 | 真实扫地机 | `home_topology.yaml` + HA 集成 |
| 虚拟 HA | 真实 HA 安装 | `HA_URL` + `HA_TOKEN` |
