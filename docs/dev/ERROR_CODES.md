# Butler 错误码规范（BTL-xxxx）

> 目标：**每个报错 = 人话原因 + 可复制的修复命令**。
> 实现：`butler/core/errors.py`（`format_error(code, detail)`），CLI / 向导 / doctor 共用同一出口。

## 码段划分

| 码段 | 范围 | 类别 |
| :--- | :--- | :--- |
| 环境 | `BTL-1xxx` | Python / 依赖 / 权限 / 端口 / 系统库 |
| 配置 | `BTL-2xxx` | .env / config.yaml / 密钥 |
| 技能 | `BTL-3xxx` | 技能加载 / 运行 / 包结构 |
| 硬件 | `BTL-4xxx` | HAL / 外设（均可优雅降级） |

## Top-10 错误速查

| 码 | 标题 | 原因 | 修复 |
| :--- | :--- | :--- | :--- |
| BTL-1001 | Python 版本不受支持 | 需要 3.10/3.11 | 换版本后 `python -m package.dependency_manager install_all` |
| BTL-1002 | 缺少 Python 依赖包 | 第三方库缺失 | `python -m package.dependency_manager install_all` |
| BTL-1003 | 目录不可写 | config/ data/ 无写权限 | `chmod u+w config data` |
| BTL-1004 | 端口被占用 | API 网关端口冲突 | `butler start --port 5002` |
| BTL-1005 | 缺少系统级依赖 | PortAudio / Redis 缺失 | `apt install portaudio19-dev redis-server` |
| BTL-2001 | AI 服务连不上 / Key 无效 | Key 缺失/过期/地址不可达 | `butler config` |
| BTL-2002 | .env 配置缺失 | 未初始化 | `butler init` |
| BTL-2003 | 配置文件冲突 | 多文件同键双写 | `butler config check`，以 config.yaml 为准 |
| BTL-3001 | 技能加载失败 | 技能依赖/代码异常 | `butler skill info <名>` |
| BTL-3002 | 技能不存在 | 名称未注册 | `butler skills list` |

（完整清单见 `butler/core/errors.py` 的 `ERROR_CATALOG`。）

## 标准输出格式

```
❌ [BTL-2001] AI 服务连不上 / Key 无效
   原因：API Key 未配置、已过期，或 API 地址不可达。
   详情：DEEPSEEK_API_KEY 未配置          ← 可选
   修复：butler config    # 重新配置并校验密钥（参考 docs/start/env-reference.md）
   💡 遇到问题随时运行: butler doctor（带「下一步建议」的一键体检）
```

## 约定

1. **对外输出禁止裸 traceback**：捕获异常后映射到错误码（traceback 只进日志）；
2. **新增错误**：在 `ERROR_CATALOG` 追加条目，码号按段递增，并同步本页 Top-10（若上榜）；
3. **降级类硬件问题**统一用 `BTL-4xxx`，文案必须包含「可忽略/已自动降级」；
4. CLI、Web UI、语音共用 `format_error`，保证三端体验一致。
