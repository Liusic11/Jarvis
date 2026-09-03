#!/usr/bin/env bash
# 新机器初始化：装依赖、生成 .env、建好数据目录。
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "未检测到 uv，请先安装："
  echo "  Windows : winget install astral-sh.uv"
  echo "  macOS   : brew install uv"
  echo "  Linux   : curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

echo "==> 安装依赖"
uv sync

if [ ! -f .env ]; then
  echo "==> 生成 .env（记得填入 Home Assistant 令牌）"
  cp .env.example .env
else
  echo "==> .env 已存在，跳过"
fi

echo "==> 创建数据目录"
mkdir -p data homeassistant/config

echo ""
echo "完成。后续步骤："
echo "  1. docker compose up -d                   启动 Home Assistant"
echo "  2. 打开 http://localhost:8123 完成首次引导，创建长期访问令牌"
echo "  3. 把令牌填入 .env 的 JARVIS_HA_TOKEN"
echo "  4. uv run uvicorn jarvis.main:app --reload"
