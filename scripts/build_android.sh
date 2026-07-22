#!/usr/bin/env bash
# ==========================================
# Butler Android 一键打包脚本
#
# 自动完成: 同步代码 → 构建前端 → 打包 APK
#
# 用法:
#   ./scripts/build_android.sh              # Debug APK
#   ./scripts/build_android.sh release      # Release APK
#   ./scripts/build_android.sh --skip-sync  # 跳过同步，直接打包
#   ./scripts/build_android.sh --skip-frontend # 跳过前端构建
# ==========================================

set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$ROOT"

MODE="${1:-debug}"
SKIP_SYNC=false
SKIP_FRONTEND=false

# 解析参数
for arg in "$@"; do
    case $arg in
        --skip-sync) SKIP_SYNC=true ;;
        --skip-frontend) SKIP_FRONTEND=true ;;
        release) MODE="release" ;;
    esac
done

echo "=========================================="
echo " Butler Android 一键打包"
echo " 模式: $MODE"
echo "=========================================="

# === Step 1: 同步 Python 代码 ===
if [ "$SKIP_SYNC" = false ]; then
    echo ""
    echo "📦 Step 1: 同步核心代码到 butler_android..."
    python "$SCRIPT_DIR/sync_android.py" $([ "$SKIP_FRONTEND" = true ] && echo "--skip-frontend")
else
    echo ""
    echo "⏭️  Step 1: 跳过同步 (--skip-sync)"
fi

# === Step 2: 构建前端 ===
if [ "$SKIP_FRONTEND" = false ] && [ "$SKIP_SYNC" = false ]; then
    echo ""
    echo "🌐 Step 2: 构建前端..."
    if [ -d "$ROOT/frontend" ] && [ -f "$ROOT/frontend/package.json" ]; then
        cd "$ROOT/frontend"
        if command -v npm &> /dev/null; then
            npm run build 2>/dev/null || echo "⚠️  前端构建失败，使用已有 dist/"
        else
            echo "⚠️  npm 未安装，跳过前端构建"
        fi
        cd "$ROOT"
    else
        echo "⚠️  frontend/ 不存在，跳过"
    fi
else
    echo ""
    echo "⏭️  Step 2: 跳过前端构建"
fi

# === Step 3: 打包 APK ===
echo ""
echo "🤖 Step 3: 打包 Android APK..."
cd "$ROOT/butler_android"

# 检查 Gradle Wrapper
if [ ! -f "gradle/wrapper/gradle-wrapper.jar" ]; then
    echo "⚠️  gradle-wrapper.jar 缺失"
    echo "   首次构建需要 Android Studio 自动下载"
    echo "   或手动执行: gradle wrapper --gradle-version 8.5"
fi

# 构建
if [ "$MODE" = "release" ]; then
    echo "  📦 构建 Release APK..."
    ./gradlew assembleRelease
    APK_PATH="app/build/outputs/apk/release/app-release-unsigned.apk"
else
    echo "  📦 构建 Debug APK..."
    ./gradlew assembleDebug
    APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
fi

cd "$ROOT"

# === 结果 ===
echo ""
if [ -f "$ROOT/butler_android/$APK_PATH" ]; then
    SIZE=$(du -h "$ROOT/butler_android/$APK_PATH" | cut -f1)
    echo "=========================================="
    echo " ✅ 构建成功!"
    echo "=========================================="
    echo ""
    echo " 📱 APK: butler_android/$APK_PATH ($SIZE)"
    echo ""
    echo " 安装到手机:"
    echo "   adb install butler_android/$APK_PATH"
    echo ""
else
    echo "=========================================="
    echo " ❌ 构建失败"
    echo "=========================================="
    echo ""
    echo " 排查:"
    echo "   1. 检查 JAVA_HOME 是否指向 JDK 17"
    echo "   2. 检查 ANDROID_HOME 是否指向 SDK"
    echo "   3. 在 Android Studio 中打开 butler_android/ 尝试构建"
    exit 1
fi
