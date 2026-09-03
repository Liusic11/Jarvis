# JARVIS 虚拟家庭设备清单

本文件描述由 `homeassistant/config/packages/virtual_home.yaml` 定义的全部虚拟设备。
**fresh clone + `docker compose up -d` 即可重建以下所有实体，无需任何 UI 操作。**

## 设计要点

- `input_boolean` / `input_number` / `input_select` 是「状态载体」，是虚拟设备的唯一真相来源，全部为可提交的 YAML 配置。
- `template:` 集成从状态载体派生出真正的设备领域实体（`light` / `climate` / `cover` / `media_player` / `lock` / `vacuum` / `sensor` / `binary_sensor`）。
- 将来换真实设备时，只需在 HA 侧配对真实设备，并把拓扑映射（`config/home_topology.yaml`，Phase 3）改到新 entity_id，本文件整体可丢弃。
- **禁止通过 HA UI 创建任何实体** —— 否则 clone 后无法复现。

## 房间与设备

| 房间 | 设备 | 领域 | entity_id | 状态载体 |
|---|---|---|---|---|
| 客厅 Living Room | 灯 | `light` | `light.living_room_light` | `input_boolean.lr_light` + `input_number.lr_light_bri` |
| 客厅 | 空调 | `climate` | `climate.living_room_ac` | `input_boolean.lr_ac` + `input_number.lr_temp_cur` / `lr_temp_set` |
| 客厅 | 窗帘 | `cover` | `cover.living_room_curtain` | `input_boolean.lr_curtain` |
| 客厅 | 电视 | `media_player` | `media_player.living_room_tv` | `input_boolean.lr_tv` |
| 客厅 | 温度 | `sensor` | `sensor.living_room_temperature` | `input_number.lr_temp_cur` |
| 客厅 | 有人 | `binary_sensor` | `binary_sensor.living_room_presence` | `input_boolean.lr_presence` |
| 卧室 Bedroom | 灯 | `light` | `light.bedroom_light` | `input_boolean.br_light` + `input_number.br_light_bri` |
| 卧室 | 空调 | `climate` | `climate.bedroom_ac` | `input_boolean.br_ac` + `input_number.br_temp_cur` / `br_temp_set` |
| 卧室 | 窗帘 | `cover` | `cover.bedroom_curtain` | `input_boolean.br_curtain` |
| 卧室 | 温度 | `sensor` | `sensor.bedroom_temperature` | `input_number.br_temp_cur` |
| 卧室 | 有人 | `binary_sensor` | `binary_sensor.bedroom_presence` | `input_boolean.br_presence` |
| 书房 Study | 灯 | `light` | `light.study_light` | `input_boolean.st_light` + `input_number.st_light_bri` |
| 书房 | 空调 | `climate` | `climate.study_ac` | `input_boolean.st_ac` + `input_number.st_temp_cur` / `st_temp_set` |
| 书房 | 温度 | `sensor` | `sensor.study_temperature` | `input_number.st_temp_cur` |
| 书房 | 有人 | `binary_sensor` | `binary_sensor.study_presence` | `input_boolean.st_presence` |
| 厨房 Kitchen | 灯 | `light` | `light.kitchen_light` | `input_boolean.kt_light` + `input_number.kt_light_bri` |
| 厨房 | 温度 | `sensor` | `sensor.kitchen_temperature` | `input_number.kt_temp_cur` |
| 厨房 | 有人 | `binary_sensor` | `binary_sensor.kitchen_presence` | `input_boolean.kt_presence` |
| 玄关 Entrance | 大门门锁 | `lock` | `lock.front_door` | `input_boolean.en_lock`（off = 上锁） |
| 玄关 | 有人 | `binary_sensor` | `binary_sensor.entrance_presence` | `input_boolean.en_presence` |
| 全屋 Home | 扫地机器人 | `vacuum` | `vacuum.robot_vacuum` | `input_select.vacuum_state`（docked / idle / cleaning） |

## 语义约定

- 亮度以 `0–100%` 存储于 `input_number`，模板内换算成 HA 内部 `0–255`；工具层统一使用百分比。
- 门锁：`input_boolean` 为 `off` 表示「已上锁（locked）」，`on` 表示「已解锁（unlocked）」。
- 空调 `hvac_mode`：用 `input_boolean` 的 on/off 表达「运行 / 关闭」，`cool` 为默认运行模式。
- 扫地机状态由 `input_select.vacuum_state` 承载，映射到 `vacuum` 的 `docked` / `idle` / `cleaning`。

## 与拓扑层的关系（Phase 3）

JARVIS 的 Agent / Tools 只认识逻辑语义（如「客厅 + 灯」），由 `config/home_topology.yaml` 翻译成上面的 `entity_id`。换真实设备时，改这一层 YAML 即可，Agent 与 Tools 代码一行不动。
