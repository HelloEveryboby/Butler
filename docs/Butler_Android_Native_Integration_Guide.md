# Butler Android 原生化深度集成技术指南

## 1. 架构概述

Butler Android 采用 **Flutter + Chaquopy + Go-Mobile** 的三层混合架构，旨在保留 PC 端核心逻辑的同时，提供极致的原生移动端体验。

### 1.1 三层架构定义
*   **UI 层 (Flutter/Dart)**: 负责“果味美学”视觉展示。通过 `BackdropFilter` 实现毛玻璃效果，提供极致流畅的交互。
*   **中控层 (Go-Mobile)**: 运行 `Butler-Runner` 核心。负责高性能并发任务调度、长连接维护及系统状态监控。
*   **执行层 (Python/Chaquopy)**: 承载 Butler Skills 技能包。允许原封不动运行原有 Python 自动化逻辑，并直接调用 Android 系统 API。
*   **底层 (C++ NDK)**: 移植音量自适应调节等数学密集型算法，确保毫秒级响应。

---

## 2. 环境配置与工具链

### 2.1 基础环境
*   **Android Studio**: Hedgehog 或更高版本。
*   **Flutter SDK**: 3.19.x+。
*   **JDK**: 17 (Gradle 8.0+ 强制要求)。
*   **Go**: 1.21+。
*   **Python**: 3.10/3.11。

### 2.2 移动端专用工具
*   **Go-Mobile**: 用于将 Go 代码编译为 Android `.aar` 库。
    ```bash
    go install golang.org/x/mobile/cmd/gomobile@latest
    gomobile init
    ```
*   **Android NDK**: 建议版本 `25.2.9519653` (r25c)。

---

## 3. 核心引擎移植 (Go-Mobile)

### 3.1 编写 Mobile 适配层
在 `programs/butler_runner/mobile` 下创建适配代码，暴露接口给 Flutter。

```go
package mobile

import (
    "encoding/json"
    "github.com/gorilla/websocket"
)

type MobileCallback interface {
    OnStatusUpdate(status string)
    OnLog(message string)
}

type Runner struct {
    callback MobileCallback
    // ... 核心逻辑
}

func (r *Runner) Start(configJSON string, cb MobileCallback) {
    r.callback = cb
    // 启动 WebSocket 连接与任务调度
}
```

### 3.2 编译 AAR 库
```bash
export ANDROID_NDK_HOME=/path/to/ndk
gomobile bind -target=android -o butler_runner.aar ./mobile
```

---

## 4. Python 技能集成 (Chaquopy)

### 4.1 Gradle 配置
在 `app/build.gradle.kts` 中配置 Chaquopy 插件。

```kotlin
plugins {
    id("com.chaquo.python")
}

android {
    defaultConfig {
        python {
            version = "3.11"
            pip {
                install("requests")
                install("pyyaml")
            }
        }
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }
}
```

### 4.2 技能包存放
将 `skills/` 文件夹复制到 `src/main/python/` 目录下。在 Flutter 中通过 `MethodChannel` 调用 Python 函数：
```python
from butler_skills import automation_task
def execute_skill():
    return automation_task.run()
```

---

## 5. UI 视觉打磨 (Flutter Glassmorphism)

### 5.1 实时毛玻璃效果
使用 `BackdropFilter` 实现 Apple 风格 UI。

```dart
ClipRect(
  child: BackdropFilter(
    filter: ImageFilter.blur(sigmaX: 10.0, sigmaY: 10.0),
    child: Container(
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.2),
      ),
      child: Text("Butler System Active"),
    ),
  ),
)
```

---

## 6. 无障碍服务 (Zero-Touch 自动化)

### 6.1 实现 AccessibilityService
替代 PC 端的 Selenium，直接操作 Android UI 元素。

```java
public class ButlerAutomationService extends AccessibilityService {
    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        AccessibilityNodeInfo node = findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
        if (node != null && node.getViewIdResourceName().equals("login_field")) {
            // 自动填充账号
            Bundle arguments = new Bundle();
            arguments.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, "Butler_User");
            node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments);
        }
    }
}
```

---

## 7. C++ NDK 底层算法移植

### 7.1 提取核心算法
从 `programs/hybrid_math` 中提取音量自适应调节逻辑。

```cpp
// native-lib.cpp
extern "C" JNIEXPORT jfloat JNICALL
Java_com_butler_app_NativeLib_calculateOptimalVolume(JNIEnv* env, jobject /* this */, jfloat ambientNoise) {
    // 移植原有 hybrid_math 的数学模型
    float gain = 1.0f + (ambientNoise / 100.0f);
    return gain;
}
```

### 7.2 CMakeLists 配置
```cmake
add_library(butler-native SHARED native-lib.cpp)
find_library(log-lib log)
target_link_libraries(butler-native ${log-lib})
```

---

## 8. APK 打包与构建流程

### 8.0 使用一键打包脚本 (推荐)
为了简化构建流程，系统提供了自动化脚本：
```bash
./scripts/build_butler_android.sh
```
该脚本会自动：
1. 检查环境变量 (NDK, Flutter, Go)。
2. 编译 Go 内核为 `.aar`。
3. 同步 `skills/` 目录到 Chaquopy 路径。
4. 执行 `flutter build apk --release`。

### 8.1 命令行手动构建
在完成代码集成后，使用以下命令生成不同类型的安装包：

*   **生成调试包 (Debug APK)**:
    ```bash
    flutter build apk --debug
    ```
*   **生成正式包 (Release APK)**:
    ```bash
    flutter build apk --release
    ```
*   **生成针对特定架构的包 (Split APKs)**:
    ```bash
    flutter build apk --split-per-abi
    ```
    *注：这会为 arm64-v8a 和 x86_64 分别生成更小的 APK 文件。*

### 8.2 应用签名
正式发布前需在 `android/key.properties` 中配置签名：
```properties
storePassword=your_password
keyPassword=your_password
keyAlias=upload
storeFile=/path/to/upload-keystore.jks
```

### 8.3 性能与体积优化
为了减小体积，建议仅针对主流移动架构进行打包。
*   **开发调试**: `abiFilters += listOf("arm64-v8a", "x86_64")`
*   **正式发布**: `abiFilters += listOf("arm64-v8a")` (可减少 40% 的体积)

### 8.4 开启 R8 混淆
在 `build.gradle` 的 `buildTypes` 中：
```kotlin
release {
    isMinifyEnabled = true
    isShrinkResources = true
    proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
}
```

---

## 9. 常见问题解决 (Troubleshooting & FAQ)

### 9.1 Go-Mobile 与 NDK 版本冲突
*   **症状**: `gomobile bind` 报错 `unsupported API version 16 (not in 19..33)`。
*   **对策**:
    1. 确保 `ANDROID_NDK_HOME` 环境变量配置正确。
    2. 在命令中显式指定 API 级别：`gomobile bind -target=android -androidapi 21 ...`
    3. 推荐使用 NDK r25c (25.2.9519653)。

### 9.2 Chaquopy 模块导入失败
*   **症状**: 运行时抛出 `ModuleNotFoundError` 或 `ImportError`。
*   **对策**:
    1. 检查库是否包含 C 扩展。如果包含，需确认 Chaquopy 官方是否已为其提供针对 Android 的预编译版本（如 `numpy`, `pandas`）。
    2. 移除所有对 Windows 专有 API 的依赖（如 `ctypes.windll`, `pywin32`）。
    3. 在 `build.gradle` 中确保 `python { version = "3.11" }` 与代码兼容。

### 9.3 内存泄漏与系统杀进程
*   **症状**: Butler 在后台执行任务时突然中断。
*   **对策**:
    1. **开启 Wake Lock**: 防止 CPU 进入低功耗睡眠。
    2. **电池优化白名单**: 引导用户将 Butler 加入“不优化电池使用”列表。
    3. **前台服务**: 必须拥有 `FOREGROUND_SERVICE_SPECIAL_USE` 权限（Android 14+）并保持通知可见。

### 9.4 Flutter 与 Native 通信延迟
*   **症状**: UI 刷新滞后或点击无响应。
*   **对策**:
    1. 避免在 Flutter 的 UI 线程中直接调用耗时的 Python/Go 函数。
    2. 使用 `isolate` 处理数据，或在 Go/Python 层通过异步回调（如 `NativeCallback`）推送数据。

### 9.5 无障碍服务无法启动
*   **症状**: `AccessibilityService` 已安装但无法获取事件。
*   **对策**:
    1. 检查 `res/xml/accessibility_service_config.xml` 配置文件。
    2. 确保已在 AndroidManifest 中声明 `android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"`。
