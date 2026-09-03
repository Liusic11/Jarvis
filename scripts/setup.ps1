# 新机器初始化（Windows）：装依赖、生成 .env、建好数据目录。
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "未检测到 uv，请先安装："
    Write-Host "  winget install astral-sh.uv"
    exit 1
}

Write-Host "==> 安装依赖"
uv sync

if (-not (Test-Path .env)) {
    Write-Host "==> 生成 .env（记得填入 Home Assistant 令牌）"
    Copy-Item .env.example .env
} else {
    Write-Host "==> .env 已存在，跳过"
}

Write-Host "==> 创建数据目录"
New-Item -ItemType Directory -Force -Path data, homeassistant/config | Out-Null

Write-Host ""
Write-Host "完成。后续步骤："
Write-Host "  1. docker compose up -d                   启动 Home Assistant"
Write-Host "  2. 打开 http://localhost:8123 完成首次引导，创建长期访问令牌"
Write-Host "  3. 把令牌填入 .env 的 JARVIS_HA_TOKEN"
Write-Host "  4. uv run uvicorn jarvis.main:app --reload"
