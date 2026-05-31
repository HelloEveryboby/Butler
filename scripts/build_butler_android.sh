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
# 注意：Chaquopy 在 Android 原生项目中通常使用 app/libs
mkdir -p "$ANDROID_DIR/app/libs"

# 显式指定 API 21 以避免 NDK 版本兼容性报错
gomobile bind -v -target=android -androidapi 21 -o "$ANDROID_DIR/app/libs/butler_runner.aar" ./mobile

# --- 3. 同步 Python 技能包 (Chaquopy) ---
echo "🐍 [3/5] 正在同步 Python 技能包..."
PYTHON_SRC_DIR="$ANDROID_DIR/app/src/main/python"
mkdir -p "$PYTHON_SRC_DIR"

# 清理旧技能并同步新技能
rm -rf "$PYTHON_SRC_DIR/skills"
cp -r "$PROJECT_ROOT/skills" "$PYTHON_SRC_DIR/"

# --- 4. 构建 Release APK ---
echo "🏗️ [4/5] 正在执行 Gradle APK 构建 (Release)..."
cd "$ANDROID_DIR"
# 如果是 Flutter 项目则使用 flutter build，如果是原生 Gradle 项目则使用 assemble
if [ -f "pubspec.yaml" ]; then
    flutter build apk --release --split-per-abi
    APK_PATH="build/app/outputs/flutter-apk"
else
    gradle assembleRelease
    APK_PATH="app/build/outputs/apk/release"
fi

# --- 5. 签名 (如果存在 keystore) ---
echo "✒️ [5/5] 正在检查签名..."
if [ -f "$PROJECT_ROOT/butler.jks" ]; then
    echo "发现 butler.jks，正在签名..."
    UNSIGNED_APK=$(find "$APK_PATH" -name "*-unsigned.apk" | head -n 1)
    if [ -n "$UNSIGNED_APK" ]; then
        /opt/android-sdk/build-tools/35.0.0/apksigner sign --ks "$PROJECT_ROOT/butler.jks" \
            --ks-pass pass:123456 --ks-key-alias butler --key-pass pass:123456 \
            --out "$APK_PATH/butler-release.apk" "$UNSIGNED_APK"
        echo "✅ 签名完成: $APK_PATH/butler-release.apk"
    fi
else
    echo "未发现 butler.jks，跳过签名步骤。"
fi

echo "✅ 构建完成！"
echo "📦 APK 目录: $ANDROID_DIR/$APK_PATH"
