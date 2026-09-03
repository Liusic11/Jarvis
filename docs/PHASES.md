# JARVIS 分阶段实施计划

**总原则：确定性优先，LLM 最后接。**
每个阶段结束时，系统都应该是可运行、可测试的状态。不允许「做了一半没法验证」就进入下一阶段。

状态图例：`未开始` / `进行中` / `已完成`

---

## 每个阶段结束的通用检查清单

进入下一阶段前，必须全部满足：

1. 应用能正常启动
2. 测试全部通过
3. 手动验证结果与预期一致
4. 修复发现的错误
5. 更新 README 与本文档（状态、快速开始、新增的配置项）
6. 确认没有提交 `.env`、数据库、日志、密钥

**不允许在没实际验证的情况下声称某功能可用。**

---

## Phase 1 — 仓库骨架与配置基础设施

**目标**：建立可跨机器复现的项目骨架，完成配置系统、日志、健康检查骨架，并让 Home Assistant 能通过 Docker 起来。

**产出**

- `git init` + `.gitignore` + `.gitattributes`（`*.sh` 强制 LF）
- 目录骨架：`src/jarvis/**`、`config/`、`homeassistant/config/`、`tests/`、`scripts/`
- `.env.example`（含全部变量的注释说明）
- `pyproject.toml`（uv 管理）+ `uv.lock` + 导出的 `requirements.txt`
- `config.py`：基于 Pydantic Settings 的配置加载与校验
- `logging.py`：结构化日志 + `request_id`
- `main.py`：FastAPI 应用工厂 + `/api/health`
- `llm/base.py`：`LLMProvider` 协议与消息类型
- `llm/stub_provider.py`：确定性 Stub
- `docker-compose.yml`：仅 Home Assistant（`full` profile 预留 Ollama + GPU）
- `scripts/setup.sh`（及 Windows 等效脚本）
- README 的快速开始章节

**验收标准**

```bash
uv sync                                    # 依赖装好
docker compose up -d                       # HA 容器起来
docker compose ps                          # 状态 healthy
curl http://localhost:8123                 # 能拿到 HA 页面
uv run pytest                              # 测试通过（至少覆盖配置加载）
uv run uvicorn jarvis.main:app --reload    # 应用启动
curl http://localhost:8000/api/health      # 返回 JSON，含 HA 连接状态
```

- HA 未启动时 `/api/health` 必须返回 `home_assistant: "disconnected"` 而**不能崩溃**
- 故意填错 `HA_TOKEN` 时，健康检查应报告未授权，应用仍正常运行

---

## Phase 2 — Home Assistant 与可复现虚拟家庭

**目标**：用纯 YAML 定义完整虚拟家庭，fresh clone 可重建相同环境，无需在 UI 中手动创建设备。

**产出**

- `homeassistant/config/configuration.yaml`
- `homeassistant/config/packages/virtual_home.yaml`（全部虚拟设备）
- 必要的 `script` 定义（供 template cover / lock / vacuum 使用）
- `scripts/ha_export.sh` / `scripts/ha_import.sh`（named volume 的备份与恢复）
- 设备清单文档（房间 / 设备 / entity_id）

**验收标准**

```bash
docker compose down -v && docker compose up -d   # 从零重建
# 等待 HA 启动完成后：
curl -H "Authorization: Bearer $HA_TOKEN" http://localhost:8123/api/states
```

- 返回的状态列表中包含全部预期实体（5 个房间 + 扫地机）
- 实体 domain 正确：`light.*` / `climate.*` / `cover.*` / `media_player.*` / `lock.*` / `vacuum.*` / `sensor.*` / `binary_sensor.*`
- 通过 REST 调用 `light.turn_on` 能改变 `light.living_room` 的状态
- 通过 REST 调用 `cover.open_cover` 能改变窗帘状态
- **完全通过 HA UI 创建任何实体即为失败**
- `export` 再 `import` 后环境一致

> 注意：本阶段的主要工作量在 `cover` / `lock` / `vacuum` 的 template 配置上，需要 `script` + `value_template` 配合，预留调试时间。

---

## Phase 3 — 拓扑配置与 HomeAssistantClient

**目标**：建立逻辑语义层与 entity_id 的映射，并实现唯一的 HA 出口。

**产出**

- `config/home_topology.yaml`
- `home/topology.py`：加载、校验、`resolve(room, device)` 查询
- `ha/models.py` / `ha/errors.py`
- `ha/client.py`：REST + WebSocket、超时、重试、错误映射、健康检查
- `ha/mock_client.py`：实现同一 Protocol 的测试替身
- 单元测试（用 mock client，不依赖 HA 容器）
- 集成测试（可选，标记 `integration`，对真实 HA 跑）

**验收标准**

- 单元测试全绿（不需要 HA 容器）
- `resolve("living_room", "light")` 返回正确 entity_id
- `resolve("nonexistent_room", "light")` 返回结构化错误，不抛裸异常
- 拓扑 YAML 中引用的每个 entity_id 都能在真实 HA 中存在（写一个校验脚本跑一遍）
- 代码中全局搜索确认：**除 `ha/client.py` 外没有任何地方出现 HTTP 调用**

### 状态：✅ 已完成（2026-09-03）

**实测结果（全部对真实 HA 验证过）**

```bash
.venv/Scripts/python.exe -m pytest -q     # 73 passed（含 Phase 1 的 22 个，无回归）
.venv/Scripts/python.exe scripts/validate_topology.py
# ✓ 全部 21 个 entity_id 都在 HA 中存在
```

| 验收项 | 结果 |
|---|---|
| 单元测试全绿（不依赖 HA 容器） | ✅ 73 passed，8 秒跑完 |
| `resolve("living_room","light")` | ✅ 返回 `light.living_room_light` |
| `resolve("nonexistent_room","light")` | ✅ 返回 `Resolution(ok=False, error="unknown_room")`，不抛异常 |
| 每个 entity_id 在真实 HA 中存在 | ✅ 21/21 通过（`scripts/validate_topology.py`） |
| 只有 `ha/client.py` 发 HTTP | ✅ grep 确认（另两处为文档字符串与日志器名） |
| 真实控制设备 | ✅ 冒烟：`turn_on → state=on → turn_off → state=off`，温度读得 22.5 °C |

**与计划的偏差（如实记录）**

- 原计划 "`ha/client.py`：REST **+ WebSocket**"。本期**只实现了 REST**。
  理由：Phase 4–7（工具、场景、记忆、规则路由）全部用 REST 轮询即可满足，
  WebSocket 属于"实时事件推送"的增强，放到真正需要事件流 / SSE 时再补。
  刻意不为了对齐文档而做一半用不上的东西。
- 额外补充：`pyproject.toml` 显式声明了 `pyyaml`（此前只是 uvicorn 的传递依赖）。

---

## Phase 4 — 工具层

**目标**：实现全部结构化工具，参数校验、错误处理、结构化返回。

**产出**

- `tools/base.py`：`Tool` 抽象、JSON Schema、`risk_level`、`ToolResult`
- `tools/registry.py`：工具注册与查找
- 工具实现：灯光、空调、窗帘、电视、门锁、传感器、扫地机
- 单元测试（用 `MockHomeAssistantClient`）
- 针对真实 HA 的冒烟测试脚本

**验收标准**

- 每个工具都有 JSON Schema，可被序列化供 LLM 使用
- 非法房间 / 非法设备 / 越界亮度值 → 返回结构化错误，不崩溃
- HA 不可用时 → 返回 `ok: false` + 错误码，不抛出未捕获异常
- 全部工具在真实 HA 上冒烟通过（脚本可一键跑）
- `unlock_front_door` 的 `risk_level` 为 `CONFIRM_REQUIRED`
- 代码中确认：**工具层没有任何原始 HTTP 调用**

---

## Phase 5 — 场景

**目标**：确定性场景，由配置定义、由代码执行，LLM 只负责识别场景名。

**产出**

- `config/scenes.yaml`（`HOME` / `MOVIE` / `SLEEP` / `MORNING` / `AWAY`）
- `scenes/engine.py`：加载、校验、按序执行、失败处理
- `tools/scenes.py`：`activate_scene(name=...)`
- 场景执行记录写入 `scene_executions` 表（表结构可先占位）
- 测试

**验收标准**

- 执行 `MOVIE` 场景后，通过 REST 查询确认相关实体状态符合预期
- 未知场景名返回结构化错误
- 场景中某个设备调用失败时，记录错误但**不中断整个场景**
- 确认**没有任何路径**允许 LLM 即兴编造场景动作

---

## Phase 6 — 记忆（SQLite）

**目标**：持久化会话、消息、工具调用、事件、场景执行与请求链路。

**产出**

- `memory/schema.sql`
- `memory/db.py`：连接管理（WAL）、初始化、迁移脚本
- `memory/repo.py`：各表的读写方法
- `trace` 写入逻辑：记录 intent / tool / arguments / result
- 测试（用临时数据库）

**验收标准**

- 应用启动自动建表（幂等）
- 写入一条会话 → 消息 → 工具调用 → trace，能完整读回
- 数据库文件不进 Git
- 并发读写不报错（WAL 生效）
- trace 中**不含模型思维链**，只有结构化字段

---

## Phase 7 — API、Web UI 与规则路由

**目标**：打通端到端链路。**此时不需要 Ollama**，用规则路由就能对话。

**产出**

- `api/routes/`：`chat` / `state` / `events` / `health`
- `agent/router.py` 的 `RuleStrategy`：覆盖高频句式
- `agent/runner.py`：执行循环 + trace + 回复组织
- `web/static/`：`index.html` + `app.js` + `styles.css`
  - 四个区块：聊天 / 当前家庭状态 / 事件日志 / 系统状态
- SSE 推送执行步骤（可选但推荐）

**验收标准**

以下语句在 `LLM_PROVIDER=stub` 下全部正确执行：

- 「打开客厅灯」→ 灯状态变为 on
- 「客厅灯调到 50%」→ 亮度正确
- 「卧室现在几度」→ 返回温度数值
- 「打开电影模式」→ 执行 MOVIE 场景
- 「我要睡觉了」→ 执行 SLEEP 场景
- 「家里现在什么情况」→ 返回各房间状态汇总
- 「关掉厕所的灯」→ 返回「未知房间」的结构化错误（不崩溃）

其他：

- UI 四个区块都能正常显示，系统状态正确反映 HA / LLM 连接情况
- 聊天区能看到 intent / tool / arguments / result
- HA 停掉后，UI 显示 `Home Assistant: DISCONNECTED`，应用不崩溃
- 规则未命中时有明确提示

---

## Phase 8 — LLM Provider 与 Agent

**目标**：把真实 LLM 作为可插拔的意图策略接进来，规则优先、LLM 兜底。

**产出**

- `llm/ollama_provider.py`：原生 tool calling + JSON 降级路径
- `llm/factory.py`：按 `LLM_PROVIDER` 创建实例
- `agent/router.py` 的 `LLMStrategy`
- `agent/prompt.py`：系统提示词与工具描述生成
- 参数校验失败重试逻辑
- `scripts/pull_model.sh`
- 测试（用 StubProvider 覆盖路由逻辑；Ollama 相关标记为 `integration`）

**验收标准**

- `LLM_PROVIDER=stub` 时行为与 Phase 7 完全一致（回归）
- `LLM_PROVIDER=ollama` 且在带 GPU 的机器上：
  - 上述 Phase 7 的全部语句仍正确执行
  - 额外的口语化表达（「有点暗，把客厅弄亮点」）能被正确路由到工具
- Ollama 不可用时自动回落到规则路由，UI 显示 `LLM: DISCONNECTED`
- 模型输出非法参数时触发重试，超过上限返回友好错误
- 系统提示词中**不含任何机器专属信息**

---

## Phase 9 — 测试、可观测性打磨与文档

**目标**：补齐测试覆盖，打磨调试体验，完善文档。

**产出**

- 关键路径的集成测试
- 完整可观测性：每个请求可在 UI 中看到完整链路
- 错误场景测试矩阵（HA 挂、Ollama 挂、非法输入、超时）
- README 完善（快速开始、多机器工作流、常见问题）
- `docs/ARCHITECTURE.md` 与本文档同步到最终状态
- 换机演练：在另一台机器上从零 clone → setup → 跑通

**验收标准**

- `uv run pytest` 全绿
- 换机演练成功：fresh clone 后按 README 步骤能完整跑通
- 所有失败场景都能优雅降级，无未捕获异常
- 文档与实际代码一致（无过时描述）
- 仓库中确认无 `.env`、数据库、日志、密钥、绝对路径

---

## 阶段间的依赖

```
Phase 1 ──> Phase 2 ──> Phase 3 ──> Phase 4 ──┐
                                              ├──> Phase 5 ──> Phase 6 ──> Phase 7 ──> Phase 8 ──> Phase 9
```

Phase 4（工具）与 Phase 5（场景）都依赖 Phase 3（拓扑 + Client）。
Phase 7 是第一个可以真正「对话」的阶段，Phase 8 只是把意图来源从规则换成 LLM + 规则。
