# 04 — 第一次用自然语言控设备（harness 路线）

> 日期：2026-11-27
> 对应阶段：`docs/PHASES.md` 阶段 1

---

## 1. 这次做了啥

给 DeepSeek Harness（DSH）写了一个 **home 插件**，约 190 行代码。装上之后，对它说「把客厅灯打开」，灯真的亮了；说「我好热」，它先问你怎么办，再把空调调好、查一遍实际状态才回复。

同时项目的方向改了：**不再自己写「脑子」，改用现成的 harness**。JARVIS 的价值在手脚（插件）和对家的理解（身份）上。用一句话说原则：JARVIS 该拥有的是体验，不是基础设施。

---

## 2. 为什么这样搭

**原来的计划**是自己写一整套：工具层、规则路由、Agent 循环、网页界面、记忆库。那套方案的前提是「只能用 CPU 跑小模型，模型不可靠，所以要用规则兜底」。

**前提变了**：

- 可以先用 API 模型，tool calling 很可靠，不需要规则兜底
- 开源的 harness 已经把「对话循环、调工具、管会话」做得很好
- 在物理意义上的家完成之前，用什么模型都一样，也不涉及隐私

**所以新架构分三层**：

| 层 | 是什么 | 换掉它时 |
|---|---|---|
| Harness | 脑子，可替换（DSH、pi 都行） | 插件和身份原样搬走 |
| 插件 | 手脚，每个场景一个 | 加能力不改脑子 |
| System prompt | 身份：是谁、家什么样、主人的习惯 | 改一段话，不改代码 |

---

## 3. 这是什么 / 能做什么 / 不能做什么

**home 插件**给模型提供了三个工具：

| 工具 | 干什么 | 类比 |
|---|---|---|
| `home_list_entities` | 列出家里的设备 | 翻一眼设备清单 |
| `home_get_state` | 查某个设备现在的状态 | 看一眼灯是亮是灭 |
| `home_call_service` | 让设备做事（开、关、调亮度…） | 按开关 |

**能做的**：控制 Home Assistant 里的任何设备，包括将来的真设备。插件不认识「客厅灯」这个词，它每次都先问 HA「家里有什么」，所以换设备不用改代码。

**不能做的**：
- 不是常驻服务。命令行模式下，一个进程只跑一个任务就退出
- 没有身份。现在是个「能控设备的助手」，还不会像管家那样了解你
- 没有权限控制。插件什么服务都放行，说「解锁前门」它会直接开，不会先问你
- 只会控设备。搜索、往屏幕上投东西，要等后面的插件

---

## 4. 你自己怎么动手

**在 DSH 桌面应用里**（插件已经装好）：

1. 重启 DSH 应用
2. 直接说「把客厅灯打开」「家里有哪些灯」「我有点热」
3. 想看它调了哪些工具，点消息上方的步骤展开

**在命令行里**（PowerShell）：

```powershell
# 从 .env 读出 HA 令牌，放进当前窗口的环境变量（不会打印出来）
$line = Get-Content "D:\Desktop\Jarvis\.env" | Where-Object { $_ -match '^JARVIS_HA_TOKEN=' } | Select-Object -First 1
$env:JARVIS_HA_TOKEN = $line.Substring('JARVIS_HA_TOKEN='.Length).Trim().Trim('"').Trim("'")

# 换到一个空目录再跑，免得模型顺手改了你的文件
cd $env:TEMP\dsh-spike-cwd

# --profile / --patch / --json 必须写在任务前面
& "D:\DSH\resources\runtime\cli\bin\dsh.cmd" --profile headless --patch overlay.yml "把客厅灯打开"
```

`overlay.yml` 是让命令行模式用上你在应用里绑好的 API key 的开关，内容只有三行：

```yaml
- id: credentials
  disabled: false
```

**插件代码在哪**：`D:\dsh-plugins\dsh-plugin-home\lib\index.js`。想加一个工具，照着 `getState` 的样子复制一份，改名字、参数和要做的事。

---

## 5. 踩过的坑

| 坑 | 现象 | 怎么解决 |
|---|---|---|
| 命令行参数顺序 | `--json` 写在任务后面，报 `unknown option` | 所有开关都放在任务文本前面 |
| 应用里装的插件不生效 | `dsh-plugin-nlbi` 装了但模型看不到 | 应用的插件管理器只把包写进 `dependencies`，没写进 `bundles`。手动在 `package.json` 的 `bundles` 里加一行 |
| 桌面应用拿不到令牌 | 插件在命令行能用，在应用里报找不到令牌 | 给插件加了 `envFile` 配置，直接从 `D:\Desktop\Jarvis\.env` 读 |
| 虚拟灯带亮度不亮 | 关着的灯说「调到 40%」，只改了亮度，灯还是灭的 | 是 Home Assistant 模板灯的行为，不是插件的错。还没修，先不带亮度开灯 |
| 命令行模式没有 API key | 报凭据缺失 | 命令行模式默认关掉了本地凭据，用上面的 `overlay.yml` 打开 |
| PowerShell 读不到输出 | 用 `??` 语法报错 | 当前是 PowerShell 5，不支持 `??`，换成 `if` 判断 |

---

## 6. 当前状态 / 下一步

**已完成**：DSH 插件控设备，命令行和桌面应用都跑通。

**还没定**：
- 最终用哪个 harness。DSH 试通了，pi 等备选还没评估
- 插件代码放在哪。现在在仓库外面
- 音箱走哪条路

**下一步**（见 `docs/CHECKLIST.md`）：定 harness → 写身份、上下文和权限 → 插件正式化 → 10 句话验收。
