#!/usr/bin/env bash
# ==========================================
# Butler PC 快速启动
#
# 用法:
#   ./scripts/start_pc.sh           # 启动 Butler
#   ./scripts/start_pc.sh --dev     # 开发模式 (热重载前端)
# ==========================================

set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$ROOT"

MODE="${1:-}"

echo "=========================================="
echo " Butler PC 启动"
echo "=========================================="

# 检查 Python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ Python 未安装"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)

# 检查依赖
echo "🔍 检查依赖..."
$PYTHON -c "import requests" 2>/dev/null || {
    echo "📦 安装核心依赖..."
    $PYTHON -m pip install -r requirements.txt -q
}

if [ "$MODE" = "--dev" ]; then
    echo ""
    echo "🔧 开发模式: 启动前端开发服务器 + Butler"
    echo "   前端: http://localhost:3000"
    echo ""

    # 后台启动前端
    if [ -d "$ROOT/frontend" ] && command -v npm &> /dev/null; then
        cd "$ROOT/frontend"
        npm run dev &
        FRONTEND_PID=$!
        cd "$ROOT"
    fi

    # 启动 Butler
    $PYTHON -m butler.butler_app

    # 清理
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
    fi
else
    echo ""
    echo "🚀 启动 Butler..."
    $PYTHON -m butler.butler_app
fi
