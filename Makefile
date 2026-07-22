.PHONY: sync-android-native sync-android-flutter build-android-native build-android-flutter

# ==========================================
# 安卓双壳同步指令 (Sync Only)
# ==========================================

## 1. 同步前端/核心资产到 Kotlin 原生壳
sync-android-native:
	@python3 scripts/sync_android.py --target native

## 2. 同步前端/核心资产到 Flutter 壳
sync-android-flutter:
	@python3 scripts/sync_android.py --target flutter


# ==========================================
# 安卓双壳一键构建指令 (Sync & Build APK)
# ==========================================

## 1. 构建 Kotlin 原生 APK
build-android-native:
	@python3 scripts/sync_android.py --target native --build

## 2. 构建 Flutter APK
build-android-flutter:
	@python3 scripts/sync_android.py --target flutter --build
