# JARVIS 学习笔记（给 Mike 的实践资料）

> 这套文档的定位：**不是给工程师看的技术规格，是给你（Mike）看得懂、能照着动手复现的学习资料。**
> 写它的目的——让你搞清楚「每一步在干什么、为什么这么搭、你自己要怎么做、整个系统是怎么一步步长出来的」。

---

## 0. 这套资料给谁看、怎么用

**读者画像（来自你的 `~/.claude/CLAUDE.md`）**：AI 产品经理 / 投资者，Python/SQL 基础，**能看懂、能改代码，但不会从零写**；前端不会。要求讲清「**这是什么、能做什么、不能做什么**」。

**和另外两份文档的分工**：

| 文档 | 给谁看 | 内容 |
|---|---|---|
| `docs/ARCHITECTURE.md` | 工程师 | 架构决策与理由（偏技术，有出入时以代码为准） |
| `docs/PHASES.md` | 工程师/规划 | 9 个阶段的计划与验收标准 |
| **`docs/LEARN.md` + `docs/learn/*.md`** | **你（Mike）** | **用大白话讲「在干什么、为什么、你能怎么动手」**，并如实标注文档与代码的偏差 |

**建议阅读顺序**：
1. 先读 [`learn/00-foundations.md`](learn/00-foundations.md) —— **技术通识**，从零讲 Docker / HTTP / API / FastAPI / YAML / Home Assistant / LLM / WebSocket / 环境变量，每个都给「是什么 + 原理类比 + 本项目里干什么 + 还能用在哪」，最后用一次「打开客厅灯」串起所有技术。
2. 再读本文件（总纲）建立全局观。
3. 然后按 `docs/learn/` 编号从 `01` 往后读，每篇对应一次已完成的工作（落地细节）。

---

## 1. JARVIS 一句话心智模型

```
你说一句话
   ↓
JARVIS Agent（理解意图，决定调哪个工具）
   ↓
LLM（大模型，负责「听懂人话」；没 GPU 时用规则兜底）
   ↓
Tool（标准化的动作，如「开灯」）
   ↓
HomeAssistantClient（唯一对外出口，封装所有 HTTP）
   ↓
Home Assistant（运行在 Docker 里的智能家居中枢）
   ↓
虚拟设备（用 YAML 造出来的灯/空调/窗帘…，不用真硬件）
```

**关键纪律（贯穿全项目）**：LLM 永远不能直接给 Home Assistant 发 HTTP 请求。它只能调标准工具，工具再交给 `HomeAssistantClient`。这样换真设备、换真 LLM 都不用重写上层。

---

## 2. JARVIS 现在能做什么 / 还不能做什么

> 这是你的硬要求，我每次都更新这段。

**已经能做的（截至 2026-09-03）**：
- ✅ 项目骨架已建好，能跨机器复现（环境变量 + 配置文件驱动，无硬编码）。
- ✅ Home Assistant 容器已在 Docker 里跑起来（端口 8123，状态 healthy）。
- ✅ 一个**虚拟家庭**已在 HA 里注册完成：4 灯、3 空调、2 窗帘、1 电视、1 门锁、1 扫地机、4 温度传感器、5 有人传感器，共 21 个"真 domain"实体。
- ✅ 配置系统、健康检查、Stub LLM、HA 客户端骨架、22 个测试已就绪。
- ✅ 仓库里 `uv run pytest` 能跑通，HA 容器探活正常。

**还做不到的（卡点 / 未做）**：
- ❌ 还不能「对话控制」设备——因为 JARVIS 应用还没连上 HA（缺 HA 长期令牌，写入 `.env` 属于你的红线操作，需你确认后才做）。
- ❌ 还没有真实 LLM 接入（现在用 Stub 假模型，只验证链路，不真听懂人话）。
- ❌ 还没有 Web 界面、场景、记忆库等（这些是 Phase 5 以后的事）。

---

## 3. 术语小词典（速查；完整原理见 [`learn/00-foundations.md`](learn/00-foundations.md)）

| 词 | 大白话 |
|---|---|
| **Docker / 容器** | 一个打包好、独立运行的小环境。HA 跑在里面，跟你本机其它东西隔离。 |
| **docker-compose** | 一个描述「起哪些容器、怎么连」的配置文件（YAML）。一条命令拉起整套环境。 |
| **Home Assistant (HA)** | 开源智能家居中枢。我们让它管"虚拟家庭"，将来也能管真设备。 |
| **YAML** | 一种人类可读的配置格式（缩进表示层级，像大纲）。本项目大部分"定义"都写在这里。 |
| **entity_id / domain** | HA 里每个设备的唯一 ID，如 `light.living_room`。`light` 是 domain（设备类型），后面是名字。 |
| **template 实体** | 用一小段"公式"从别的实体派生出新实体。我们的虚拟设备主要靠它造。 |
| **环境变量 / .env** | 把密钥、地址等配置放在文件里传给程序，不写进代码。本项目用 `JARVIS_` 前缀读取。 |
| **REST / HTTP** | 程序之间"发请求拿结果"的通用方式。JARVIS 通过它指挥 HA。 |
| **WebSocket** | 一种长连接通信，用于 HA 的某些命令（如取长期令牌）。 |
| **LLM / tool calling** | 大模型"听懂人话并决定调用哪个工具"。 |
| **Stub** | 一个"假的"替身，行为确定、可控，用来在不依赖真模型的情况下把整条链路测通。 |
| **Ollama** | 在你本机跑大模型的服务。带 GPU 的机器才用。 |
| **FastAPI** | 我们 JARVIS 应用用的 Web 框架。 |
| **Pydantic** | 帮我们"校验配置对不对"的 Python 库。 |
| **uv** | 现代的 Python 依赖/环境管理工具（比 pip 快）。 |

---

## 4. 每篇学习笔记的固定结构

`docs/learn/NN-*.md` 每篇都按这个格式写，方便你快速定位：

1. **这次做了啥**（结论先行，一两句说完）
2. **为什么这样搭**（关键决策与理由）
3. **这是什么 / 能做什么 / 不能做什么**（科普框，给你这种"不会从零写"的人）
4. **你自己怎么动手**（复现 / 改动的步骤，命令我会解释在干什么）
5. **踩过的坑**（真实错误与修复，避免你重蹈）
6. **当前状态 / 下一步**

---

## 5. 目录索引

### 已完成（可阅读）
- [`00-foundations.md`](learn/00-foundations.md) — **技术通识基础**：Docker / HTTP·REST / API / FastAPI / YAML / Home Assistant / LLM·tool calling / WebSocket / 环境变量，含「打开客厅灯」完整串讲
- [`01-phase1-repo-skeleton.md`](learn/01-phase1-repo-skeleton.md) — 仓库骨架、配置系统、健康检查、Stub LLM、HA 客户端骨架、22 测试（已提交 commit `1267388`）
- [`02-phase2-virtual-home.md`](learn/02-phase2-virtual-home.md) — 用纯 YAML 造出 21 个虚拟设备，HA 容器跑起来（已落盘，未提交）

### 计划中（进度推进时新增）
- `03-phase3-topology-and-client.md` — 拓扑配置 + 真正的 HA 客户端（连上设备）
- `04-phase4-tools.md` — 工具层（开灯/调温等标准化动作）
- `05-phase5-scenes.md` — 场景（"电影模式"一键联动）
- `06-phase6-memory.md` — 记忆库（SQLite）
- `07-phase7-web-and-rules.md` — Web 界面 + 规则路由（此时能对话控制）
- `08-phase8-llm.md` — 接入真实 LLM
- `09-phase9-polish.md` — 测试、可观测性、文档打磨

> 完整阶段计划见 `docs/PHASES.md`。

---

## 6. 从零把项目跑起来（给非写代码者的概览）

> 以下是从 `git clone` 到能看到 HA 页面的完整路径。**密钥/令牌相关步骤（第 4 步）是红线，我会先问你再动。**

1. **装依赖**：`uv sync` —— 把 Python 依赖装进隔离环境（不污染你系统）。
2. **起 HA**：`docker compose up -d` —— 按 `docker-compose.yml` 拉起 Home Assistant 容器。
3. **等它健康**：`docker compose ps` 看到 `healthy` 即可（首次启动慢，1–3 分钟）。
4. **拿 HA 令牌填入 `.env`**（⚠️ 红线，需你确认）—— 浏览器开 `http://localhost:8123`，建账号、生成长期访问令牌（LLAT），写进 `.env` 的 `JARVIS_HA_TOKEN`。
5. **起 JARVIS 应用**：`uv run uvicorn jarvis.main:app --reload` —— 应用监听 `http://127.0.0.1:8000`。
6. **探活**：`curl http://localhost:8000/api/health` 应返回 JSON。

---

## 7. 约定：每次做完工作，新增一篇笔记

**规则（已固化）**：每次完成一个阶段、或一次有意义的工作，就在 `docs/learn/` 下新增 `NN-*.md`，并把链接加进上面的「目录索引」。

这样这个项目会**随时间自动积累成一套完整的、讲人话的搭建教程**——既是给你看的学习资料，也是将来换机器复现的说明书。

---

## 8. 文档与代码不一致记录（已核实）

> 这些偏差我会持续在这里登记，避免你照着过时文档踩坑。

| 位置 | 文档说 | 代码实际 | 状态 |
|---|---|---|---|
| `ARCHITECTURE.md` D7 | HA 用 named volume | 已改为 **bind mount** `./homeassistant/config:/config` | 需在 ARCHITECTURE 里改正 |
| `ARCHITECTURE.md` §10 环境变量表 | `HA_URL` / `HA_TOKEN` / `LLM_PROVIDER`… | 实际带 `JARVIS_` 前缀：`JARVIS_HA_URL` / `JARVIS_HA_TOKEN` / `JARVIS_LLM_PROVIDER`… | 需在 ARCHITECTURE 里改正 |
| `ARCHITECTURE.md` §5 | cover/lock/vacuum 用 template + script | 实际用 `generic_thermostat`(空调) + `template switch`(电视)，未用 script | 描述可简化 |
