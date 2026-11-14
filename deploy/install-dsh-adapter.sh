#!/usr/bin/env bash
# butler-dsh-adapter 安装脚本：从 GitHub Releases 拉取预编译产物到 lib_external/。
#
# 对齐 Butler 便携模式：产物隔离在 --prefix 下，删目录即卸载；仓库零二进制。
#
# 用法：
#   bash deploy/install-dsh-adapter.sh [选项]
#
# 选项：
#   --version <tag>     版本 tag（默认 latest，即 GitHub 最新 Release）
#   --prefix <dir>      安装根目录（默认 ./lib_external）
#   --repo <owner/repo> 仓库（默认 HelloEveryboby/Butler）
#   --base-url <url>    自定义下载基址（镜像/测试用；亦可用 BUTLER_DSH_BASE_URL 环境变量）
#   --from-source       不下载预编译产物，本地源码编译（要求 go + node/npm）
#   --skip-node-check   跳过 Node.js 版本检查
#   -h, --help          显示帮助
#
# 环境变量：
#   BUTLER_DSH_BASE_URL  覆盖下载基址（内网镜像/加速代理友好）
#   BUTLER_DSH_REPO      覆盖仓库

set -euo pipefail

REPO="${BUTLER_DSH_REPO:-HelloEveryboby/Butler}"
BASE_URL="${BUTLER_DSH_BASE_URL:-}"
VERSION="latest"
PREFIX="./lib_external"
FROM_SOURCE=0
SKIP_NODE_CHECK=0

log()  { printf '[dsh-adapter] %s\n' "$*"; }
die()  { printf '[dsh-adapter] 错误: %s\n' "$*" >&2; exit 1; }

usage() { sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --version)         VERSION="${2:?--version 需要参数}"; shift 2 ;;
    --prefix)          PREFIX="${2:?--prefix 需要参数}"; shift 2 ;;
    --repo)            REPO="${2:?--repo 需要参数}"; shift 2 ;;
    --base-url)        BASE_URL="${2:?--base-url 需要参数}"; shift 2 ;;
    --from-source)     FROM_SOURCE=1; shift ;;
    --skip-node-check) SKIP_NODE_CHECK=1; shift ;;
    -h|--help)         usage; exit 0 ;;
    *)                 die "未知参数: $1（--help 查看用法）" ;;
  esac
done

# ---- 平台探测 ----
detect_platform() {
  local os arch
  case "$(uname -s)" in
    Linux)  os="linux" ;;
    Darwin) os="darwin" ;;
    *)      die "不支持的操作系统: $(uname -s)（Windows 请用 install-dsh-adapter.ps1）" ;;
  esac
  case "$(uname -m)" in
    x86_64|amd64)  arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *)             die "不支持的 CPU 架构: $(uname -m)" ;;
  esac
  echo "${os}-${arch}"
}

# ---- Node.js 运行时检查（shim 运行必需，连接器本身零依赖） ----
check_node() {
  [ "$SKIP_NODE_CHECK" = 1 ] && return 0
  if ! command -v node >/dev/null 2>&1; then
    die "未找到 Node.js。DSH 宿主 shim 需要 Node.js >= 20，请先安装（https://nodejs.org）"
  fi
  local major
  major="$(node -e 'console.log(process.versions.node.split(".")[0])')"
  if [ "$major" -lt 20 ]; then
    die "Node.js 版本过低（$(node --version)），需要 >= 20"
  fi
  log "Node.js $(node --version) ✓"
}

# ---- 校验和验证：优先 sha256sum，macOS 退到 shasum ----
verify_sha256() {
  local file="$1" sums="$2"
  if command -v sha256sum >/dev/null 2>&1; then
    (cd "$(dirname "$file")" && grep "$(basename "$file")" "$sums" | sha256sum -c -) \
      || die "校验和不匹配: $file"
  elif command -v shasum >/dev/null 2>&1; then
    (cd "$(dirname "$file")" && grep "$(basename "$file")" "$sums" | shasum -a 256 -c -) \
      || die "校验和不匹配: $file"
  else
    log "警告: 未找到 sha256sum/shasum，跳过校验"
  fi
}

download() {
  local url="$1" out="$2"
  log "下载 $url"
  curl -fsSL --retry 3 --retry-delay 2 -o "$out" "$url" \
    || die "下载失败: $url（网络问题可设 BUTLER_DSH_BASE_URL 走镜像）"
}

# ---- 从 Releases 安装 ----
install_from_release() {
  local plat sums_url
  plat="$(detect_platform)"
  # tmp 必须是全局量：EXIT trap 在函数返回后才执行，局部变量已出栈（set -u 下会炸）
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT

  if [ "$VERSION" = "latest" ]; then
    # 解析最新 Release tag（GitHub API；镜像场景请显式指定 --version）
    VERSION="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
      | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)"
    [ -n "$VERSION" ] || die "无法解析最新 Release，请显式指定 --version"
    log "最新版本: $VERSION"
  fi

  if [ -z "$BASE_URL" ]; then
    BASE_URL="https://github.com/${REPO}/releases/download/${VERSION}"
  fi

  local conn_pkg="butler-dsh-connector_${VERSION}_${plat}.tar.gz"
  local host_pkg="butler-dsh-host_${VERSION}.tar.gz"

  sums_url="${BASE_URL}/SHA256SUMS"
  download "$sums_url" "$tmp/SHA256SUMS"
  download "${BASE_URL}/${conn_pkg}" "$tmp/${conn_pkg}"
  download "${BASE_URL}/${host_pkg}" "$tmp/${host_pkg}"

  verify_sha256 "$tmp/${conn_pkg}" "$tmp/SHA256SUMS"
  verify_sha256 "$tmp/${host_pkg}" "$tmp/SHA256SUMS"

  mkdir -p "${PREFIX}/dsh-connector" "${PREFIX}/dsh-host"
  tar -xzf "$tmp/${conn_pkg}" -C "${PREFIX}/dsh-connector"
  tar -xzf "$tmp/${host_pkg}" -C "${PREFIX}/dsh-host"
  chmod +x "${PREFIX}/dsh-connector/butler-dsh-connector" 2>/dev/null || true

  printf '%s\n' "$VERSION" > "${PREFIX}/dsh-connector/VERSION"
  log "安装完成 → ${PREFIX}/dsh-connector/  ${PREFIX}/dsh-host/"
}

# ---- 源码编译安装（开发/无网 Releases 场景） ----
install_from_source() {
  local root
  root="$(cd "$(dirname "$0")/.." && pwd)"

  command -v go >/dev/null 2>&1  || die "--from-source 需要 Go 工具链（https://go.dev）"
  command -v npm >/dev/null 2>&1 || die "--from-source 需要 Node.js/npm"

  log "编译连接器（Go）..."
  (cd "${root}/connector" && CGO_ENABLED=0 go build -trimpath \
    -ldflags "-s -w -X main.version=source" \
    -o "${root}/${PREFIX}/dsh-connector/butler-dsh-connector" ./cmd/dsh-connector)

  log "构建 DSH 宿主 shim（npm）..."
  (cd "${root}/dsh-host" && npm ci --silent && npm run build)
  mkdir -p "${root}/${PREFIX}/dsh-host"
  cp -r "${root}/dsh-host/dist" "${root}/dsh-host/package.json" "${root}/${PREFIX}/dsh-host/"

  printf 'source\n' > "${root}/${PREFIX}/dsh-connector/VERSION"
  log "源码构建完成 → ${PREFIX}/"
}

# ---- main ----
check_node
mkdir -p "$PREFIX"
if [ "$FROM_SOURCE" = 1 ]; then
  install_from_source
else
  install_from_release
fi

cat <<EOF

[dsh-adapter] ✅ 安装完成。下一步：
  1. 配置连接器（可参考 connector/README.md 的配置示例）:
       ${PREFIX}/dsh-connector/butler-dsh-connector -config <connector.json>
  2. 或用一键启动:
       bash deploy/start-dsh-adapter.sh -config <connector.json>
  3. 卸载 = 删除目录: rm -rf ${PREFIX}/dsh-connector ${PREFIX}/dsh-host
EOF
