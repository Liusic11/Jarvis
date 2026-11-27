# JARVIS 计划重评 v2（方向已定）

## 一、方向

| 事项 | 决定 |
|---|---|
| 定位 | 成品音箱当「嘴和耳朵」，JARVIS 当「脑子」 |
| 目的 | 学习和好用并重，长期迭代 |
| 阶段顺序 | 保持原样 4 → 5 → 6 → 7 → 8 → 9，末尾新增 Phase 10「接成品音箱」 |
| 音箱 | 都可以，优先 HomePod，到 Phase 10 再买 |

这个方向带来四个结论：

1. **语音链路永远不自己写。** ARCHITECTURE.md 已经写了「不做语音」，只需把「麦克风 + 唤醒词」那一行扩展方向改成「成品音箱作为输入适配器」。
2. **JARVIS 对外的核心契约是一句话：文字进，一句回复出。** Siri 也好、小爱也好，最后都是往这一个接口发文字。所以 Phase 7 的对话接口要按音箱的需求来设计：快、短句、能容忍语音转写的标点。
3. **JARVIS 必须比 HA 自带的 Ollama 集成好，才值得写代码。** 好在三处：规则命中的快路径（音箱链路本身就有延迟）、高危操作可控、每一层都能讲清楚。所以先用零代码把这个基线量出来。
4. **执行顺序不改。** 每个阶段收尾都有可演示的东西：Phase 4 之后能用接口控设备，Phase 5 之后有场景，Phase 7 之后能对话。

## 二、调研结论（供记录）

| 项目 | 做法 | 对 JARVIS |
|---|---|---|
| HA 官方 Ollama 集成 + Assist | 内置的本地模型控设备。默认先用规则，处理不了才给模型；模型只看得到暴露的实体；门锁永不自动暴露 | 印证「规则优先」。借来：暴露给模型的工具要少，高危设备不交给模型 |
| MyJarvis / Home Brain | 先写 33 句路由测试，只断言「第一次工具调用对不对」，再在自己硬件上横评模型 | 借来：评测集先于 Agent，作为验收标准 |
| Project JARVIS | 语音 + 文本，MCP 动态发现工具 | 不采用动态发现，18 个工具静态注册 |
| Home-LLM、assist-llm | 用合成数据微调小模型 | 不微调，先用通用模型 + 规则兜底 |
| HomePod 接 HA | HomeKit Bridge（官方）让 Siri 直接控设备；Siri 快捷指令把听写文字转给 HA 对话接口（社区） | 这是 Phase 10 的主路线 |
| 小爱音箱接 HA | 社区项目 xiaogpt，登录小米账号轮询对话记录 | 备选。账号要交给第三方脚本 |
| TinyLLM、Blue Teaming | 4B 以下模型工具调用准确率最高约 66%；开源模型的函数调用默认不安全 | 支持：参数必须校验，高危工具不让模型碰到 |

## 三、验证策略：三层，由便宜到贵

| 验证什么 | 做法 | 成本 | 何时做 | 不通过怎么办 |
|---|---|---|---|---|
| 小模型能不能控设备（用别人做好的） | HA 自带 Ollama 集成，手测 10 句 | 零代码 | 步骤 1 | 先解决网络和模型问题，不往下做 |
| 我们的工具设计，小模型能不能选对 | 冒烟脚本 + 36 句评测集 | 一个脚本 | 步骤 2 | 改描述、改命名、合并工具，最多两轮 |
| 一句话能不能真的动了设备 | 同一个脚本，灯的用例对真实 HA 执行 | 同上 | 步骤 2 | 问题出在 HA 服务还是模型，一看就知道 |
| 规则路由准不准 | `run_evals.py --strategy rule` | Phase 7 里写 | Phase 7 | 收紧规则，拿不准的交给模型 |
| 模型兜底准不准 | `run_evals.py --strategy llm` | 同上 | Phase 8 | 改提示词、换模型、合并工具 |
| 音箱这条路通不通 | MacBook 上的 Siri 快捷指令，不用买音箱 | 一条快捷指令 | Phase 10 | 换小爱方案，或退回文字界面 |

## 四、迭代机制（长期项目）

**每个阶段固定收尾五件事**：跑测试和 lint；对真实 HA 冒烟；跑评测并记数字；写一篇学习笔记；提交点（是否提交由你决定）。

**门槛不过的循环规则**：先改最便宜的东西（描述、提示词、规则表），再改结构（合并工具、换模型），最多两轮。两轮不过就停下来一起看，不硬磨。

**每次收尾回看三个问题**：这一阶段哪里和预想不一样？门槛数字要不要调？下一个阶段的范围要不要缩？

**范围控制**：新想法先记到 PHASES.md 的「待办」，不插队。

## 五、硬件分工

| 机器 | 配置 | 角色 |
|---|---|---|
| 本机 | i9-13900H，32GB 内存，无独显 | 开发、跑测试、Docker 里的 HA、JARVIS 服务 |
| 家里的台式机 | RTX 3070 Ti（8GB 显存），32GB 内存 | 只跑 Ollama |
| MacBook M2 | 8GB 内存 | Phase 10 用它的 Siri 做预演；Phase 9 换机演练 |

## 六、分步计划

### 步骤 0：环境就绪

1. **需要你操作**：在本机启动 Docker Desktop。
2. 仓库根目录执行 `docker compose up -d`，再 `curl http://localhost:8000/health`，确认 HA 状态正常。
3. **需要你操作**：在 3070 Ti 那台装 Ollama（Windows 版），设置系统环境变量 `OLLAMA_HOST=0.0.0.0`。不设的话只监听本机，局域网连不上。
4. **需要你操作**：在那台机器上 `ollama pull qwen2.5:7b-instruct` 和 `ollama pull qwen3:8b`。Windows 防火墙拦了入站的话，放行 11434 端口（专用网络）。
5. 本机验证：`curl http://<那台机器的IP>:11434/api/tags` 能列出两个模型。连不上先查 `OLLAMA_HOST` 和防火墙。
6. 本机 `.env` 里把 `JARVIS_OLLAMA_URL` 改成 `http://<那台机器的IP>:11434`。`JARVIS_LLM_PROVIDER` 保持 `stub`，到 Phase 8 才切。

### 步骤 1：零代码基线

目的：先看别人做好的「本地模型控设备」在同一套虚拟家庭上表现如何。这个数字就是 JARVIS 要超过的线。

1. **需要你操作**：打开 `http://localhost:8123`，设置 → 设备与服务 → 添加集成 → Ollama，地址填 `http://<那台机器的IP>:11434`（容器里不能填 localhost），模型选 `qwen2.5:7b-instruct`。
2. 同一界面：设置 → 语音助手，把助手的对话代理换成刚加的 Ollama，确认「设备控制」这组 AI 工具是开着的。
3. 在对话面板里手测 10 句，记下每句的对错和大概等多久：
   - 打开客厅灯、把客厅灯关了、客厅灯调到 50%、打开卧室空调、卧室空调调到 24 度
   - 打开客厅窗帘、打开客厅电视、解锁前门、扫地机开始打扫、卧室有人吗
4. 把结果记到 `docs/PHASES.md`，表格三列：句子、HA 自带的结果、备注。
5. 如果 10 句里对了不到 5 句，问题在网络或模型，不在设计。先排查，不往下做。

补充：「解锁前门」这句预期是不会执行的，因为 HA 不让模型碰门锁。这是正常的。

### 步骤 2：模型冒烟测试

目的：在写工具代码之前，知道两个模型对着**我们的** 18 个工具能选得多准。

1. 新建 `evals/cases.yaml`，36 条。30 条正例覆盖 18 个工具，其中 8 条故意口语化（「有点暗，把客厅弄亮点」「卧室好冷」）；6 条负例是不该调工具的闲聊。字段：`id`、`text`、`expect.tool`（负例为 null）、`expect.args`。
   - 不放「房间不存在」「参数越界」的用例，模型选了不存在的房间算对算错有争议。这些留给单元测试。
2. 新建一次性脚本 `scripts/spike_llm_routing.py`：手写 18 个工具的 JSON Schema（中文描述），逐条发给 Ollama 的 `/api/chat`，温度 0，关闭思考模式。
3. **真执行一部分**：期望结果是开灯或关灯的用例，脚本真的去调 HA，再读回灯的状态核对。这就是第一条端到端：一句话 → 模型选工具 → 灯亮了。
4. 输出一张表：每个模型的「工具名正确率」「工具名和参数都对」「负例未误调」「中位延迟」。原始输出写到系统临时目录，不入库。
5. **门槛**：至少一个模型正例工具名 ≥ 90%，工具名加参数 ≥ 80%，负例 6 条至少 5 条不误调。
6. 不达标时按第四节循环，最多两轮。
7. 结果表记到 `docs/PHASES.md`。脚本留到 Phase 7 的 `run_evals.py` 接手后删除。

### 步骤 3：把方向写进文档

1. `README.md`：定位一段改成「成品音箱当嘴和耳朵，JARVIS 当脑」，长期目标不变。
2. `docs/ARCHITECTURE.md`：扩展方向那一行的「麦克风 + 唤醒词」改成「成品音箱（Siri 快捷指令或小爱）作为输入适配器」。
3. `docs/PHASES.md`：新增 Phase 10；新增「验证记录」小节，放步骤 1、2 的结果表；新增「待办」小节。
4. 提交点。

### Phase 4：工具层

目录 `src/jarvis/tools/`，只依赖 `HomeAssistantProtocol` 和 `Topology`，不含 HTTP 调用。阶段顺序和范围与原计划一致，补三处设计决定。

**基类与注册表**

1. 新建 `base.py`：
   - `RiskLevel`：`SAFE`、`CONFIRM_REQUIRED`。
   - `ToolResult`：`{ok, data, error: None | {code, message}, meta}`。
   - 抽象类 `Tool`：`name`、`description`、`risk_level`、Pydantic 参数模型 `Args`、`async execute(**kwargs)`、`spec()`（返回 `llm/base.py` 里已有的 `ToolSpec`）。
   - `DeviceTool` 基类：持有客户端和拓扑，声明自己操作哪个 `device_key`，负责校验房间、设备、能力。`room` 同时接受房间 key 和中文名。
   - 房间参数的描述由拓扑生成（「房间名，可选：客厅、卧室、书房、厨房」）。不做枚举，冒烟显示模型会填错房间时再改。
2. 新建 `registry.py` 的 `ToolRegistry`：`register`、`get`、`names`、`llm_specs()`、`build_default()`、`call(name, args, confirmed=False)`。

**三个设计决定**

- **域名一律取 `device.domain`，不写死。** 电视现在是 `switch` 冒充的，换成真实的 `media_player` 时只改拓扑。
- **`unlock_front_door` 不进 LLM 工具清单。** `llm_specs()` 排除所有 `CONFIRM_REQUIRED` 的工具，模型根本看不到它。只有明确的规则指令能触达，且必须二次确认。`lock_front_door`（上锁）是安全的，照常可见。
- **`call()` 是唯一入口，按固定顺序把关**：工具名 → Pydantic 校验参数 → 高危确认 → 执行。任何一步失败都返回结构化错误，不抛异常。

**18 个工具**

| 类别 | 工具 | 发给 HA 的服务 |
|---|---|---|
| 状态 | `get_home_state()`、`get_room_state(room)` | 逐个读实体状态 |
| 灯 | `turn_on_light`、`turn_off_light`、`set_light_brightness(room, brightness)` | `light.turn_on`、`turn_off`、`turn_on` 带 `brightness_pct`（1–100） |
| 空调 | `turn_on_ac`、`set_ac(room, temperature)`、`turn_off_ac` | `climate.set_hvac_mode`（制冷）、`set_temperature`（16–30）、`turn_off` |
| 窗帘 | `open_curtain`、`close_curtain` | `cover.open_cover`、`close_cover` |
| 电视 | `turn_on_tv`、`turn_off_tv` | `<domain>.turn_on`、`turn_off` |
| 门锁 | `lock_front_door()`、`unlock_front_door()` | `lock.lock`、`lock.unlock` |
| 只读 | `get_temperature(room)`、`get_presence(room)` | 读传感器 |
| 扫地机 | `vacuum_start()`、`vacuum_stop()`、`vacuum_return_to_dock()` | `vacuum.start`、`stop`、`return_to_base` |

- `set_ac` 发现空调关着时，先制冷开机再设温度。
- 传感器状态是 `unavailable` 或 `unknown` 时返回 `entity_unavailable`。

**实现顺序，每步做完都跑测试**

3. `base.py` + `registry.py` + 测试：Schema 能序列化、未知工具返回 `unknown_tool`、非法参数返回 `invalid_args`、`llm_specs()` 里没有开锁。
4. `light.py` + 测试。这是第一个完整工具，把模式跑通，然后立刻对真实 HA 试一次「开客厅灯」。
5. 依次写 `climate.py`、`cover.py`、`lock.py`、`sensor.py`、`vacuum.py`、`state.py`，各配测试。
6. 给 `mock_client.py` 补一处：把 `brightness_pct` 记到实体属性里，亮度工具的测试才能断言结果。
7. 每个工具的测试覆盖四种情况：成功、房间或设备不存在、HA 不可用、能力不支持。门锁另加确认开关的两种状态。
8. 架构测试：扫描 `src/jarvis/tools/`，出现 `httpx` 即失败。

**接口与接线**

9. `main.py` 启动时构建注册表挂到 `app.state`；`deps.py` 加 `get_tool_registry`。
10. 新建 `api/routes/tools.py`：`GET /api/tools`；`POST /api/tools/{name}/call`，请求体 `{args, confirm}`。这个调试接口对高危工具始终要求 `confirm: true`，不受配置开关影响。
11. `Settings.confirm_high_risk` 和 `.env.example` 的默认值改成 `true`。

**对真实 HA 冒烟**

12. 新建 `scripts/smoke_tools.py`：对真实 HA 依次执行 18 个工具，打印结果，有失败退出码非零。
13. 重点看两处只能推测的行为：对关着的灯发 `brightness_pct: 50`，亮度是否变成 50；对关着的空调直接设温度，是否会开机。
14. 冒烟暴露的差异回到对应工具修掉，再跑。

**收尾**

15. 更新 `docs/ARCHITECTURE.md`：D12 补「高危工具不进 LLM 清单」、电视 domain 说明、环境变量名、D7 改为 bind mount。
16. 新建 `docs/learn/04-phase4-tools.md`，讲四个概念：注册表模式、JSON Schema 与参数校验、最小权限、依赖倒置。
17. 提交点。验收：测试全绿、lint 通过、冒烟全过、`llm_specs()` 里没有开锁、工具层无 HTTP 调用。

### Phase 5：场景（原计划，范围不变）

1. 新建 `config/scenes.yaml`，五个场景：回家、观影、睡眠、早安、离家。每步是「工具名 + 参数」，用拓扑里的房间 key，不含高危工具。
2. 新建 `scenes/engine.py`：启动时加载校验，引用了不存在的工具或高危工具就启动失败。执行时某步失败只记录、不中断。
3. 新建 `tools/scenes.py` 的 `activate_scene(name)`，注册进注册表，对 LLM 可见。
4. 评测集加 3 条场景用例。
5. 测试用替身；冒烟脚本加一项「跑五个场景」。
6. 收尾五件事。验收：执行观影场景后查实体状态符合预期；未知场景名返回结构化错误；场景内容全在配置文件里。

### Phase 6：记忆（原计划，范围不变）

1. 新建 `memory/schema.sql`：会话、消息、工具调用、trace、场景执行五张表，外加版本号表。
2. `memory/db.py`：连接管理，开 WAL，启动自动建表，幂等。
3. `memory/repo.py`：各表的读写。
4. trace 只记结构化字段，不记模型的思维链。
5. 确认 `data/` 已在 `.gitignore`。
6. 收尾五件事。验收：启动自动建表；一条完整链路能写进去再读回来。

### Phase 7：对话接口、规则路由、Web 界面（原顺序，补音箱相关设计）

这是第一次「说一句话，设备动了」。不需要模型。

**对话接口（按音箱的需求设计）**

1. 新建 `api/routes/chat.py`：`POST /api/chat`。
   - 请求：`{text, session_id}`。
   - 响应：`{reply, speak, steps}`。`speak` 是给音箱播的短句（30 字以内），`reply` 给界面看，可以更详细。
   - 带 `?format=text` 时只返回纯文本的 `speak`，给 Siri 快捷指令的「朗读文本」用。
2. 新建 `agent/normalize.py`：进来的文字先归一化，去首尾空白和标点（语音转写常带句号）。
3. **接口此时仍只监听本机，不加鉴权。** 对局域网开放和令牌放到 Phase 10 一起做。

**规则路由**

4. 新建 `agent/router.py` 的 `RuleStrategy`：
   - 房间和设备名用拓扑已有的 `find_room`、`find_device`，代码里不出现「客厅」。
   - 动作用一张声明式规则表：设备类型、动词表、对应工具、参数提取。如灯的「打开、开、开一下、亮」对应 `turn_on_light`。
   - 句子里没房间、而多个房间都有这种设备（「开灯」），不调用，反问是哪个房间。
   - **规则只认高确定性的句式。** 规则命中就直接执行，错一次就是动错设备；漏掉只是转给模型。
5. 新建 `agent/replies.py`：每个工具一条 `speak` 模板（「客厅灯已打开」「卧室现在 24.5 度」）。
6. 新建 `agent/runner.py`：
   - 按顺序问策略，谁给出调用就停。
   - 遇到 `confirmation_required`，记为「待确认」并反问。同一会话下一句是「确认、是的、好」就执行，「算了、不用」就取消。待确认状态先放内存。
   - 规则没命中、又没配模型时，回复没听懂，并给两三个例句。
7. 把 `spike_llm_routing.py` 改造成 `scripts/run_evals.py`，Schema 改为从注册表读，支持 `--strategy rule`，然后删除冒烟脚本。

**门槛**：`run_evals.py --strategy rule` 输出覆盖率和准确率。**命中的用例准确率必须 100%，覆盖率 ≥ 70%。**

**Web 界面（定位为调试和演示面板）**

8. 新建 `api/routes/state.py`：当前家庭状态。先用轮询。
9. 新建 `web/static/` 下的 `index.html`、`styles.css`、`app.js`，四个区块：聊天、家庭状态、事件日志、系统状态。每条消息可展开看工具、参数、结果。实现界面时用 frontend-design 技能。
10. 高危操作在界面上弹二次确认，确认后带 `confirm` 重发。
11. 用浏览器实测：正常对话、规则未命中的提示、HA 停掉后状态区显示未连接。
12. 用 curl 对真实 HA 跑 PHASES.md 里 Phase 7 的七句话。
13. 收尾五件事。验收：门槛达标、七句话通过、「关掉厕所的灯」返回未知房间且应用不崩。

### Phase 8：接入真模型（原计划，补评测门槛）

1. 新建 `llm/ollama_provider.py`：调 `/api/chat`，工具转函数定义格式，不流式，温度 0，关闭思考模式。连接失败和超时抛 `LLMError`。
2. 新建 `agent/prompt.py`：系统提示词由拓扑生成，不含地址、令牌、绝对路径。
3. `agent/router.py` 加 `LLMStrategy`：把 `llm_specs()` 给模型。工具名不存在或参数校验失败时，把错误回传给模型重试，最多 2 次。
4. `llm/factory.py` 加 `ollama` 分支。`runner.py` 在模型不可用时自动只用规则，并在响应里标明。
5. `run_evals.py` 加 `--strategy llm` 和 `--strategy auto`，支持 `--model`。
6. **门槛**：`llm` 策略正例工具名 ≥ 90%、工具名加参数 ≥ 80%，负例至少 5 条不误调；`auto` 策略工具名 ≥ 95%。延迟只记录。
7. 和步骤 1 的基线对比，结果表记到 `docs/PHASES.md`。**如果没超过基线，停下来一起看。**
8. `.env` 切到 `JARVIS_LLM_PROVIDER=ollama`。
9. 收尾五件事。验收：门槛达标；`stub` 下行为不变；关掉 Ollama 后自动回落到规则。

### Phase 9：打磨与文档（原计划）

1. 补错误场景测试：HA 挂、模型挂、非法输入、超时。
2. README 补快速开始、双机分工、`OLLAMA_HOST` 和防火墙的常见问题。
3. 三份文档同步到最终状态。
4. 换机演练：在 MacBook 上 fresh clone 跑通测试和启动，模型仍连 3070 Ti 那台。
5. 检查仓库里没有 `.env`、数据库、日志、密钥。

### Phase 10：接成品音箱（新增）

**选型**：优先 HomePod。HomeKit Bridge 是 HA 官方集成，Siri 快捷指令不用把账号交给第三方。小爱作备选。

1. **零成本预演，不用买音箱**：在 MacBook 的快捷指令里建一条「问管家」：听写文本 → 请求 `POST http://<开发机IP>:8000/api/chat?format=text` → 朗读返回的文本。对 Mac 说「嘿 Siri，问管家，打开客厅灯」。
   - 这一步要实测一件事：Mac 上 Siri 能否语音触发这条快捷指令并朗读结果。
2. **对局域网开放**：应用改为监听局域网地址；新增 `JARVIS_API_KEY`，对话接口和工具调用接口校验 `Authorization: Bearer`。只对这两个会动设备的接口加。
3. **HomeKit Bridge**：HA 里添加这个集成，暴露灯、空调、窗帘、开关。这样「嘿 Siri，打开客厅灯」这类固定指令走 Apple 自己的路，不过脑子，最快。
4. **快捷指令正式版**：「嘿 Siri，问管家 + 任意一句话」走 JARVIS，有规则、模型、确认。
5. **验收**：对音箱说 10 句。8 句正例设备要动；「解锁前门」要反问确认；1 句闲聊不能动任何设备。记录从说完到音箱出声的延迟。
6. **已知坑**（来自社区）：回复在 HomePod 上播放可能落到 iPhone 上，变通办法是让 HA 侧发 webhook 推给音箱播放；每台音箱要各配一条快捷指令。
7. 收尾五件事，外加一篇学习笔记讲「成品和自研的边界怎么划」。

如果到时候改选小爱，先确认 xiaogpt 的自定义接口方式，再回来细化这一阶段。

## 七、验证命令汇总

仓库根目录执行：

```
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts\smoke_tools.py
.\.venv\Scripts\python.exe scripts\run_evals.py --strategy rule
.\.venv\Scripts\python.exe scripts\run_evals.py --strategy llm --model qwen2.5:7b-instruct
```

当前基线：73 个测试通过。

## 八、假设与约定

- 测试期间两台机器同时开机，同一局域网。
- `.env` 里已有的 HA 令牌在容器重启后仍有效。
- Docker Desktop 需要你手动启动。
- 评测门槛（90% / 80% / 70% / 95%）是按 30 条正例定的初始值，冒烟后可以调。
- 提交点只是建议边界，我不会主动提交。
- HomePod 要到 Phase 10 才买，前面的阶段不需要任何硬件。

## 参考来源

- [Home Assistant：Assist](https://www.home-assistant.io/voice_control/)
- [Home Assistant：AI-powered local smart home](https://home-assistant.io/blog/2025/09/11/ai-in-home-assistant)
- [Home Assistant：暴露实体给语音助手](https://www.home-assistant.io/voice_remote_expose_devices/)
- [Home Assistant：Ollama 集成](https://www.home-assistant.io/integrations/ollama/)
- [Home Assistant：HomeKit Bridge](https://www.home-assistant.io/integrations/homekit/)
- [社区：通过 Siri 与 HA 语音助手对话](https://community.home-assistant.io/t/talk-to-your-ha-voice-assistant-via-siri/905997)
- [MyJarvis / Home Brain](https://bitworking.org/news/2026/05/surprising-things-i-learned-putting-together-a-home-brain/)
- [Project JARVIS](https://pypi.org/project/project-jarvis/)
- [xiaogpt 实战指南](https://blog.gitcode.com/c2fbfa56ccb746d4be8965d3a964b45a.html)
- [Home Assistant 米家集成（小米官方）](https://gitee.com/zjjjunjian/ha_xiaomi_home/blob/main/doc/README_zh.md)
- [TinyLLM](https://dl.acm.org/doi/10.1145/3801487.3805608)
- [Blue Teaming Function-Calling Agents](https://arxiv.org/html/2601.09292)
