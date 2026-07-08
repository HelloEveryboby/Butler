# Butler 资产同步中心 (Asset Sync Hub) 指南

Butler 资产同步中心（Asset Sync Hub）是一个工业级的资源管理与同步系统，旨在解决 PC 端核心源码与 Android 端发布资产之间的解耦、转换与验证问题。

## 核心能力

1.  **零配置规则引擎**：默认内置代码、资产与前端页面的映射规则。
2.  **编译流水线**：自动执行图片压缩（WebP）、音频转换（OGG），支持智能降级。
3.  **增量同步与指纹缓存**：基于 MD5 指纹，仅同步变更文件，极大缩短发布时间。
4.  **配置自动化注入**：从 `android.env` 自动替换模板并更新 `gradle.properties`。
5.  **回滚与备份**：自动保留最近 3 个同步版本，支持一键回滚。
6.  **代码冲突监测**：防止 Android 端手工修改的代码被 PC 端无意覆盖。

## 快速开始

### 1. 初始化
在项目根目录下运行：
```bash
python butler.py init
```
这将生成 `.butler_manifest.json`、`config.template.json` 和 `butler_android/android.env.example`。

### 2. 环境检查
检查工具链（cwebp, ffmpeg）是否可用：
```bash
python butler.py check-env
```

### 3. 一键同步
将代码和资产同步到 Android 项目：
```bash
python butler.py sync
```
*同步前会自动创建备份。如果检测到代码冲突，请根据提示处理。*

### 4. 版本回滚
如果同步后打包失败，可一键回滚：
```bash
python butler.py rollback --step=1
```

## 目录结构说明

- `butler.py`: 统一入口脚本。
- `.butler_manifest.json`: 同步规则配置文件。
- `.sync_cache.json`: 文件指纹缓存（请勿删除）。
- `butler_android/.sync_backups/`: 存放历史备份。
- `butler/sync_hub/`: 核心逻辑包。

## 进阶配置

您可以修改 `.butler_manifest.json` 来定义更复杂的同步逻辑。例如：

```json
{
  "source": "assets/special/",
  "target": "butler_android/app/src/main/assets/special/",
  "convert": {
    "format": "webp",
    "quality": 70
  }
}
```

## 禁区保护
以下路径受系统保护，同步脚本永远不会触碰，以确保原生 Android 开发的安全：
- `app/src/main/java/`
- `app/src/main/kotlin/`
- `app/src/main/res/values/strings.xml`
- `app/build.gradle`
- 以及 Gradle 相关配置文件。
