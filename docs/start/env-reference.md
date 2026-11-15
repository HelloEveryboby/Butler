# Butler 完整环境变量参考（.env）

> `.env.example` 为最小可用配置（1 个服务商 + 1 个密钥）。本页是**全部可选项**的参考手册，
> 仅在使用非默认服务商、语音、消息总线等进阶功能时才需要。

## 1. AI 模型提供商

| 变量 | 说明 | 示例 |
| :--- | :--- | :--- |
| `AI_PROVIDER` | 服务商选择：`deepseek`(默认) / `openai` / `zhipu` / `anthropic` / `gemini` / `dashscope` / `qianfan` / `custom` | `deepseek` |
| `CUSTOM_PROVIDER_NAME` | 自定义提供商名称（`AI_PROVIDER=custom` 时用于区分多个自定义配置） | `我的Ollama` |
| `API_BASE_URL` | 自定义 API 基础地址（custom 必填；也可覆盖默认地址） | `http://localhost:11434/v1` |
| `MODEL_NAME` | 模型名称（留空使用提供商默认模型） | `deepseek-chat` |

各服务商默认模型：DeepSeek `deepseek-chat` / OpenAI `gpt-3.5-turbo` / 智谱 `glm-4-flash` /
Claude `claude-3-5-sonnet-20241022` / Gemini `gemini-1.5-flash` / 通义 `qwen-turbo` / 文心 `ernie-4.0-8k`。

## 2. API 密钥（仅需填写 `AI_PROVIDER` 对应的那一个）

```env
DEEPSEEK_API_KEY=YOUR_KEY_HERE
OPENAI_API_KEY=YOUR_KEY_HERE
ZHIPU_API_KEY=YOUR_KEY_HERE
ANTHROPIC_API_KEY=YOUR_KEY_HERE
GEMINI_API_KEY=YOUR_KEY_HERE
DASHSCOPE_API_KEY=YOUR_KEY_HERE
QIANFAN_API_KEY=YOUR_KEY_HERE
CUSTOM_API_KEY=YOUR_KEY_HERE
```

常用 API 基础地址（`custom` / 覆盖默认时参考）：

| 服务商 | API_BASE_URL |
| :--- | :--- |
| DeepSeek | `https://api.deepseek.com/v1` |
| OpenAI | `https://api.openai.com/v1` |
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` |
| Claude | `https://api.anthropic.com/v1` |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 文心一言 | `https://qianfan.baidubce.com/v2` |
| 本地 Ollama | `http://localhost:11434/v1` |

## 3. 语音服务（可选）

缺省使用本地语音引擎（Faster-Whisper + 离线合成），无需任何 Key。以下为进阶选项：

```env
# 百度云语音
BAIDU_APP_ID=YOUR_APP_ID
BAIDU_API_KEY=YOUR_KEY_HERE
BAIDU_SECRET_KEY=YOUR_KEY_HERE

# Picovoice（唤醒词 / 录音授权）
PICOVOICE_ACCESS_KEY=YOUR_KEY_HERE
```

## 4. MQTT 消息总线（可选，如适用）

```env
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_TOPIC_PREFIX=butler/
```

## 5. 敏感凭据建议

第三方凭据建议使用内置的 **零信任 SecretVault**（PBKDF2 + AES-256-GCM 本地加密）保存，
`.env` 仅存放 AI 服务商密钥即可。
