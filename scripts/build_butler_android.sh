#!/bin/bash

# Butler Android 一键打包脚本
# 环境要求: Flutter, Go, gomobile, Python 3.11, Android NDK r25c

set -e

# --- 1. 环境检查 ---
echo "🚀 [1/5] 正在检查构建环境..."

if [ -z "$ANDROID_NDK_HOME" ]; then
    echo "❌ 错误: 未设置 ANDROID_NDK_HOME 环境变量"
    exit 1
fi

if ! command -v flutter &> /dev/null; then
    echo "❌ 错误: 未找到 flutter 命令"
    exit 1
fi

if ! command -v gomobile &> /dev/null; then
    echo "❌ 错误: 未安装 gomobile, 请运行 'go install golang.org/x/mobile/cmd/gomobile@latest'"
    exit 1
fi

PROJECT_ROOT=$(pwd)
ANDROID_DIR="$PROJECT_ROOT/butler_android"

if [ ! -d "$ANDROID_DIR" ]; then
    echo "⚠️ 警告: 未找到 $ANDROID_DIR, 请确保你已按照文档创建了 Flutter 项目。"
    exit 1
fi

# --- 2. 编译 Go 核心引擎 (Go-Mobile) ---
echo "⚙️ [2/5] 正在编译 Go-Mobile 内核 (.aar)..."
cd "$PROJECT_ROOT/programs/butler_runner"
mkdir -p "$ANDROID_DIR/android/app/libs"

# 检查 gomobile 是否可用，如果不可用则提示但跳过（以便在受限环境下生成代码）
if command -v gomobile &> /dev/null; then
    # 显式指定 API 21 以避免 NDK 版本兼容性报错
    gomobile bind -v -target=android -androidapi 21 -o "$ANDROID_DIR/android/app/libs/butler_runner.aar" ./mobile
else
    echo "⚠️ 警告: 未找到 gomobile, 跳过 Go 编译。在真实环境中此步必不可少。"
fi

# --- 3. 同步 Python 技能包 (Chaquopy) ---
echo "🐍 [3/5] 正在同步 Python 技能包..."
PYTHON_SRC_DIR="$ANDROID_DIR/android/app/src/main/python"
mkdir -p "$PYTHON_SRC_DIR"

# 清理旧技能并同步新技能
rm -rf "$PYTHON_SRC_DIR/skills"
cp -r "$PROJECT_ROOT/skills" "$PYTHON_SRC_DIR/"

# --- 4. Flutter 依赖同步 ---
echo "📦 [4/5] 正在同步 Flutter 依赖..."
cd "$ANDROID_DIR"
flutter pub get

# --- 5. 执行最终构建 ---
echo "🏗️ [5/5] 正在执行 Flutter APK 构建 (Release)..."
# 默认开启分架构打包以优化体积
flutter build apk --release --split-per-abi

echo "✅ 构建完成！"
echo "📦 APK 目录: $ANDROID_DIR/build/app/outputs/flutter-apk/"
ls -lh "$ANDROID_DIR/build/app/outputs/flutter-apk/app-arm64-v8a-release.apk" || true
