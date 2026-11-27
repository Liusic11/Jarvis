# JARVIS

一个长期演进的个人 AI
Agent。长期目标是成为一个能够理解主人、持续运行，并通过不同工具与数字世界和物理环境交互的个人智能体。

对标《钢铁侠》里的
JARVIS：它不属于某个设备、某个模型或某个应用。智能家居是第一个应用场景，而不是项目边界。

当前仍处于原型阶段：先以文字入口和 Home Assistant
虚拟设备验证最小闭环，再逐步扩展
Web、屏幕、电脑等能力。现在还没有接入真实家庭硬件。

## 项目方向

**长期目标：Personal AI Agent。当前落地：Smart Home first。**

JARVIS
的价值不在于控制某一类设备，而在于能够理解用户的任务，并通过可替换的能力模块完成任务。

长期可能涉及的能力包括：

-   智能家居与物理设备
-   Web 搜索与信息整理
-   电脑和应用操作
-   文件与日程管理
-   长期个人上下文与记忆
-   多步骤任务协调

这些是长期能力方向，不代表当前阶段都要实现。

## 架构原则

1.  **解耦（Decoupling）**：模块职责清晰，通过稳定接口协作；更换一个模块不应导致其他模块大规模修改。
2.  **可迁移（Portability）**：不绑定某个模型供应商、Harness、操作系统、硬件或设备生态。
3.  **可替换（Replaceability）**：模型、Harness、插件、交互入口和外部系统都允许升级或替换。
4.  **故障隔离与优雅降级（Graceful
    Degradation）**：单个插件或外部服务不可用，不应拖垮整个
    JARVIS；能力可以独立失效和恢复。

核心原则：**JARVIS 应该拥有体验，而不是拥有基础设施。**

优先使用成熟生态提供的模型、Agent
Runtime、语音和设备接入能力；自己掌握稳定的核心契约、身份与上下文、权限规则，以及让不同组件协同工作的整体体验。只有现有方案无法满足真实需求时，才考虑自研基础设施。

## 当前架构概念

``` text
交互层
  文字 / 语音 / 手机 / 桌面 / 屏幕
        │
        ▼
Agent Runtime
  Harness / 模型 / 工具调度 / 会话管理
        │
        ▼
JARVIS Core Contracts
  Identity & Context / Permissions
  （Memory、Task State 后续按需引入）
        │
        ▼
能力层（插件）
  Home / Web / Screen / Computer / Files / ...
        │
        ▼
外部系统
  Home Assistant / 操作系统 / 互联网 / 设备 / 应用
```

这是长期参考架构，不是当前开发清单。当前只实现最小闭环，不提前建设完整的记忆系统、任务编排框架或通用
Agent 平台。

一句话概括当前实现思路：**Harness 提供 Agent
运行环境，插件提供能力，JARVIS 定义身份、上下文与权限边界。**

## 当前进展（2026-11-27）

-   **Python 基础仓库**：配置系统、Home Assistant 客户端、拓扑映射、21
    个虚拟设备，已对真实 HA 验证；阶段 0 记录为 73 个测试通过。
-   **Harness spike 已通过**：使用 DeepSeek Harness（DSH）验证了 home
    插件；模型能够列出客厅设备、控制灯并读回状态，在 DSH
    桌面应用中跑通。
-   **尚未决定**：最终 Harness（DSH、pi
    或其他）、插件正式放置位置、Python HA client
    如何接入、常驻服务形态、语音入口路线。

详细结果见 [`docs/PHASES.md`](docs/PHASES.md)，架构决策见
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 当前阶段明确不做

-   不自己写 Agent Runtime / Harness；优先采用成熟方案。
-   不自己写语音链路（麦克风、唤醒词、语音识别、合成）；优先复用现有语音生态。
-   不做购买和支付。
-   不做主动式行为；先把用户发起任务的闭环做好。
-   不接真实物理硬件；先用 Home Assistant 虚拟设备验证。
-   不提前建设完整 Memory、通用任务编排或个人操作系统。

## 文档

  -----------------------------------------------------------------------------------------
  文档                                             内容
  ------------------------------------------------ ----------------------------------------
  [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)   长期定位、架构原则、设计决策与技术记录

  [`docs/PHASES.md`](docs/PHASES.md)               阶段计划、验收标准、实测记录

  [`docs/CHECKLIST.md`](docs/CHECKLIST.md)         执行清单

  [`docs/LEARN.md`](docs/LEARN.md)                 学习笔记

  [`docs/VIRTUAL_HOME.md`](docs/VIRTUAL_HOME.md)   虚拟家庭设备清单

  [`docs/research/`](docs/research/)               调研笔记
  -----------------------------------------------------------------------------------------

## 环境要求

  ----------------------------------------------------------------------------------------
  组件              版本              必需              说明
  ----------------- ----------------- ----------------- ----------------------------------
  Python            ≥ 3.11            是                推荐用
                                                        [uv](https://docs.astral.sh/uv/)
                                                        管理

  Docker + Compose  近期版本          是                当前用于运行 Home Assistant

  Git               任意              是                

  一个 Harness（如  ---               运行插件时需要    可使用 API 模型，不要求 GPU
  DSH）                                                 
  ----------------------------------------------------------------------------------------

跨平台目标：Windows / Linux /
macOS。机器相关配置通过环境变量或本地配置文件提供，不提交密钥和私人数据。

> **Docker Desktop 授权提醒**：Docker Desktop
> 对大型企业的商业使用需要付费订阅。若有合规顾虑，可评估 WSL2 中的
> Docker Engine，并遵循所在组织政策。

## 快速开始

### 1. 初始化

``` bash
./scripts/setup.sh          # Windows (PowerShell): .\scripts\setup.ps1
```

### 2. 启动 Home Assistant

``` bash
docker compose up -d
docker compose ps
```

首次启动后打开 `http://localhost:8123` 完成 HA
引导，并将长期访问令牌写入本地 `.env` 的 `JARVIS_HA_TOKEN`。

### 3. 启动 Python 服务

``` bash
uv run uvicorn jarvis.main:app --reload
```

### 4. 验证

``` bash
curl http://localhost:8000/api/health
uv run pytest
uv run ruff check .
```

HA 不可用时，服务应保持可用并报告 `degraded`，而不是整体崩溃。

## 仓库结构

``` text
homeassistant/    HA 配置与 virtual_home.yaml
config/           home_topology.yaml
src/jarvis/       Python 服务
tests/            单元测试与集成测试
evals/            评测集
scripts/          初始化、校验与辅助脚本
docs/             架构、阶段计划与学习笔记
```

home 插件 spike
当前位于仓库外：`D:\dsh-plugins\dsh-plugin-home`；正式放置位置待定。

## 多机器工作流

-   代码与虚拟家庭定义通过 Git 同步。
-   每台机器独立维护 `.env`。
-   数据库与对话历史默认不跨机器同步。
-   Python 依赖由 `uv.lock` 锁定。
-   不将机器专属路径、IP、密钥或令牌硬编码进源码。

## 安全

-   源码不包含密钥、令牌和密码；`.env` 不提交。
-   模型只能调用插件暴露的结构化工具，不能直接获取 HA 地址和令牌。
-   高风险动作必须由代码层权限策略控制并要求确认，不能只依赖 system
    prompt。
-   不提交数据库、日志、缓存、Docker volume 和私人对话数据。

## 许可

个人项目。如需开源，待定。
