# JARVIS

本地优先（local-first）的个人 AI 家庭助手原型。

长期愿景是《钢铁侠》里那种 JARVIS：语音交互、全屋传感器、灯光空调窗帘家电、本地大模型、长期记忆、自动化。但**现在还没有真实硬件**，所以当前项目是一个**纯软件的、可迁移到真实智能家居的原型**。

语音这部分不自己写：**成品音箱当「嘴和耳朵」，JARVIS 当「脑」**。音箱负责听和说，把听到的话转成文字交给 JARVIS；JARVIS 负责听懂、决定、控制设备，再回一句话让音箱播出来。所以 JARVIS 对外的核心契约只有一条：**文字进，一句回复出**。接音箱是最后一个阶段（Phase 10），前面的阶段不需要任何硬件。

核心要证明的事情只有一件：

```
自然语言 → 本地 LLM → Agent → Tool Calling → Home Assistant → 虚拟家庭
```

这条链路能稳定跑通，并且未来把「虚拟设备」换成「真实设备」时，Agent 和 Tool 不需要重写。

---

## 当前状态

**Phase 1–3 已完成** —— 仓库骨架与配置系统、可复现虚拟家庭（21 个虚拟设备）、拓扑语义层与 Home Assistant 客户端（73 个测试全绿，已对真实 HA 验证）。

| 阶段 | 内容 | 状态 |
|---|---|---|
| 1 | 仓库骨架与配置基础设施 | ✅ 已完成 |
| 2 | Home Assistant 与可复现虚拟家庭 | ✅ 已完成 |
| 3 | 拓扑配置与 HomeAssistantClient | ✅ 已完成 |
| 4 | 工具层 | 未开始 |
| 5 | 场景 | 未开始 |
| 6 | 记忆（SQLite） | 未开始 |
| 7 | API 与 Web UI + 规则路由 | 未开始 |
| 8 | LLM Provider 与 Agent | 未开始 |
| 9 | 测试、可观测性打磨、文档 | 未开始 |
| 10 | 接成品音箱（Siri 快捷指令 / 小爱） | 未开始 |

详细的阶段计划与验收标准见 [`docs/PHASES.md`](docs/PHASES.md)，每一步的实测数字记在其中的「验证记录」小节。
架构设计与决策理由见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。
**给非工程背景的学习笔记（讲人话、每次做完工作一篇）见 [`docs/LEARN.md`](docs/LEARN.md)。**

---

## 明确不做（当前阶段）

以下都属于未来阶段，**当前不实现**：

- 任何物理硬件：Zigbee、Matter、真实灯具/传感器/扫地机
- 麦克风阵列、唤醒词、Whisper、TTS
- 摄像头与真实存在检测
- RAG、向量数据库、Milvus
- Kubernetes、分布式系统、微服务拆分

当前唯一目标是**用虚拟设备证明架构可行**。

---

## 环境要求

| 组件 | 版本 | 必需 | 说明 |
|---|---|---|---|
| Python | ≥ 3.11 | 是 | 推荐用 [uv](https://docs.astral.sh/uv/) 管理 |
| Docker + Compose | 近期版本 | 是 | **仅用于跑 Home Assistant**（HA 不支持 Windows 原生安装） |
| Ollama | 近期版本 | 否 | 有 NVIDIA GPU 的机器上才需要；无 GPU 可用 `stub` provider 开发 |
| Git | 任意 | 是 | |

跨平台目标：Windows / Linux / macOS 都能跑。Windows 上的已知差异记录在 `docs/ARCHITECTURE.md` 的「可移植性」一节。

> **Docker Desktop 授权提醒**：Docker Desktop 对大型企业的商业使用需要付费订阅。若在开发机上有合规顾虑，可在 WSL2 中直接安装免费的 Docker Engine 作为替代。请自行确认所在组织的政策。

---

## 快速开始

### 1. 初始化

```bash
./scripts/setup.sh          # Windows (PowerShell): .\scripts\setup.ps1
```

脚本会检查 uv → 安装依赖 → 从 `.env.example` 生成 `.env` → 建好 `data/` 与 `homeassistant/config/`。

没有 uv 的话先装一个：

```bash
# Windows
winget install astral-sh.uv
# macOS
brew install uv
# Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 启动 Home Assistant

```bash
docker compose up -d
docker compose ps            # 等状态变成 healthy
```

首次启动需要 1–3 分钟。之后打开 <http://localhost:8123> 完成首次引导，
创建长期访问令牌（左下角用户名 → 安全 → 创建令牌），填进 `.env` 的 `JARVIS_HA_TOKEN`。

> HA 配置通过 **bind mount** 直接挂在宿主机 `homeassistant/config/`（非 named volume），改 YAML 即时生效，无需导出脚本。

### 3. 启动 JARVIS

```bash
uv run uvicorn jarvis.main:app --reload
```

### 4. 验证

```bash
curl http://localhost:8000/api/health
```

还没配 HA 令牌时会返回：

```json
{
  "status": "degraded",
  "env": "dev",
  "version": "0.1.0",
  "services": {
    "jarvis":         { "status": "online",       "detail": "running", "latency_ms": null },
    "home_assistant": { "status": "disconnected", "detail": "未配置 JARVIS_HA_TOKEN", "latency_ms": 3.1 },
    "llm":            { "status": "disconnected", "detail": "stub provider：未连接任何模型", "latency_ms": null }
  }
}
```

**注意 HA 不可用时接口依然返回 200**，只是整体状态标成 `degraded`。这是刻意的降级行为：
任何外部服务故障都不能让 JARVIS 崩掉。

### 常用命令

```bash
uv run pytest                          # 跑测试（不需要 HA 或 Ollama）
uv run ruff check .                    # 静态检查
docker compose logs -f homeassistant   # 看 HA 日志
docker compose down                    # 停 HA（YAML 配置保留在宿主机 homeassistant/config/，不受影响）
```

---

## 仓库结构（概览）

```
config/           home_topology.yaml（Phase 3 起：设备映射唯一真相）、scenes.yaml（Phase 5 起）
homeassistant/    HA 配置与 virtual_home.yaml（可复现的虚拟家庭）
src/jarvis/       llm / ha / home / tools / agent / memory / api / web
tests/            单元测试与集成测试
scripts/          初始化、HA 配置导出导入等辅助脚本
docs/             ARCHITECTURE.md、PHASES.md、LEARN.md（学习笔记，见 learn/ 子目录）
```

---

## 配置

所有机器相关的配置走环境变量。复制 `.env.example` 为 `.env` 后按需填写：

```bash
cp .env.example .env
```

**`.env` 永不提交。** 令牌、密钥、数据库、日志、模型文件全部在 `.gitignore` 中。

---

## 多机器工作流

本仓库设计为在多台机器间流转（例如一台无 GPU 的开发机 + 一台带 NVIDIA GPU 的家用机）：

- **代码与虚拟家庭定义**：通过 Git 同步，fresh clone 即可重建相同环境
- **环境变量**：每台机器各自维护自己的 `.env`（不提交）
- **数据库与对话历史**：**不同步**，每台机器独立
- **模型**：不提交，通过 `scripts/pull_model.sh` 按需拉取
- **依赖**：由 `uv.lock` 锁定，保证两台机器依赖版本一致

详细的换机初始化步骤见 `docs/ARCHITECTURE.md`。

---

## 安全

- 源码中不含任何密钥、令牌、密码
- 高危操作（如开前门锁）在架构层面带确认机制，MVP 阶段可通过配置关闭
- 不提交 `.env`、数据库、日志、Docker volume

---

## 许可

个人项目。如需开源，待定。
