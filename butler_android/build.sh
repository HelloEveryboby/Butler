# Butler Android 打包脚本 (Linux/macOS)
# 用法: ./build.sh [debug|release]
#
# 前提条件:
#   - JDK 17 (JAVA_HOME 已设置)
#   - Android SDK (ANDROID_HOME 已设置)
#   - 或使用 Android Studio 内置终端运行

set -e

MODE=${1:-debug}
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

echo "========================================"
echo " Butler Android 构建"
echo " 模式: $MODE"
echo "========================================"

# 检查 JAVA_HOME
if [ -z "$JAVA_HOME" ]; then
    # 尝试自动检测
    if command -v java >/dev/null 2>&1; then
        echo "⚠️  JAVA_HOME 未设置，使用系统 Java"
    else
        echo "❌ 未找到 Java。请安装 JDK 17:"
        echo "   macOS:   brew install openjdk@17"
        echo "   Ubuntu:  sudo apt install openjdk-17-jdk"
        echo "   设置:    export JAVA_HOME=/path/to/jdk17"
        exit 1
    fi
fi

# 检查 Android SDK
if [ -z "$ANDROID_HOME" ] && [ -z "$ANDROID_SDK_ROOT" ]; then
    # 尝试默认路径
    if [ -d "$HOME/Library/Android/sdk" ]; then
        export ANDROID_HOME="$HOME/Library/Android/sdk"
    elif [ -d "$HOME/Android/Sdk" ]; then
        export ANDROID_HOME="$HOME/Android/Sdk"
    else
        echo "❌ 未找到 Android SDK。请安装 Android Studio 或设置 ANDROID_HOME。"
        exit 1
    fi
    echo "ℹ️  Android SDK: $ANDROID_HOME"
fi

# 使 gradlew 可执行
chmod +x gradlew

# 构建
if [ "$MODE" = "release" ]; then
    echo ""
    echo "📦 构建 Release APK..."
    ./gradlew assembleRelease
    APK_PATH="app/build/outputs/apk/release/app-release-unsigned.apk"
else
    echo ""
    echo "📦 构建 Debug APK..."
    ./gradlew assembleDebug
    APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
fi

echo ""
if [ -f "$APK_PATH" ]; then
    SIZE=$(du -h "$APK_PATH" | cut -f1)
    echo "✅ 构建成功!"
    echo "📱 APK: $APK_PATH ($SIZE)"
    echo ""
    echo "安装到设备:"
    echo "  adb install $APK_PATH"
else
    echo "❌ 构建失败，请检查错误信息。"
    exit 1
fi
