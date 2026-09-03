# 02 · Phase 2 — Home Assistant 与可复现虚拟家庭

> 🔰 读这篇前若对 Docker / YAML / Home Assistant / HTTP 还模糊，先读 [`learn/00-foundations.md`](00-foundations.md)（技术通识），第 6 课专讲 HA、第 10 课有完整串讲。
> 对应状态：**已落盘，未提交**（git status 显示 `homeassistant/config/packages/`、`docs/VIRTUAL_HOME.md`、export/import 脚本均为未跟踪；`configuration.yaml`、`docker-compose.yml`、`.gitignore` 有修改）。本阶段目标：用纯 YAML 定义整套虚拟家庭，fresh clone 就能重建，不用在 HA 界面里手动建任何设备。

---

## 这次做了啥（结论）

在跑着的 Home Assistant 里，"造"出了一整套**虚拟智能家居**，共 **21 个设备实体**，全部由 YAML 定义、可提交、可复现：

- 4 盏灯（客厅/卧室/书房/厨房）
- 3 台空调（客厅/卧室/书房）
- 2 道窗帘（客厅/卧室）
- 1 台电视（客厅）
- 1 把大门门锁（玄关，高危）
- 1 台扫地机器人（全屋）
- 4 个温度传感器 + 5 个有人传感器

**一句话**：现在 HA 里有一个"假的但结构完整"的家，将来把 YAML 里的虚拟设备换成真设备，上层 JARVIS 代码一行都不用改。

---

## 为什么用 YAML "造"设备，而不是真硬件 / UI 手建

| 方案 | 为什么不选 |
|---|---|
| 买真智能灯/真空调 | 你明确 1–2 年内不接真硬件；成本、配对、稳定性都拖慢验证。 |
| 在 HA 网页里手动点出来 | 手动建的实体存在 HA 自己的 `.storage/` 里，**不进 Git**，别人 clone 你的仓库拿不到，无法复现。 |
| **纯 YAML + template 派生** ✅ | 配置即代码，可提交、可 review、fresh clone 一键重建，零 UI 操作。 |

这是整个项目"可复现"理念的核心体现（见 `ARCHITECTURE.md` D1）。

---

## 这是什么 / 能做什么 / 不能做什么

### Home Assistant（HA）
- **是什么**：开源智能家居中枢，管"家里有什么设备、它们状态如何"。我们让它管虚拟家庭。
- **能做什么**：持有所有设备实体、提供 REST/WebSocket 接口让你查询和控制、跑自动化。
- **不能做什么**：它不会"听懂人话"——那是 JARVIS / LLM 的活。HA 只认标准指令（`开灯`、`设温度`）。

### template 实体（造虚拟设备的核心机制）
- **是什么**：HA 的一种"用公式从别的实体派生新实体"的配置写法。
- **能做什么**：我们用 `input_boolean`（开关）、`input_number`（数值）、`input_select`（选项）当"状态底板"，再用 `template:` 把它们包装成**真 domain 实体**（light / cover / lock / vacuum / sensor / binary_sensor / switch）。
- **不能做什么**：`template:` 平台**不支持 `climate`（空调）和 `media_player`（电视电源）**。空调改用 `generic_thermostat`（见下），电视电源用 `template switch` 顶上。

### 虚拟设备 vs 真设备
- **能做什么**：在"控制链路"上和真设备一模一样——JARVIS 调 `light.turn_on`，HA 执行，状态变化。
- **不能做什么**：灯不会真亮、空调不会真制冷。它验证的是**软件链路**，不是物理世界。

---

## 实体清单（21 个，全部已注册成功）

| 房间 | 设备 | domain / entity_id | 状态载体 |
|---|---|---|---|
| 客厅 | 灯 | `light.living_room_light` | input_boolean.lr_light + input_number.lr_light_bri |
| 卧室 | 灯 | `light.bedroom_light` | br_light + br_light_bri |
| 书房 | 灯 | `light.study_light` | st_light + st_light_bri |
| 厨房 | 灯 | `light.kitchen_light` | kt_light + kt_light_bri |
| 客厅 | 空调 | `climate.living_room_ac` | generic_thermostat（用 lr_ac 作电源） |
| 卧室 | 空调 | `climate.bedroom_ac` | generic_thermostat（br_ac） |
| 书房 | 空调 | `climate.study_ac` | generic_thermostat（st_ac） |
| 客厅 | 窗帘 | `cover.living_room_curtain` | input_boolean.lr_curtain |
| 卧室 | 窗帘 | `cover.bedroom_curtain` | input_boolean.br_curtain |
| 客厅 | 电视 | `switch.living_room_tv` | input_boolean.lr_tv |
| 玄关 | 大门门锁 | `lock.front_door` | input_boolean.en_lock（off=上锁） |
| 全屋 | 扫地机器人 | `vacuum.robot_vacuum` | input_select.vacuum_state |
| 客厅/卧室/书房/厨房 | 温度传感器 | `sensor.*_temperature` | input_number.*_temp_cur |
| 客厅/卧室/书房/厨房/门口 | 有人传感器 | `binary_sensor.*_presence` | input_boolean.*_presence |

> 完整定义见 `homeassistant/config/packages/virtual_home.yaml`，设备清单文档见 `docs/VIRTUAL_HOME.md`。

---

## 你自己怎么动手（加一个新设备为例）

假设你要加一个"卫生间灯"：

1. **开 `homeassistant/config/packages/virtual_home.yaml`**。
2. **加状态底板**：在 `input_boolean:` 下加一行 `wc_light: { name: "卫生间灯", initial: off }`；若要亮度，在 `input_number:` 下加 `wc_light_bri: {...}`。
3. **加派生实体**：在 `template:` 的 `light:` 列表里加一项，照着客厅灯的写法改名字和 `unique_id`（用 `jarvis_light_wc` 这种前缀避免冲突）。
4. **保存** → HA 会自动重载 packages（或 `docker compose restart`）。
5. **验证**：`curl -H "Authorization: Bearer $JARVIS_HA_TOKEN" http://localhost:8123/api/states | grep wc_light` 看到新实体即成功。

> ⚠️ 记住铁律：**禁止在 HA 网页里手动创建实体**。一切走 YAML，才能复现。

---

## 踩过的坑（真实记录，重点）

1. **命名卷读不到 YAML（最大坑）**：最初 `docker-compose.yml` 用 `ha-config:/config` 命名卷，结果 HA 容器里是空配置——YAML 在宿主机但卷是空的。改成 **bind mount** `./homeassistant/config:/config`，让宿主机目录直接挂进去。这推翻了 `ARCHITECTURE.md` D7 的"named volume"决策（已在 `LEARN.md` 第 8 节登记，待改正文档）。
2. **template 语法**：亮度字段要用 `level:`（不是 `brightness:`）；`template:` 平台不支持 `climate` / `media_player`，分别改用 `generic_thermostat` 和 `template switch`。
3. **HA 2026.9.0 令牌流程变了**（这是当前卡点的根源）：
   - 换 token 的端点不是 `/api/auth/token`，而是 `/auth/token`；
   - `client_id` 不能是随意字符串，必须是 **https URL**（如 `https://jarvis.local/auth`）；
   - 旧版的 REST 长期令牌（LLAT）端点已**移除**，只能用 **WebSocket 命令** `auth/long_lived_access_token` 获取。
4. **路径混乱**：Git Bash 的 `/tmp` 和 Windows 的 `C:/Users/.../AppData/Local/Temp/` 不是一回事，脚本里统一用 Windows Temp 路径。

---

## 如何（重新）生成 HA 长期令牌（JARVIS_HA_TOKEN）

> 场景：换机器、令牌过期/泄露、或 `.env` 丢了。这是一次**无浏览器**的取令牌流程（HA 2026.9 专用）。原理见 [`00-foundations.md` 第 9.5 课](00-foundations.md)：先用账号密码走登录流拿**短令牌**，再用短令牌经 **WebSocket 命令**换出**长期令牌（LLAT）**，写进 `.env`。

### 步骤（已验证可复现）
1. **确认 owner 账号密码**：HA 里有一个 owner（本项目登录名 `jarvis`）。
   - 若密码忘了：进容器重置 `docker exec jarvis-homeassistant hass -c /config --script auth change_password jarvis <新密码>`。
   - ⚠️ 本项目 2026.9 的 `hass` CLI 读认证库有 bug，可能报 `User not found`。遇此情况，改为删掉 `.storage/auth`、`.storage/auth_provider.homeassistant`、`.storage/onboarding` 三个文件并重启容器，再走下方 onboarding 重建 owner（保留 `core.entity_registry` 等设备注册表）。
2. **登录流拿 auth_code**（必须带 PKCE）：
   - `POST /auth/login_flow` `{client_id:"https://jarvis.local/auth", handler:["homeassistant",null], redirect_uri:"https://jarvis.local/"}` → 取 `flow_id`
   - `POST /auth/login_flow/<flow_id>` `{username:"jarvis", password:"...", client_id:"https://jarvis.local/auth"}` → 返回的 `result` 字段就是 `auth_code`
3. **auth_code 直接当 OAuth 授权码用**（HA 2026.9 的关键技巧）：
   `POST /auth/token` `grant_type=authorization_code` + `code=<auth_code>` + `code_verifier=<PKCE 验证器>` → 返回 `access_token`（短令牌，约 30 分钟有效）。
   ⚠️ **必须带 `code_verifier`**，否则报 `Invalid code`。无需再走 `/auth/authorize` 跳转。
4. **WebSocket 换长期令牌**：连 `ws://127.0.0.1:8123/api/websocket`，先发 `auth` 用短令牌登录，再发 `{"type":"auth/long_lived_access_token","lifespan":3650}` → 返回的 `result` 即为 LLAT（有效期 10 年）。
5. **写进 `.env`**：填到 `JARVIS_HA_TOKEN=...`（`.env` 已被 git 忽略，不会提交）。

### 验证
```bash
TOKEN=$(grep '^JARVIS_HA_TOKEN=' .env | cut -d= -f2-)
curl -sS -H "Authorization: Bearer $TOKEN" http://localhost:8123/api/states \
  | python -c "import sys,json;d=json.load(sys.stdin);print('entities:',len(d))"
# 应看到 62 个实体，其中包含 light.living_room_light 等 21 个虚拟设备
```

> 一键脚本见本地临时文件 `C:/Users/Liusi/AppData/Local/Temp/mint_ha_token.py`（逻辑即上面 5 步，**未进仓库**，因内含 owner 密码；想复现按上面步骤重跑即可）。

---

## 当前状态 / 下一步（关键）

- ✅ 21 个虚拟实体已在 HA 注册，零配置错误。
- ✅ **JARVIS 已连上 HA**：长期令牌（LLAT）已生成并写入 `.env` 的 `JARVIS_HA_TOKEN`（2026-09-03 经你授权后执行）。实测 `GET /api/states` 带该令牌可列出全部 62 个实体，含 21 个虚拟设备——鉴权链路打通。
- 📌 令牌是「长期」的（有效期 10 年），正常情况下无需频繁重造；重造步骤见上节。
- ➡️ Phase 2 可收尾提交，进入 **Phase 3（拓扑配置 `home_topology.yaml` + 真正的 `HomeAssistantClient` 实现 + 规则路由）**。届时 JARVIS 才真正「能控制」设备（开灯/设温/锁门等），而不只是能列状态。
