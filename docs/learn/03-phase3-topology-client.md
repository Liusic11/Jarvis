# 03 · Phase 3 — 拓扑语义层与 Home Assistant 客户端

> 🔰 读这篇前若对 HTTP / REST / API / Home Assistant / entity_id 还模糊，先读 [`learn/00-foundations.md`](00-foundations.md)（技术通识），第 2、3、6、9.5 课与本阶段直接相关。
> 对应状态：**已完成并验证**（73 个测试全绿；21 个 entity_id 已对真实 HA 逐个校验通过；真实开关灯冒烟成功）。

---

## 这次做了啥（结论）

给 JARVIS 装上了**"能真正控制设备"的底座**，两块：

1. **拓扑语义层**（`config/home_topology.yaml` + `src/jarvis/home/topology.py`）
   全系统唯一知道「客厅 + 灯 = `light.living_room_light`」的地方。
2. **HA 客户端**（`src/jarvis/ha/`）
   全系统唯一能向 HA 发 HTTP 请求的地方，提供读状态、调服务的能力，
   外加一个不联网的测试替身。

**一句话**：以前 JARVIS 只能"问 HA 你还好吗"；现在它能说"把客厅灯打开"，并且灯真的会亮。

**实测**（对着真实 HA 跑的，不是模拟）：
```
拓扑解析 living_room/light -> light.living_room_light | ok: True
初始状态 : off
turn_on  : ok
开灯后   : on
关灯后   : off
客厅温度 : 22.5 °C
```

---

## 本课新增的 6 个概念（先给地图）

| # | 概念 | 一句话 | 为什么需要 |
|---|---|---|---|
| 1 | 拓扑映射层 | 一张「人话 ↔ 机器 id」的翻译表 | 换真设备时只改一张表 |
| 2 | Protocol（接口契约） | 先约定"长什么样"，再谈实现 | 让测试替身能顶替真客户端 |
| 3 | 结构化结果 | 失败用返回值表达，而不是抛异常 | HA 挂了要能回复用户，不是崩掉 |
| 4 | 幂等与重试 | 读可重试，写绝不重试 | 防止"灯其实开了但响应丢了"导致重复动作 |
| 5 | 测试替身（Mock） | 不联网的假实现 | 测试要快、稳、可离线 |
| 6 | 防腐层 | 把外部 JSON 挡在自家类型之后 | 外部格式变了，内部不受影响 |

下面逐个讲透，最后用一次完整旅程把它们串起来。

---

## 概念一：拓扑映射层 —— 为什么要单独做一张"翻译表"

### 是什么

一张把**人类语义**（房间 + 设备）翻译成 **HA 的 entity_id** 的配置表：

```yaml
living_room:            # 房间逻辑键
  name: 客厅
  aliases: [客厅, 大厅, 起居室]
  devices:
    light:              # 设备逻辑键
      name: 客厅灯
      entity_id: light.living_room_light   # ← HA 真正认识的 id
      domain: light
      capabilities: [on_off, brightness]   # 这个设备能干什么
      aliases: [灯, 灯光, 照明]
```

### 原理（类比）

把它想成**公司前台的分机表**。

- 来访者说"我找市场部的小张"——这是**人话**。
- 前台查表，拨 `内线 8023`——这是**机器能懂的地址**。
- 如果小张换了工位、分机号变了，**只需要改前台那张表**，
  所有来访者该怎么说还怎么说，完全不受影响。

没有这张表会怎样？每个需要打电话的人，都得自己记住"小张 = 8023"。
等小张换号，就得把公司里所有记过这个号码的人全部通知一遍——这就是**硬编码的代价**。

### 在本项目里干什么

- **解耦**：将来把虚拟设备换成真实设备，entity_id 必然变化。
  有这一层就只改 `config/home_topology.yaml`，Tools / Agent / 场景一行都不用动。
  （这正是你在最初需求里定的"换真设备不用改代码"的落地方式。）
- **可校验**：启动时能逐个确认 entity_id 真的存在于 HA，
  避免"代码写着能开灯、实际实体不存在"这种到运行才炸的问题。
- **语义集中**：中文别名都在这张表里，未来的规则路由直接查表，
  不用在代码里散落一堆 `if "客厅" in text`。

对应的代码是 `src/jarvis/home/topology.py`，核心 API：

```python
topology.resolve("living_room", "light")     # -> entity_id
topology.find_room("打开客厅灯")              # -> "living_room"
topology.find_device("living_room", "客厅现在几度")  # -> "temperature"
```

**关键设计：`resolve()` 返回结构化结果，不抛异常。**
用户说了一个不存在的房间，这是**正常的业务结果**（要回复他"没有这个房间"），
不是程序错误——所以不该用异常表达（详见概念三）。

### 还能用在哪

这个模式的正式名字叫"**间接层 / 映射表**"，到处都是：

- **DNS**：域名 ↔ IP。网站换服务器只改 DNS 记录，用户照样输同一个网址。
- **环境变量**：同一个配置项在不同机器上值不同，代码只读名字。
- **数据库 ORM 的字段映射**：Python 属性名 ↔ 数据库列名。
- **微服务里的服务发现**：服务名 ↔ 实际地址。

凡是"一边会变、一边不想跟着变"的地方，都可以插一张表。

---

## 概念二：Protocol —— 先定契约，再谈实现

### 是什么

Python 的 `Protocol`（结构化类型 / 鸭子类型）用来定义"**一个对象应该长什么样**"：

```python
@runtime_checkable
class HomeAssistantProtocol(Protocol):
    async def health_check(self) -> HomeHealth: ...
    async def get_state(self, entity_id: str) -> HAResult[EntityState]: ...
    async def get_states(self) -> HAResult[list[EntityState]]: ...
    async def call_service(self, domain: str, service: str, data=None) -> HAResult[Any]: ...
    async def aclose(self) -> None: ...
```

只要某个类**有这些方法、签名一致**，它就被认为"是"这个 Protocol 的实例——
**不需要继承、不需要注册**。这就是"鸭子类型"：走起来像鸭子、叫起来像鸭子，那它就是鸭子。

### 原理（类比）

**电源插座标准。**

- 插座标准规定：三孔、220V、这个形状。这是**契约**。
- 台灯、电扇、充电器，只要插头符合这个标准就能插上去——
  它们彼此毫无关系，不需要继承自同一个"电器基类"。
- 发电厂升级了、换了个供应商，只要你家插座标准没变，**你的电器一个都不用改**。

### 在本项目里干什么

- **测试替身能顶替真客户端**：`MockHomeAssistantClient` 只要实现同样的方法就能顶上，
  单元测试因此完全不需要真的起 HA 容器（快、稳、可离线）。
  我们有专门的测试断言两者都符合契约：

  ```python
  def test_mock_client_satisfies_protocol():
      assert isinstance(MockHomeAssistantClient(), HomeAssistantProtocol)
  ```

- **将来换实现不影响调用方**：加缓存层、换 HTTP 库、甚至换成别的智能家居中枢，
  上层 Tools / Agent 一行都不用改。

这就是软件工程里"**依赖倒置**"（依赖抽象，而不是依赖具体实现）最轻量、最 Pythonic 的做法。

### 还能用在哪

- 任何"可能有多种实现"的地方：数据库驱动、支付渠道、消息队列、云存储 SDK。
- 写库给别人用时，用 Protocol 定义入参要求，比强制继承某个基类友好得多
  （对方不用改自己的类继承体系）。

---

## 概念三：结构化结果 vs 抛异常

### 是什么

我们的 HA 客户端**对外方法一律不抛异常**，而是返回：

```python
@dataclass(frozen=True)
class HAResult(Generic[T]):
    ok: bool
    data: T | None = None
    error_code: str = ""   # 机器可读：unavailable / unauthorized / not_found ...
    message: str = ""      # 人话：可以直接回复用户
```

### 原理（类比）

**去医院体检拿报告单。**

- 报告单上写"某项指标异常"——这是**结果**，医生据此告诉你该注意什么。
- 如果体检中心一发现异常就直接**拉响火警、整个大楼疏散**——那就是"抛异常"，
  反应过度了：一个人指标异常，不该让整栋楼停摆。

异常应该留给"**程序自己都没想到的状况**"（代码 bug），
而不是"**早就预料到会发生的状况**"（HA 没起、令牌过期、实体不存在）。

### 在本项目里干什么

HA 挂掉、令牌失效、实体不存在，全都是**可预期的运行状态**。
上层要据此回复用户（"Home Assistant 现在连不上"），而不是让整个请求 500。

内部实现上我们仍然用异常，但只在**模块内部**用：

```
HTTP 层出错
   ↓  抛 HomeAssistantUnavailable / HomeAssistantAuthError（内部）
模块边界
   ↓  翻译成 HAResult(ok=False, error_code=...)
调用方
   ↓  只看 ok / error_code，永远不用写 try/except
```

这个"内部用异常、边界上翻译成结果"的模式叫**异常边界**（exception boundary）。

**唯一的例外**：拓扑文件本身写错（`TopologyError`）**必须抛异常让应用启动失败**——
那是配置缺陷，绝不能带着错误的设备映射继续跑。

### 还能用在哪

- Web API 的错误响应：`{"ok": false, "error": "xxx"}`，而不是直接 500。
- 表单校验：返回错误清单，而不是抛 `ValidationError` 让页面崩掉。
- 任何"失败是正常流程一部分"的场景（支付被拒、库存不足、权限不够）。

---

## 概念四：幂等与重试 —— 为什么"写操作绝不重试"

### 是什么

我们定的规则：

| 操作类型 | 例子 | 遇到瞬时故障会重试吗 |
|---|---|---|
| **读** | `get_state` / `get_states` | ✅ 会（最多 3 次） |
| **写** | `call_service`（开灯、开锁） | ❌ **一次都不重试** |

代码里就是 `attempts=1` 这一行，外加注释说明原因。

### 原理（类比）

**你在自助售票机买票。**

- 你点了"确认支付"，机器卡了一下，屏幕转圈——**你不知道票到底出没出**。
- 这时候如果你再点一次"确认支付"，很可能**买了两张票**。
- 但如果你是"查询余票"（读操作），点多几次完全无所谓，结果都一样。

**幂等（idempotent）** 就是这个性质：**做一次和做多次，效果相同**。
读操作天然幂等；写操作（尤其是支付、开锁、发消息）通常不是。

### 在本项目里干什么

`call_service` 一次调用可能**已经生效**（灯其实已经开了），只是响应丢了或超时。
盲目重试会造成重复动作——最典型的例子是**连开两次门锁**。

所以我们让写操作只发一次，失败就如实上报，让上层（或用户）决定要不要再来一次。
对应的测试专门锁死这个行为：

```python
async def test_call_service_does_not_retry(ha_client):
    ...
    assert attempts["n"] == 1, "写操作只允许发一次"
```

这条测试的意义是：将来谁手滑改坏了重试策略，测试会立刻拦住他。

### 还能用在哪

- **支付接口**：必须带幂等键（idempotency key），否则网络重试会重复扣款。
- **消息队列**：消费者可能收到重复消息，处理逻辑要幂等。
- **数据库迁移脚本**：要能重复执行而不出错。
- 凡是"重试"的地方，先问自己一句：**这个操作重试一次会怎样？**

---

## 概念五：测试替身（Mock）—— 让测试不依赖真实环境

### 是什么

`MockHomeAssistantClient`：一个**不联网**的假 HA，接口与真客户端完全一致。

它不只是"调用就返回成功"，而是**真的改变内存里的状态**：

```python
client = MockHomeAssistantClient({"light.living_room_light": "off"})
await client.call_service("light", "turn_on", {"entity_id": "light.living_room_light"})
assert client.state_of("light.living_room_light") == "on"   # 状态真的变了
```

### 原理（类比）

**飞行员训练用的模拟舱。**

- 真飞机：贵、要排队、天气不好就不能飞、摔了就出大事。
- 模拟舱：便宜、随时可用、可以反复练"引擎失灵"这种极端情况，摔了重来就是。

测试替身就是代码的"模拟舱"——而且它还能**模拟真实环境里很难复现的故障**
（HA 挂掉、服务返回 500、令牌失效），这些在真实环境里反而测不方便。

### 在本项目里干什么

- 单元测试**不需要起 Docker / HA 容器**：毫秒级、可离线、结果完全确定。
  73 个测试跑完 8 秒。
- 能覆盖真实环境不好造的异常路径：`available=False` 模拟 HA 挂掉、
  `fail_services={"light.turn_on"}` 模拟某个服务失败。
- 记录所有调用（`client.calls`），方便断言"到底发了什么指令"。
- **为 Phase 4（工具层）铺路**：将来测"开灯工具"时，直接用它就能验证
  "工具确实调了 `light.turn_on`、且状态真的变了"。

### 还能用在哪

- 单元测试中替换数据库、文件系统、时钟、随机数、第三方 API。
- 前端开发中先造假接口，后端还没好也能并行开发。
- 混沌工程：注入故障验证系统的降级能力。

---

## 概念六：防腐层 —— 别让别人的格式污染你的代码

### 是什么

HA 的 `/api/states` 返回的是一大坨 JSON。我们没有把它直接传给上层，
而是在 `ha/models.py` 里定义了自己的类型：

```python
@dataclass(frozen=True)
class EntityState:
    entity_id: str
    state: str
    attributes: dict[str, Any]
    last_changed: str | None
    last_updated: str | None

    @classmethod
    def from_payload(cls, payload): ...   # ← 唯一的"翻译点"
```

### 原理（类比）

**出国旅行用的转换插头 + 变压器。**

- 外国的电是 110V、插头形状也不同（**外部格式**）。
- 你的笔记本需要稳定的 220V 标准输入（**内部格式**）。
- 转换头负责中间那一层转换。将来去另一个国家，换一个转换头就行，
  **你的笔记本不用改**。

如果没有这一层，你的代码里就会到处散落 `payload["attributes"]["friendly_name"]`
这种直接读外部 JSON 的写法——一旦 HA 改字段名，你得改遍整个项目。

### 在本项目里干什么

- 上层（Tools / Agent）只认识 `EntityState`，完全不知道 HA 的 JSON 长什么样。
- 将来 HA 改字段、甚至换成别的智能家居平台，**只改 `from_payload`**，上层一行不动。
- 顺带把"只读得上的字段"挑出来，避免把 HA 的完整状态对象整个搬进内部。

### 还能用在哪

- 调用任何第三方 API 时都值得做：支付回调、天气 API、社交媒体数据。
- 数据库层：SQL 结果 → 领域对象。
- 微服务之间：对方的 DTO → 自己的领域模型（避免"上游改字段，下游全线崩"）。

---

## 完整旅程：说一句"打开客厅灯"，这些模块怎么协作

把上面 6 个概念串成一条线（注意：其中"听懂人话"那一步属于 Phase 7，现在还没做）：

```
① 用户说："打开客厅灯"
        │
        │  ← Phase 7 才实现：规则路由 / LLM 识别意图
        ▼
② 找出房间和设备
     topology.find_room("打开客厅灯")            -> "living_room"
     topology.find_device("living_room", "打开客厅灯") -> "light"
        │  【概念一：拓扑映射层】
        ▼
③ 解析成 entity_id
     topology.resolve("living_room", "light")
        -> Resolution(ok=True, entity_id="light.living_room_light")
        │  查不到就返回 ok=False + 错误码，不抛异常【概念三】
        ▼
④ 调用客户端（依赖的是 Protocol，不是具体类）【概念二】
     await client.call_service("light", "turn_on",
                               {"entity_id": "light.living_room_light"})
        │  写操作只发一次，不重试【概念四】
        ▼
⑤ 客户端发 HTTP（全系统只有这一个地方发）【防腐层在 models.py】
     POST http://localhost:8123/api/services/light/turn_on
     Authorization: Bearer <JARVIS_HA_TOKEN>
        ▼
⑥ HA 执行，返回受影响实体的新状态
        │
        ▼
⑦ 客户端把 HA 的 JSON 转成 EntityState【概念六】
     HAResult(ok=True, data=[EntityState(...state="on"...)])
        │  失败则是 ok=False + error_code，绝不抛异常【概念三】
        ▼
⑧ 上层据此回复用户："客厅灯已打开"
```

单元测试跑这条链路时，第 ④ 步的 `client` 直接换成 `MockHomeAssistantClient`，
于是 ⑤⑥ 全部跳过，整个测试在内存里毫秒级完成【概念五】。

---

## 这次新增 / 改动了哪些文件

**新增**
| 文件 | 作用 |
|---|---|
| `config/home_topology.yaml` | 拓扑映射表：6 个房间/区域、21 个设备、中文别名、能力声明 |
| `src/jarvis/home/topology.py` | 加载 / 严格校验 / `resolve` / 别名查找 |
| `src/jarvis/ha/models.py` | `EntityState` / `HAResult` / `HomeHealth` / 错误码常量 |
| `src/jarvis/ha/protocol.py` | `HomeAssistantProtocol` 接口契约 |
| `src/jarvis/ha/mock_client.py` | 不联网的测试替身，会真的改状态 |
| `tests/test_topology.py` | 拓扑：解析、结构化错误、别名、加载校验 |
| `tests/test_ha_client_rest.py` | 客户端 REST：错误映射、重试策略 |
| `tests/test_mock_client.py` | 测试替身：协议一致性、状态变化 |
| `scripts/validate_topology.py` | 对真实 HA 逐个校验 entity_id |

**改动**
- `src/jarvis/ha/client.py`：新增 `get_state` / `get_states` / `call_service`，
  加入超时、重试（读写有别）、错误映射；`health_check` 行为保持不变。
- `src/jarvis/ha/__init__.py`、`src/jarvis/home/__init__.py`：导出新模块。
- `pyproject.toml` / `requirements.txt`：显式声明 `pyyaml` 依赖。

---

## 怎么自己验证

```bash
# 1. 单元测试（不需要 HA 容器，离线可跑）
.venv/Scripts/python.exe -m pytest -q          # 73 passed

# 2. 对真实 HA 校验拓扑里每个 entity_id 是否存在
.venv/Scripts/python.exe scripts/validate_topology.py
#    输出：✓ 全部 21 个 entity_id 都在 HA 中存在

# 3. 确认"只有 client.py 发 HTTP"这条架构约束
grep -rn "httpx" src/ scripts/ --include=*.py
#    期望：只有 src/jarvis/ha/client.py 真正 import 并使用
```

---

## 当前能做什么 / 还不能做什么

**✅ 现在能**
- 用 `(房间, 设备)` 查出 entity_id；查不到时拿到结构化错误而不是崩溃
- 从 HA 读取任意实体状态（灯、空调、传感器……）
- 调用 HA 服务真的改变设备状态（开灯、关窗帘、设温度、开锁……）
- 在完全不联网的情况下测试上述所有逻辑

**❌ 现在还不能**
- **听懂人话**：说"打开客厅灯"让 JARVIS 自己执行——那是 **Phase 7**（规则路由）。
  Phase 3 只提供了"能被程序调用来控制设备"的能力，还没有"理解自然语言"的入口。
- **WebSocket 订阅**：`PHASES.md` 原计划 Phase 3 做 "REST + WebSocket"。
  本期**只做了 REST**，因为 Phase 4–7 全部用 REST 轮询即可满足，
  WebSocket 属于"实时推送"的锦上添花，放到需要时（事件流 / SSE）再补。
  （已在 `PHASES.md` 里如实标注，避免文档与代码不一致。）

---

## 下一步：Phase 4 —— 工具层

Phase 3 给的是"**能**控制设备"，Phase 4 要把它包装成**结构化的工具**：

- 每个工具（开灯、设温度、锁门……）都有 **JSON Schema**，将来能直接给 LLM 用
- 参数校验：亮度必须在 0–100，房间必须存在 → 返回结构化错误，不崩溃
- 高危操作（开锁）标记 `risk_level = CONFIRM_REQUIRED`，需要二次确认
- 全部用 `MockHomeAssistantClient` 测试，不需要 HA 容器

到 Phase 4 结束时，距离"说一句话就开灯"就只差 Phase 7 的路由了。
