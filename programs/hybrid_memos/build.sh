#!/bin/bash
# 备忘录 Go 后端构建脚本

set -e

# 进入脚本所在目录
cd "$(dirname "$0")"

echo "正在构建备忘录 Go 后端..."
if ! command -v go &> /dev/null; then
    echo "错误：未安装 Go。"
    exit 1
fi

# 整理依赖并构建
go mod tidy
go build -o memos_service memos_service.go

echo "构建完成：$(pwd)/memos_service"
