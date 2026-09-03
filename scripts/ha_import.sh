#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# 从归档恢复 Home Assistant 配置目录（会覆盖现有文件！）。
#
# 用法：
#   ./scripts/ha_import.sh <归档文件名或路径>
#   ./scripts/ha_import.sh ha-config-20260903-120000.tar.gz
# 恢复后建议重启 HA：docker compose restart homeassistant
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${JARVIS_BACKUP_DIR:-$ROOT/backups}"

ARCHIVE="${1:-}"
if [ -z "$ARCHIVE" ]; then
  echo "用法: $0 <ha-config-*.tar.gz>" >&2
  echo "可用归档:" >&2
  ls -1 "$BACKUP_DIR" 2>/dev/null >&2 || echo "  (无)" >&2
  exit 1
fi
if [ ! -f "$ARCHIVE" ]; then ARCHIVE="$BACKUP_DIR/$ARCHIVE"; fi
if [ ! -f "$ARCHIVE" ]; then echo "找不到归档: $ARCHIVE" >&2; exit 1; fi

echo "从 $ARCHIVE 恢复 -> $ROOT/homeassistant/config（将覆盖现有文件）"
tar xzf "$ARCHIVE" -C "$ROOT/homeassistant"
echo "完成。重启 HA 以生效：docker compose restart homeassistant"
