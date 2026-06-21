# Butler 系统配置指南

本文档详细说明了 Butler 智能管家系统的配置项及其用法。系统采用单一的 `config/config.yaml` 文件进行管理，并支持环境变量动态注入。

## 1. 配置文件结构

配置文件位于 `config/config.yaml`。它由多个逻辑部分组成：

### 1.1 API 配置 (`api`)
管理所有第三方服务的访问密钥和配额。

| 参数 | 说明 | 环境变量支持 |
| :--- | :--- | :--- |
| `deepseek_key` | DeepSeek LLM 的 API 密钥 | `DEEPSEEK_API_KEY` |
| `baidu_app_id` | 百度语音服务的 App ID | `BAIDU_APP_ID` |
| `baidu_api_key` | 百度语音服务的 API Key | `BAIDU_API_KEY` |
| `baidu_secret_key` | 百度语音服务的 Secret Key | `BAIDU_SECRET_KEY` |
| `picovoice_access_key` | Picovoice 唤醒词服务的 Access Key | `PICOVOICE_ACCESS_KEY` |
| `quota.consumed` | 已消耗的 API 额度（自动更新） | - |

### 1.2 语音配置 (`voice`)
控制语音交互模式。

- `mode`: 支持 `online` (百度), `local` (Faster-Whisper), `offline`。
- `local_stt_model`: 本地 STT 使用的模型大小 (如 `base`, `small`, `medium`)。

### 1.3 界面与显示 (`display`)
- `default_mode`: UI 运行模式。
- `theme`: 界面主题（如 `google`, `apple`）。
- `usb_screen`: 外部 USB 屏幕的分辨率配置。

### 1.4 便携模式 (`portable_mode`)
控制 Butler 在脱离系统环境时的行为。

- `enabled`: 是否开启便携模式。
- `auto_detect_display`: 自动检测可用显示器。
- `serial_link`: 与外部硬件（如 STM32）的串口通信配置。

### 1.5 性能与运行 (`performance` & `interpreter`)
- `performance.mode`: `NORMAL`, `ECO`, `HIGH_PERFORMANCE`。
- `interpreter.safety_mode`: 开启代码执行安全检查。
- `interpreter.max_iterations`: 允许 Agent 自主思考的最大循环次数。

---

## 2. 环境变量注入

系统支持在 YAML 中使用 `${VAR_NAME:-DEFAULT_VALUE}` 语法。

**示例：**
```yaml
api:
  deepseek_key: "${DEEPSEEK_API_KEY:-your_default_key}"
```

在系统启动前，可以通过 `.env` 文件或系统环境变量设置这些值。`ConfigLoader` 会在加载时自动进行替换。

---

## 3. 技术实现

### 3.1 验证机制
系统使用 **Pydantic** (`butler/core/config_model.py`) 对配置进行强类型校验。如果 `config.yaml` 中的格式错误或缺少必填项，系统将抛出警告并回退到安全的默认配置。

### 3.2 动态保存
通过 `config_loader.save(new_config_updates)` 方法，系统可以在运行时修改配置并持久化到 YAML 文件中。保存时会保持原有的注释结构（在可能的情况下）。

---

## 4. 常见问题 (FAQ)

**Q: 为什么我的 API Key 没有生效？**
A: 请检查是否在根目录下创建了 `.env` 文件，或者直接在 `config.yaml` 中填入了值（不带 `${}`）。

**Q: `settings.yaml` 去了哪里？**
A: 该文件已被废弃并整合进 `config.yaml`，以实现单一事实来源。
