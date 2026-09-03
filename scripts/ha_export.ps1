# ─────────────────────────────────────────────────────────────
# ha_export.ps1 —— Windows 原生 PowerShell 版
# 备份 Home Assistant 配置目录到本地归档。
# 用法：.\scripts\ha_export.ps1
# ─────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

$ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SRC = Join-Path $ROOT "homeassistant/config"
$BACKUP_DIR = if ($env:JARVIS_BACKUP_DIR) { $env:JARVIS_BACKUP_DIR } else { Join-Path $ROOT "backups" }
New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null

$STAMP = Get-Date -Format "yyyyMMdd-HHmmss"
$ARCHIVE = Join-Path $BACKUP_DIR "ha-config-$STAMP.tar.gz"

Write-Host "备份 $SRC -> $ARCHIVE"
tar.exe czf $ARCHIVE -C $ROOT/homeassistant config
Write-Host "完成：$ARCHIVE"
