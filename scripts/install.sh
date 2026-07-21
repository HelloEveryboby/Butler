#!/bin/bash
# ==============================================================================
# Butler POSIX 自动化一键部署引擎 (Linux / macOS)
# ==============================================================================
# 设计特点:
#   1. 完全静默 & 非交互，避免 pipe 阻塞
#   2. 自包含沙箱设计，支持自定义 $BUTLER_HOME，默认 ~/.local/share/butler
#   3. 使用极速包管理器 uv 自动引导、创建虚拟环境并进行超高速依赖安装
#   4. 自治检测缺失依赖 (git, python3)，提供自动化的本地独立运行降级方案
#   5. 注册 ~/.local/bin/butler 快捷指令，自动净化及刷新 PATH 环境变量
# ==============================================================================

set -eo pipefail

# ANSI 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0;37m' # No Color
BOLD='\033[1m'

# 打印美化日志
log_info() {
    printf "${GREEN}${BOLD}[INFO]${NC} %b\n" "$1"
}
log_warn() {
    printf "${YELLOW}${BOLD}[WARN]${NC} %b\n" "$1"
}
log_error() {
    printf "${RED}${BOLD}[ERROR]${NC} %b\n" "$1"
}
log_step() {
    printf "${CYAN}${BOLD}=== %b ===${NC}\n" "$1"
}

# 1. 路径规划
BUTLER_HOME="${BUTLER_HOME:-$HOME/.local/share/butler}"
BUTLER_BIN="${BUTLER_BIN:-$HOME/.local/bin}"
APP_DIR="$BUTLER_HOME/app"
UV_BIN="$BUTLER_HOME/bin/uv"

log_step "阶段 1: 平台与沙箱路径初始化"
log_info "目标安装目录 (BUTLER_HOME): ${BLUE}${BUTLER_HOME}${NC}"
log_info "目标可执行命令目录 (BUTLER_BIN): ${BLUE}${BUTLER_BIN}${NC}"

mkdir -p "$BUTLER_HOME"
mkdir -p "$BUTLER_BIN"

# 2. 前置依赖自检与静默补足
log_step "阶段 2: 系统基础工具链自检 (Git & Python)"

# 检查 Git
if ! command -v git >/dev/null 2>&1; then
    log_error "系统未检测到 'git'。一键部署需要 git 来克隆和升级 Butler。"
    log_warn "请先安装 git 后重试：\n  - Debian/Ubuntu: sudo apt install -y git\n  - macOS: brew install git"
    exit 1
else
    log_info "Git 校验通过: $(git --version)"
fi

# 检查 Python3
HAS_SYSTEM_PYTHON=true
if ! command -v python3 >/dev/null 2>&1; then
    log_warn "系统未检测到 'python3'。"
    HAS_SYSTEM_PYTHON=false
else
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    log_info "Python3 校验通过, 当前版本: $PYTHON_VERSION"
fi

# 3. 超高速包管理器 uv 引导
log_step "阶段 3: 引导极速 Python 包管理器 (uv)"
if [ ! -f "$UV_BIN" ]; then
    log_info "未检测到本地私有 'uv'，正在静默下载并部署..."
    # 使用官方独立的 shell 安装脚本进行静默隔离安装
    export UV_INSTALL_DIR="$BUTLER_HOME/bin"
    if curl -sSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1; then
        log_info "uv 部署成功: $($UV_BIN --version)"
    else
        log_warn "通过官方 API 引导 uv 失败，尝试使用 Python 自加载备用方案..."
        if [ "$HAS_SYSTEM_PYTHON" = true ]; then
            python3 -m pip install --user uv >/dev/null 2>&1 || true
            if command -v uv >/dev/null 2>&1; then
                mkdir -p "$BUTLER_HOME/bin"
                cp "$(command -v uv)" "$UV_BIN"
                log_info "uv 备用方案部署成功: $($UV_BIN --version)"
            fi
        fi
    fi
else
    log_info "本地私有 'uv' 已存在，跳过引导: $($UV_BIN --version)"
fi

# 如果还是没有 uv，我们后面将退化为使用系统的 python3 -m venv
USE_UV=true
if [ ! -f "$UV_BIN" ]; then
    log_warn "未能成功引导独立 'uv' 引擎，将退化为系统原生 pip/venv 机制运行。"
    USE_UV=false
fi

# 4. 代码库下载与安全更新
log_step "阶段 4: 克隆/同步 Butler 核心代码仓库"
REPO_URL="https://github.com/HelloEveryboby/Butler.git"

if [ -d "$APP_DIR/.git" ]; then
    log_info "检测到已存在的 Butler 目录，正在安全拉取最新变更..."
    cd "$APP_DIR"
    # 强制清理未提交的临时修改，防止 git pull 报错冲突
    git stash -u >/dev/null 2>&1 || true
    if git pull origin main; then
        log_info "Butler 代码更新成功。"
    else
        log_warn "Git 同步遇到波折，保留当前本地版本继续执行安装。"
    fi
else
    log_info "正在静默克隆 Butler 主仓库到沙箱空间..."
    if git clone --depth=1 "$REPO_URL" "$APP_DIR"; then
        log_info "Butler 仓库克隆完成。"
    else
        log_error "克隆 Butler 仓库失败，请检查网络连接。"
        exit 1
    fi
fi

# 5. 构建隔离虚拟环境 & 高速安装依赖
log_step "阶段 5: 构建独立虚拟环境与极速依赖编译"
cd "$APP_DIR"

# 自动注入/选择 Python 解释器
# 如果系统没有 Python，但是有 uv，uv 具备自主拉取 CPython 独立二进制环境的能力
if [ "$USE_UV" = true ]; then
    log_info "正在使用 uv 初始化轻量级独立虚拟环境 (.venv)..."
    # uv venv 会在当前目录创建 .venv
    $UV_BIN venv --quiet --python 3.10

    log_info "正在使用 uv 极速安装 Butler 的生产级依赖库..."
    # 优先安装核心依赖与本地包
    $UV_BIN pip install --quiet -r requirements.txt
    $UV_BIN pip install --quiet -e .
else
    if [ "$HAS_SYSTEM_PYTHON" = false ]; then
        log_error "系统缺乏 Python3 环境且未能引导独立 uv 引擎，无法继续安装依赖。"
        exit 1
    fi
    log_info "正在使用系统原生 venv 初始化环境..."
    python3 -m venv .venv
    log_info "正在安装依赖（这可能需要较长时间，请耐心等待）..."
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
    .venv/bin/pip install --quiet -e .
fi

log_info "独立虚拟环境构建完成。"

# 6. 配置文件初始化与链式环境变量注入
log_step "阶段 6: 引导自动化环境配置文件 (.env) 模板注入"
if [ ! -f ".env" ]; then
    log_info "未检测到 .env 配置文件，正在以 .env.example 为模板克隆创建..."
    cp .env.example .env

    # 检测外界是否通过命令行链式注入了 DEEPSEEK_API_KEY 等敏感变量
    if [ -n "$DEEPSEEK_API_KEY" ]; then
        log_info "捕获到链式声明的 ${CYAN}DEEPSEEK_API_KEY${NC}，正在自动完成无感写入..."
        # 兼容 macOS 和 Linux 的 sed 替换
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/DEEPSEEK_API_KEY=.*/DEEPSEEK_API_KEY=\"$DEEPSEEK_API_KEY\"/g" .env
        else
            sed -i "s/DEEPSEEK_API_KEY=.*/DEEPSEEK_API_KEY=\"$DEEPSEEK_API_KEY\"/g" .env
        fi
    fi
else
    log_info ".env 配置文件已存在，跳过初始化，保留您的本地设置。"
fi

# 7. 全系统 CLI 指令封装与 PATH 注入
log_step "阶段 7: 全局 CLI 指令封装与用户 PATH 变量注册"

LAUNCHER_PATH="$BUTLER_BIN/butler"
log_info "正在将快速启动入口封装至: ${BLUE}$LAUNCHER_PATH${NC}"

cat > "$LAUNCHER_PATH" << EOF
#!/bin/bash
# Butler 自动化虚拟环境调度外壳
export PATH="$APP_DIR/.venv/bin:\$PATH"
exec "$APP_DIR/.venv/bin/python" "$APP_DIR/butler_cli.py" "\$@"
EOF

chmod +x "$LAUNCHER_PATH"

# 自动分析当前 Shell 配置文件，注册 PATH
CURRENT_SHELL=$(basename "$SHELL")
SHELL_RC=""

case "$CURRENT_SHELL" in
    bash)
        SHELL_RC="$HOME/.bashrc"
        ;;
    zsh)
        SHELL_RC="$HOME/.zshrc"
        ;;
    *)
        if [ -f "$HOME/.profile" ]; then
            SHELL_RC="$HOME/.profile"
        fi
        ;;
esac

PATH_LINE="export PATH=\"\$HOME/.local/bin:\$PATH\""

if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
    if ! grep -q "local/bin" "$SHELL_RC"; then
        log_info "正在将 $BUTLER_BIN 追加写入您的 ${CYAN}$SHELL_RC${NC} 配置文件中..."
        echo -e "\n# Butler CLI PATH Entry\n$PATH_LINE" >> "$SHELL_RC"
        log_info "PATH 写入完成。重启终端或运行 ${BOLD}source $SHELL_RC${NC} 即可直接生效。"
    else
        log_info "您的 ${CYAN}$SHELL_RC${NC} 中已包含 ~/.local/bin，跳过 PATH 写入。"
    fi
else
    log_warn "未能自动匹配到有效的 Shell 配置文件，请手动将 ${BOLD}$BUTLER_BIN${NC} 加入您的系统 PATH 中。"
fi

# 8. 顺利完结与指引提示
log_step "🎉 Butler 部署顺利完成！"
printf "${GREEN}${BOLD}恭喜！Butler 操作系统级数字员工已在您的系统沙箱成功安家。${NC}\n\n"
echo "您可以执行以下命令进行体验："
echo -e "  1. 激活新终端环境后运行：   ${YELLOW}${BOLD}butler doctor${NC}       (全面体检自检)"
echo -e "  2. 立即启动核心服务：       ${YELLOW}${BOLD}butler start${NC}        (启动核心网关)"
echo -e "  3. 委派特定 AI 角色执行任务： ${YELLOW}${BOLD}butler agent run demo-agent \"你的任务需求\"${NC}\n"

if [ ! -f "$APP_DIR/.env" ] || ! grep -q "sk-" "$APP_DIR/.env"; then
    log_warn "💡 提示: 检测到您尚未配置有效的 DeepSeek API 密钥。"
    echo -e "   请编辑 ${BLUE}$APP_DIR/.env${NC} 文件填充 ${CYAN}DEEPSEEK_API_KEY=\"您的密钥\"${NC}，方可享受完整 AI 协同体验！\n"
fi
# ==============================================================================
