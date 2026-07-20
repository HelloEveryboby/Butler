#!/usr/bin/env bash

# set -e: 任何命令失败立即退出
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANDROID_DIR="$PROJECT_ROOT/butler_android"

echo "====== [Butler Android Build Pipeline] ======"
echo "Initializing build in: $ANDROID_DIR"

# 1. 环境与 JDK 21 状态检查
if [ -n "$JAVA_HOME" ]; then
    echo "Using JAVA_HOME: $JAVA_HOME"
else
    echo "Warning: JAVA_HOME is not set. Relying on system default java."
fi

# 2. 验证 "One Folder = One Skill" 资产释放目录是否存在
ASSETS_DIR="$ANDROID_DIR/app/src/main/assets/skills"
if [ ! -d "$ASSETS_DIR" ]; then
    echo "Creating missing assets/skills directory..."
    mkdir -p "$ASSETS_DIR"
fi

# 3. 复制 Python 技能包
PYTHON_SRC_DIR="$ANDROID_DIR/app/src/main/python"
mkdir -p "$PYTHON_SRC_DIR"
echo "Syncing Python skill packages..."
rm -rf "$PYTHON_SRC_DIR/skills"
cp -r "$PROJECT_ROOT/skills" "$PYTHON_SRC_DIR/"

# 4. 执行闭环编译
cd "$ANDROID_DIR"
echo "Running Gradle daemon-less assembleDebug..."
gradle clean assembleDebug --no-daemon

# 5. 产物交付校验
APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
if [ -f "$APK_PATH" ]; then
    echo "============================================="
    echo "✓ SUCCESS: Butler Android APK generated perfectly!"
    echo "Target: $ANDROID_DIR/$APK_PATH"
    echo "============================================="
else
    echo "Error: APK generation missed silently."
    exit 1
fi
