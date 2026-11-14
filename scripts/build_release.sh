#!/usr/bin/env bash
# 一键构建（可选发布）多架构镜像。
#
# 用法：
#   ./scripts/build_release.sh                 # 仅本地构建当前平台
#   ./scripts/build_release.sh --push          # 构建并推送到 GHCR（需登录）
set -euo pipefail

IMAGE="${IMAGE:-butler}"
TAG="${TAG:-latest}"

push=false
for arg in "$@"; do
  case "$arg" in
    --push) push=true ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "错误：未找到 docker。请先安装 Docker。" >&2
  exit 1
fi

# 确保 buildx 可用（多架构构建需要）
docker buildx version >/dev/null 2>&1 || {
  echo "提示：未检测到 buildx，尝试使用默认 builder。" >&2
}

if [ "$push" = true ]; then
  echo "构建并推送多架构镜像: $IMAGE:$TAG (linux/amd64 + linux/arm64)"
  docker buildx build --platform linux/amd64,linux/arm64 \
    -t "ghcr.io/${IMAGE}:${TAG}" \
    -t "ghcr.io/${IMAGE}:latest" \
    --push .
else
  echo "本地构建镜像: $IMAGE:$TAG"
  docker build -t "$IMAGE:$TAG" .
fi

echo "完成。运行方式（Docker）："
echo "  docker run -d --name butler -p 5001:5001 -p 8000:8000 -p 3000:3000 \\"
echo "    -v \$(pwd)/data:/app/data -v \$(pwd)/config:/app/config \\"
echo "    --env-file .env $IMAGE:$TAG"
