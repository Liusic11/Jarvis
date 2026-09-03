#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# 备份 Home Assistant 配置目录（含运行时状态：.storage / 数据库等不可复现部分）。
#
# HA 配置以绑定挂载方式位于 homeassistant/config，本脚本直接归档该目录。
# 用途：换机迁移、灾难恢复。纯 YAML 定义的虚拟设备本身由版本库保证可复现，
#       本脚本只用于迁移「运行时状态」（已创建的长期令牌、UI 设置、数据库等）。
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/homeassistant/config"
BACKUP_DIR="${JARVIS_BACKUP_DIR:-$ROOT/backups}"
mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="$BACKUP_DIR/ha-config-$STAMP.tar.gz"

echo "备份 $SRC -> $ARCHIVE"
tar czf "$ARCHIVE" -C "$ROOT/homeassistant" config
echo "完成：$ARCHIVE"
