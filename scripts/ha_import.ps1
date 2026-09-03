# ─────────────────────────────────────────────────────────────
# ha_import.ps1 —— Windows 原生 PowerShell 版
# 从归档恢复 Home Assistant 配置目录（会覆盖现有文件！）。
# 用法：.\scripts\ha_import.ps1 ha-config-20260903-120000.tar.gz
# ─────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

$ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BACKUP_DIR = if ($env:JARVIS_BACKUP_DIR) { $env:JARVIS_BACKUP_DIR } else { Join-Path $ROOT "backups" }

$ARCHIVE = $args[0]
if (-not $ARCHIVE) {
  Write-Host "用法: .\scripts\ha_import.ps1 <ha-config-*.tar.gz>" -ForegroundColor Red
  Write-Host "可用归档:" -ForegroundColor Yellow
  Get-ChildItem $BACKUP_DIR -Filter "ha-config-*.tar.gz" | Select-Object Name
  exit 1
}
if (-not (Test-Path $ARCHIVE)) { $ARCHIVE = Join-Path $BACKUP_DIR $ARCHIVE }
if (-not (Test-Path $ARCHIVE)) { Write-Host "找不到归档: $ARCHIVE" -ForegroundColor Red; exit 1 }

Write-Host "从 $ARCHIVE 恢复 -> $ROOT/homeassistant/config（将覆盖现有文件）"
tar.exe xzf $ARCHIVE -C $ROOT/homeassistant
Write-Host "完成。重启 HA 以生效：docker compose restart homeassistant" -ForegroundColor Green
