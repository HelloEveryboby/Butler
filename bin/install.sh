#!/bin/bash

# A script to automate the installation and configuration of the Butler assistant.

echo "Starting Butler installation..."

# Get the directory where the script is located (bin/)
BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Change to the project root (parent of bin/)
cd "$BIN_DIR/.."
PROJECT_ROOT=$(pwd)

echo "This script will guide you through the setup process."
echo "-----------------------------------------------------"

# --- Check for dependencies ---
echo "Step 1: Checking for required tools (python3, pip3)..."

command -v python3 >/dev/null 2>&1 || { echo >&2 "Error: python3 is not installed. Please install it and try again."; exit 1; }
echo "✅ Python 3 found."

command -v pip3 >/dev/null 2>&1 || { echo >&2 "Error: pip3 is not installed. Please install it and try again."; exit 1; }
echo "✅ pip3 found."

echo "-----------------------------------------------------"

# --- Install Python packages ---
echo "Step 2: Installing Python dependencies..."

echo "Choose Installation Mode:"
echo "1) Standard (System Python/venv)"
echo "2) Portable (External Libs only)"
echo "3) Full Portable (Portable Python Runtime + External Libs)"
read -r install_mode

if [ "$install_mode" == "3" ]; then
    echo "Setting up portable Python runtime..."
    python3 -m package.dependency_manager setup_runtime

    echo "Installing dependencies to lib_external (using system pip)..."
    python3 -m package.dependency_manager install_all
    if [ $? -eq 0 ]; then
        echo "✅ Full Portable setup complete."
    else
        echo >&2 "Error: Failed to install dependencies."
        exit 1
    fi
elif [ "$install_mode" == "2" ]; then
    echo "Installing dependencies to lib_external..."
    python3 -m package.dependency_manager install_all
    if [ $? -eq 0 ]; then
        echo "✅ Local dependencies installed successfully."
    else
        echo >&2 "Error: Failed to install local dependencies."
        exit 1
    fi
else
    echo "Installing dependencies globally/in venv from setup.py..."
    pip3 install .
    if [ $? -eq 0 ]; then
        echo "✅ Python dependencies installed successfully."
    else
        echo >&2 "Error: Failed to install Python dependencies. Please check the output above for errors."
        exit 1
    fi
fi

echo "-----------------------------------------------------"

# --- Configure AI Provider & API Keys ---
echo "Step 3: 配置 AI 服务商 & API 密钥"

# Check if .env file exists
if [ -f ".env" ]; then
    echo "检测到已存在的 .env 文件。是否覆盖? (y/n)"
    read -r overwrite
    if [ "$overwrite" != "y" ]; then
        echo "跳过 API 密钥配置。"
        echo "-----------------------------------------------------"
        echo "🎉 Butler 安装完成！"
        echo "启动助手: ./run.sh"
        exit 0
    fi
fi

echo ""
echo "========================================"
echo "  ① 选择 AI 模型服务商"
echo "========================================"
echo "1) DeepSeek (默认推荐)"
echo "2) OpenAI / 兼容 OpenAI 格式服务"
echo "3) 智谱 AI (GLM 系列)"
echo "4) Anthropic Claude"
echo "5) Google Gemini"
echo "6) 通义千问 (DashScope)"
echo "7) 百度文心一言 (千帆)"
echo "8) 自定义 API 地址 (Ollama / 本地部署等)"
echo ""
read -r -p "请输入选项编号 [1-8，默认 1]: " provider_choice

provider_choice="${provider_choice:-1}"
AI_PROVIDER=""
API_BASE_URL=""
MODEL_NAME=""
CUSTOM_PROVIDER_NAME=""
API_KEY_ENV_NAME=""
API_KEY_DISPLAY=""
API_KEY_VALUE=""

case "$provider_choice" in
    1)
        AI_PROVIDER="deepseek"
        API_KEY_ENV_NAME="DEEPSEEK_API_KEY"
        API_KEY_DISPLAY="DeepSeek API Key"
        ;;
    2)
        AI_PROVIDER="openai"
        API_KEY_ENV_NAME="OPENAI_API_KEY"
        API_KEY_DISPLAY="OpenAI API Key"
        ;;
    3)
        AI_PROVIDER="zhipu"
        API_KEY_ENV_NAME="ZHIPU_API_KEY"
        API_KEY_DISPLAY="智谱 API Key"
        ;;
    4)
        AI_PROVIDER="anthropic"
        API_KEY_ENV_NAME="ANTHROPIC_API_KEY"
        API_KEY_DISPLAY="Anthropic Claude API Key"
        ;;
    5)
        AI_PROVIDER="gemini"
        API_KEY_ENV_NAME="GEMINI_API_KEY"
        API_KEY_DISPLAY="Google Gemini API Key"
        ;;
    6)
        AI_PROVIDER="dashscope"
        API_KEY_ENV_NAME="DASHSCOPE_API_KEY"
        API_KEY_DISPLAY="通义千问 API Key"
        ;;
    7)
        AI_PROVIDER="qianfan"
        API_KEY_ENV_NAME="QIANFAN_API_KEY"
        API_KEY_DISPLAY="文心一言 API Key"
        ;;
    8)
        AI_PROVIDER="custom"
        API_KEY_ENV_NAME="CUSTOM_API_KEY"
        API_KEY_DISPLAY="自定义 API Key"
        echo ""
        read -r -p "请输入自定义名称（用于区分，例如 我的Ollama）: " CUSTOM_PROVIDER_NAME
        echo "请输入 API 基础地址（例如 http://localhost:11434/v1）："
        read -r API_BASE_URL
        echo "请输入模型名称（例如 qwen2.5:7b）："
        read -r MODEL_NAME
        ;;
    *)
        echo "无效选项，使用默认 DeepSeek。"
        AI_PROVIDER="deepseek"
        API_KEY_ENV_NAME="DEEPSEEK_API_KEY"
        API_KEY_DISPLAY="DeepSeek API Key"
        ;;
esac

# ② 输入对应的 API 密钥
echo ""
echo "========================================"
echo "  ② 输入 API 密钥"
echo "========================================"
echo "当前选择: $AI_PROVIDER ($API_KEY_DISPLAY)"
echo ""
echo "请输入您的 $API_KEY_DISPLAY（内容将被隐藏）："
read -s API_KEY_VALUE
echo ""

# 是否使用自定义地址（非 custom 模式下可选）
if [ "$AI_PROVIDER" != "custom" ] && [ -z "$API_BASE_URL" ]; then
    read -r -p "是否需要自定义 API 基础地址? (覆盖默认) [y/N]: " override_url
    if [ "$override_url" = "y" ] || [ "$override_url" = "Y" ]; then
        echo "请输入自定义 API 基础地址："
        read -r API_BASE_URL
    fi
fi

if [ "$AI_PROVIDER" != "custom" ] && [ -z "$MODEL_NAME" ]; then
    read -r -p "是否需要自定义模型名称? (覆盖默认) [y/N]: " override_model
    if [ "$override_model" = "y" ] || [ "$override_model" = "Y" ]; then
        echo "请输入自定义模型名称："
        read -r MODEL_NAME
    fi
fi

# 可选：百度语音
echo ""
echo "========================================"
echo "  语音服务配置 (可选，直接回车跳过)"
echo "========================================"
echo "请输入 Baidu App ID (回车跳过):"
read BAIDU_APP_ID
echo "请输入 Baidu API Key (回车跳过):"
read BAIDU_API_KEY
echo "请输入 Baidu Secret Key (回车跳过，输入将被隐藏):"
read -s BAIDU_SECRET_KEY
echo ""
echo "请输入 Picovoice Access Key (回车跳过):"
read PICOVOICE_ACCESS_KEY

# Create .env file
echo "正在创建 .env 文件..."
cat > .env << EOL
# AI 模型提供商配置
AI_PROVIDER="${AI_PROVIDER}"
CUSTOM_PROVIDER_NAME="${CUSTOM_PROVIDER_NAME}"
API_BASE_URL="${API_BASE_URL}"
MODEL_NAME="${MODEL_NAME}"

# AI API 密钥（根据 AI_PROVIDER 生效，仅对应服务商写入）
DEEPSEEK_API_KEY="$([ "$AI_PROVIDER" = "deepseek" ] && echo "${API_KEY_VALUE}" || echo "")"
OPENAI_API_KEY="$([ "$AI_PROVIDER" = "openai" ] && echo "${API_KEY_VALUE}" || echo "")"
ZHIPU_API_KEY="$([ "$AI_PROVIDER" = "zhipu" ] && echo "${API_KEY_VALUE}" || echo "")"
ANTHROPIC_API_KEY="$([ "$AI_PROVIDER" = "anthropic" ] && echo "${API_KEY_VALUE}" || echo "")"
GEMINI_API_KEY="$([ "$AI_PROVIDER" = "gemini" ] && echo "${API_KEY_VALUE}" || echo "")"
DASHSCOPE_API_KEY="$([ "$AI_PROVIDER" = "dashscope" ] && echo "${API_KEY_VALUE}" || echo "")"
QIANFAN_API_KEY="$([ "$AI_PROVIDER" = "qianfan" ] && echo "${API_KEY_VALUE}" || echo "")"
CUSTOM_API_KEY="$([ "$AI_PROVIDER" = "custom" ] && echo "${API_KEY_VALUE}" || echo "")"

# 百度语音 API (可选)
BAIDU_APP_ID="${BAIDU_APP_ID}"
BAIDU_API_KEY="${BAIDU_API_KEY}"
BAIDU_SECRET_KEY="${BAIDU_SECRET_KEY}"

# Picovoice (可选)
PICOVOICE_ACCESS_KEY="${PICOVOICE_ACCESS_KEY}"

# MQTT （如适用）
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_TOPIC_PREFIX=butler/
EOL

echo "✅ .env 文件创建成功。"
echo "  - AI_PROVIDER = ${AI_PROVIDER}"
[ -n "$CUSTOM_PROVIDER_NAME" ] && echo "  - CUSTOM_PROVIDER_NAME = ${CUSTOM_PROVIDER_NAME}"
echo "  - 密钥保存到 = ${API_KEY_ENV_NAME}（已隐藏输入）"
[ -n "$API_BASE_URL" ] && echo "  - API_BASE_URL = ${API_BASE_URL}"
[ -n "$MODEL_NAME" ] && echo "  - MODEL_NAME = ${MODEL_NAME}"
echo "-----------------------------------------------------"

echo "🎉 Butler installation and configuration is complete!"
echo "You can now start the assistant by running ./run.sh (on Linux/macOS) or run.bat (on Windows)."
echo "If you are on Linux or macOS, you may need to make the script executable first with: chmod +x run.sh"
