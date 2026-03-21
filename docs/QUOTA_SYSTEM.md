# API Token 额度与金额管理系统 (Quota System)

为了防止 API 调用产生的费用超出预期，Butler 引入了基于金额的额度监控与强制关断系统。

## 核心原理

1. **消耗监控**：系统会在每次 API 调用（目前支持 DeepSeek）后，从响应中获取 `total_tokens`。
2. **金额换算**：根据配置的 `token_rate`（每百万 tokens 的价格），将 token 消耗转换为人民币金额。
3. **强制停止**：当已消耗金额超过设定的 `limit` 时，系统将自动拦截后续的 AI 调用。如果开启了 `halt_system`，Butler 将锁定所有用户指令。

## 配置文件说明

额度配置位于 `config/system_config.json` 中的 `api.quota` 字段：

```json
{
    "api": {
        "quota": {
            "enabled": true,        // 是否启用额度控制
            "limit": 100.0,         // 总额度限额 (单位：元/RMB)
            "consumed": 0.0,        // 当前已消耗金额 (自动更新)
            "token_rate": 2.0,      // 每 1,000,000 tokens 的价格 (元)
            "halt_system": true     // 额度耗尽后是否锁定整个系统
        }
    }
}
```

## 如何恢复系统

如果系统因额度耗尽而锁定（报错提示：`⚠️ 系统已锁定: API 额度已耗尽`），您可以采取以下操作之一：

### 1. 增加限额
打开 `config/system_config.json`，将 `"limit"` 的值调大（例如从 `100.0` 改为 `200.0`）。

### 2. 重置消耗
如果您已经手动充值了 API 余额，可以将 `"consumed"` 字段重置为 `0.0`。

### 3. 禁用限制 (不推荐)
将 `"enabled"` 设置为 `false`。

## 开发者说明

在编写新的需要调用外部 API 的功能时，请务必集成 `QuotaManager`：

```python
from package.core_utils.quota_manager import quota_manager

# 1. 调用前检查
if not quota_manager.check_quota():
    return "额度不足，无法执行"

# 2. 执行 API 调用
response = requests.post(...)
total_tokens = response.json().get('usage', {}).get('total_tokens', 0)

# 3. 更新消耗
quota_manager.update_usage(total_tokens)
```

## 默认价格参考 (2025)
* **DeepSeek V3/R1**: 约 1~4 元 / 1M tokens (视缓存而定)。本系统默认设为 `2.0` 元。
