# 01 · Phase 1 — 仓库骨架与配置基础设施

> 🔰 读这篇前若对 Docker / HTTP / API / FastAPI / 环境变量 还模糊，先读 [`learn/00-foundations.md`](00-foundations.md)（技术通识）。本篇只讲「这些技术在本项目里落地成了哪些文件」。
> 对应提交：`1267388`（已提交）。本阶段目标是把"可复现的地基"打好：项目怎么组织、配置从哪来、应用怎么起来、测试怎么跑。

---

## 这次做了啥（结论）

把 JARVIS 项目的地基一次性打好了，并且**可跨机器复现、可测试**：

- 仓库骨架（目录结构、`pyproject.toml`、`uv.lock`、`.gitignore`）
- 配置系统（`src/jarvis/config.py`，所有设置走环境变量，源码零硬编码）
- 日志 + 应用入口（`logging.py`、`main.py` + `/api/health` 健康检查）
- LLM 抽象 + Stub 替身（`llm/base.py` 协议、`llm/stub_provider.py`）
- HA 客户端骨架（`ha/client.py` 协议 + 错误类型）
- Home Assistant 的 Docker 配置（`docker-compose.yml`，端口 8123）
- 22 个测试全绿

**一句话**：地基已通，HA 能起来，应用能启动，但还没真正"连上"——对话控制设备要等到后面阶段。

---

## 为什么这样搭（关键决策）

| 决策                                            | 理由（大白话）                                                             |
| ----------------------------------------------- | -------------------------------------------------------------------------- |
| **配置全走环境变量**，加 `JARVIS_` 前缀 | 换机器只改 `.env`，不碰代码。前缀避免和你系统里其它变量撞名。            |
| **LLM 抽象在 Phase 1 就位 + Stub 替身**   | 没有真模型也能把整条链路测通，否则后面 7 个阶段都没法验证。                |
| **HA 客户端先用"协议 + 骨架"**            | 先定好"对外出口长什么样"，后面填实现，测试不依赖真 HA 容器。               |
| **Docker 只装 HA，代码本机跑**            | Windows 容器里热重载慢、难调试；HA 跑容器里最省事。                        |
| **无 GPU 机器不装 Ollama，用 Stub**       | 开发专注确定性逻辑；真模型只在带 GPU 的机器验证。                          |
| **`uv` 管理依赖**                       | 比 pip 快、可锁定版本（`uv.lock`），同时导出 `requirements.txt` 兜底。 |

---

## 这是什么 / 能做什么 / 不能做什么

### `config.py`（配置系统）

- **是什么**：一个读取环境变量的模块，把"HA 地址、LLM 类型、端口…"集中管理。
- **能做什么**：启动时一次性加载、校验配置；字段缺失或非法会报错而不是悄悄用错值。
- **不能做什么**：它不是"存密钥的安全箱"。密钥仍由你放进 `.env`，它只负责读。

### `main.py` + `/api/health`（健康检查）

- **是什么**：FastAPI 应用入口，提供一个"我活着吗"的接口。
- **能做什么**：`curl http://localhost:8000/api/health` 返回 JSON（含 HA 连接状态）。HA 没起来时它**不会崩**，只报告 `disconnected`。
- **不能做什么**：它现在不处理任何"对话"或"控制设备"——那是以后的事。

### `llm/stub_provider.py`（Stub 模型）

- **是什么**：一个"假装的大模型"，行为确定、可预测。
- **能做什么**：让链路在没有真模型时也能跑测试、验证逻辑。
- **不能做什么**：它听不懂人话，只会按预设返回固定结果。

### `docker-compose.yml`（HA 容器）

- **是什么**：一条命令拉起 Home Assistant 的配置。
- **能做什么**：`docker compose up -d` 后，HA 跑在 `http://localhost:8123`，状态 `healthy`。
- **不能做什么**：它只负责"把 HA 跑起来"，不负责"把 JARVIS 应用连上去"。

---

## 你自己怎么动手（复现 / 改动）

> 你不需要从零写这些。以下命令我会解释在干什么，需要时改的是配置不是代码。

```bash
# 1) 装 Python 依赖（装进隔离环境，不污染系统）
uv sync

# 2) 起 Home Assistant 容器（后台运行）
docker compose up -d

# 3) 看容器状态，等到 Status 出现 healthy
docker compose ps

# 4) 起 JARVIS 应用（监听 8000 端口，改代码自动重启）
uv run uvicorn jarvis.main:app --reload

# 5) 探活：返回 JSON 即成功
curl http://localhost:8000/api/health

# 6) 跑测试（22 个应该全绿）
uv run pytest
```

**如果要改配置**：编辑项目根目录的 `.env`（从 `.env.example` 复制而来），例如把 `JARVIS_LLM_PROVIDER` 从 `stub` 改成 `ollama`。**不要去改 `config.py` 里的默认值来适配某台机器**——那是反模式。

---

## 踩过的坑（真实记录）

1. **`uv` 没装**：在受管 venv 里用 `pip install uv` 解决，没动你系统环境。
2. **Docker Desktop 守护进程经常掉线**：所有 Docker 命令都要先确认守护进程在，否则报"无法连接"。属 Windows + WSL2 常态，重启 Docker Desktop 即可。
3. **HA 首次启动慢（1–3 分钟）**：别以为挂了，看 `docker compose ps` 的 healthy 状态为准。

---

## 当前状态 / 下一步

- ✅ Phase 1 已提交，22 测试全绿，`/api/health` 实测 200。
- ➡️ 下一步是 **Phase 2（虚拟家庭）**——在 HA 里用 YAML "造"出一整套可复现的虚拟设备（见 `02-phase2-virtual-home.md`）。
