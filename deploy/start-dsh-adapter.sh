#!/usr/bin/env bash
# 一键启动 butler-dsh-adapter（连接器 + 自动拉起 DSH 宿主 shim）。
#
# 用法：
#   bash deploy/start-dsh-adapter.sh -config integration/connector.json [连接器参数...]
#
# 查找顺序（找到即用）：
#   1. lib_external/dsh-connector/butler-dsh-connector   （install 脚本产物）
#   2. connector/bin/butler-dsh-connector                （源码 go build 产物）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

die() { printf '[dsh-adapter] 错误: %s\n' "$*" >&2; exit 1; }

CONFIG=""
PASSTHROUGH=()
while [ $# -gt 0 ]; do
  case "$1" in
    -config) CONFIG="${2:?-config 需要参数}"; shift 2 ;;
    *)       PASSTHROUGH+=("$1"); shift ;;
  esac
done

BIN=""
for candidate in \
  "${ROOT}/lib_external/dsh-connector/butler-dsh-connector" \
  "${ROOT}/connector/bin/butler-dsh-connector"; do
  if [ -x "$candidate" ]; then BIN="$candidate"; break; fi
done
[ -n "$BIN" ] || die "未找到连接器可执行文件。先运行: bash deploy/install-dsh-adapter.sh（或 go build）"

# Node.js 运行时检查（宿主 shim 必需）
command -v node >/dev/null 2>&1 || die "未找到 Node.js（>= 20），DSH 宿主 shim 无法启动"
MAJOR="$(node -e 'console.log(process.versions.node.split(".")[0])')"
[ "$MAJOR" -ge 20 ] || die "Node.js 版本过低（$(node --version)），需要 >= 20"

if [ -n "$CONFIG" ]; then
  [ -f "$CONFIG" ] || die "配置文件不存在: $CONFIG"
  set -- -config "$CONFIG" "${PASSTHROUGH[@]+"${PASSTHROUGH[@]}"}"
else
  set -- "${PASSTHROUGH[@]+"${PASSTHROUGH[@]}"}"
fi

printf '[dsh-adapter] 启动连接器: %s\n' "$BIN"
exec "$BIN" "$@"
