# 🌐 Butler Android — 方案 C: Flutter 跨平台

> **技术栈**: Flutter 3.x + Dart + Platform Channels
> **平台**: Android + iOS
> **架构**: Flutter UI ↔ Platform Channel ↔ Python/gRPC 后端

## 架构

```
┌─────────────────────────────────────┐
│           Flutter UI (Dart)         │
│  ┌─────────┐ ┌──────────┐ ┌──────┐ │
│  │ChatScreen│ │SkillsScr  │ │Settings│ │
│  └────┬────┘ └────┬─────┘ └──┬───┘ │
│       │           │          │      │
│  ┌────▼───────────▼──────────▼───┐  │
│  │     ButlerService (Dart)      │  │
│  │  ┌─────────────────────────┐  │  │
│  │  │  Platform Channel       │  │  │
│  │  │  (MethodChannel)        │  │  │
│  │  └──────────┬──────────────┘  │  │
│  └─────────────┼─────────────────┘  │
│                │                    │
│  ┌─────────────▼─────────────────┐  │
│  │  Android: Chaquopy Python     │  │
│  │  iOS: gRPC → Remote Server    │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

## 构建

```bash
cd butler-android-c
flutter pub get
flutter build apk --release

# APK: build/app/outputs/flutter-apk/app-release.apk
```

## 功能

- 💬 Material Design 3 Chat 界面
- 📦 技能列表浏览
- ⚙️ 设置面板
- 🔄 Platform Channel 调用原生 Python
- 📱 Android + iOS 双端支持
