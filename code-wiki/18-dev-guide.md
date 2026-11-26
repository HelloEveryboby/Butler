# 18 · 开发指南

> 面向贡献者：如何新增技能、BHL 模块、意图、工具，以及代码规范与调试方法。

## 18.1 新增一个技能（最快扩展方式）

### 最小步骤

```bash
mkdir skills/my_skill
```

**1) 写 `skills/my_skill/SKILL.md`**

```markdown
---
name: My Skill
description: 一句话说明这个技能做什么，供 LLM 判断何时使用。
provides: [demo.output]
requires: {}
risk: low
keywords: [示例, demo, hello]
---

# My Skill

详细说明能力、参数、示例。LLM 在命中时会读取这段指令。
```

**2) 如需执行逻辑，写 `skills/my_skill/main.py`**

```python
def handle_request(action, **kwargs):
    """技能执行入口。action 为动作名，其余为参数。"""
    if action == "run":
        text = kwargs.get("text", "")
        return f"处理结果: {text.upper()}"
    return {"status": "failed", "error": f"未知动作: {action}"}
```

> 也可用 `__init__.py` 导出同样的 `handle_request`。核心插件则导出 `initialize_core(context)` 获取 `event_bus/message_bus/blackboard/data_storage/system_sensor`。

**3) 验证**

- 保存后 watchdog 自动热加载；
- `/skills` 查看是否出现；
- `/skill-info my_skill` 查看元数据；
- `/skill my_skill run text=hello` 手动执行；
- CLI：`python butler_cli.py skill list` / `skill info my_skill`。

### 高级能力

| 需求 | 做法 |
| :--- | :--- |
| 子进程隔离 | `SKILL.md` 加 `isolation: process` |
| 声明依赖上游 | `requires:` + 从黑板快照取 |
| 输出给下游 | `provides:`（LDST 影子链会写黑板） |
| 高危操作二次确认 | `risk: high` 或 `requires` 含 admin/root |
| 禁止模型调用 | `disable-model-invocation: true` |
| 禁止用户直接运行 | `user-invocable: false` |
| 二进制技能 | 目录放可执行文件 + manifest/入口，`action=run` |
| 脚本动作 | `action` 以 `scripts/` 开头（走白名单） |

### 调试技巧

```python
from butler.core.tool_bridge import get_tools
tools = get_tools()          # read / write / edit / bash...
```

- 技能内部可复用 `package/` 能力；
- 不要在技能里重复实现已有能力；
- 单测参考 `tests/unit/test_skill_manager.py`、`tests/unit/test_skill_compat.py`。

## 18.2 新增一个 BHL 混合语言模块

```bash
butler hybrid new image_ops --lang cpp   # c / cpp / go / rust / python
butler hybrid build image_ops
butler hybrid call ping --module image_ops
```

生成器（`butler/core/hybrid_scaffold.py`）会写好：
- `manifest.json`（language/build/executable/methods）
- 最小 stdio worker（`ping` / `echo` / `exit`）

### 手动接入规范

1. 在 `programs/<module>/manifest.json` 声明 `name/language/protocol/executable/methods/build`。
2. 实现 stdio JSON-RPC worker：
   - 从 stdin 逐行读 JSON 请求；
   - 在 stdout 输出 `{"jsonrpc":"2.0","id":...,"result":...}`；
   - 事件（无 id）可主动推送。
3. 关键方法建议在 `butler/core/hybrid_fallbacks.py` 提供 Python 回退。
4. 运行 `butler hybrid status` 确认被发现与构建。
5. 单测参考 `tests/unit/test_hybrid_hub.py`。

> 一次性工具可用 `"protocol": "cli"` + `methods: {"count_words": {"argv": ["{path}"]}}`，stdout 即结果。

## 18.3 新增一个意图（旧循环/本地精确执行）

```python
# butler/core/intents/my_intents.py
from butler.core.intent_dispatcher import register_intent

@register_intent("my_intent", source="llm")
def handle_my_intent(container, entities, **kwargs):
    """一句话描述（会用于本地相似度匹配）。"""
    nlu = container.resolve("nlu_service")
    return "完成"
```

1. 在 `butler/core/intents/__init__.py` 中导入该模块以触发注册。
2. `source="llm"` 表示由 LLM 返回的 intent 名分发；`source="local"` 供本地调用。
3. 返回字符串/字典会成为观察结果；异常会被弹性层捕获。
4. 若需要 `butler_app`，直接声明参数 `butler_app`（由分发器注入）。

> 新架构下更推荐把能力做成**技能/工具**，让 LLM 自主调用，而不是新增意图。

## 18.4 新增内置工具（AgentRuntime）

1. 在 `butler/core/agent_runtime/builtin_tools.py` 写 `_register_xxx_tool(registry, ws_root)`：
   - 用 `registry.register(name=..., description=..., parameters=..., handler=..., permission=...)`；
   - 路径必须经 `_safe_path()` 校验，限制在 workspace 内；
   - 选择合适的 `PermissionLevel`。
2. 在 `register_builtin_tools()` 中调用它。
3. 若工具会访问外部系统/写操作，确保危险命令被拒绝。
4. 单测参考 `tests/unit/test_builtin_file_tools.py`。

## 18.5 新增 AI 提供商

1. 在 `butler/core/config_model.py` 的 `PROVIDER_DEFAULTS` 追加 `provider: {base_url, model_name, key_env, display_name}`。
2. 在 `butler/core/llm_providers.py` 的 `_PROVIDER_TABLE` 追加同样的端点和模型。
3. 在 `package/core_utils/config_loader.py` / `config.yaml` 的 `api.*` 中增加对应 key 字段（或复用 `custom`）。
4. 在 `.env.example` 与 `docs/start/env-reference.md` 补充变量说明。
5. 验证：`butler config check`、`butler doctor`。

## 18.6 代码规范

| 规范 | 说明 |
| :--- | :--- |
| Python 版本 | ≥ 3.10；使用 `from __future__ import annotations` |
| 行宽 | 100（ruff，E501 忽略） |
| 导入顺序 | ruff isort，首方 `butler` |
| 类型 | 新核心模块遵循 mypy strict；存量渐进 |
| 注释 | 中文注释 + 标准 docstring（仓库约定） |
| 重依赖 | 函数内延迟导入 + `try/except ImportError` 降级 |
| 安全 | 禁止前端 `innerHTML`；URL 校验；密钥走 SecretVault |
| 异常 | 用户可见错误用 `BTL-xxxx`（`butler/core/errors.py`），不要裸 traceback |
| 文件组织 | 能力放 `package/`，系统编排放 `butler/`，避免循环依赖 |

### 完成前自检

```bash
ruff check butler/ tests/
ruff format --check butler/ tests/
mypy butler/core/container.py butler/core/config_model.py \
     butler/core/capability_reporter.py butler/core/code_sandbox.py \
     butler/core/intent_dispatcher.py
PYTHONPATH=. pytest tests/unit/ -q
```

## 18.7 调试与观测

| 工具 | 用法 |
| :--- | :--- |
| 体检 | `butler doctor` |
| 能力矩阵 | 启动日志中的 `CapabilityReporter` 输出 |
| 就绪探针 | `GET /readyz`（Vault/NLU/Runner/熔断） |
| 事件历史 | `event_bus.get_history()`（最近 100 条） |
| 意图指标 | `intent_registry.get_metrics()` / `get_all_intents()` |
| 技能来源 | `python butler_cli.py skill list -j` |
| BHL 状态 | `butler hybrid status` |
| 时光机 | `data/system_data/time_machine.db` / 前端 (0,1) 象限 |
| 日志 | `logs/`、`data/security_audit.log` |

## 18.8 常见陷阱

1. **两套记忆/工作流**：确认你改的是桌面主程序路径还是 `ButlerRuntime` 路径（见 [09](./09-memory.md)、[15](./15-dependencies.md)）。
2. **静默降级**：大量 `try/except` 会吞异常；新增能力务必通过 `CapabilityReporter`/日志显式暴露状态。
3. **技能返回值**：应返回字符串或含 `status` 的字典；`pending_confirmation`/`pending_resource` 会被特殊处理。
4. **权限**：写操作/危险命令必须声明 `REQUIRE_CONFIRM`/`NEVER_ALLOW`；不要绕过权限系统。
5. **BHL 回退**：不要把 `via="fallback"` 误认为原生成功；需要原生能力时确保工具链可用。
6. **前端 XSS**：用户数据一律 `textContent` 或 `escapeHTML()`。

## 18.9 相关章节

- 技能细节：[07 技能系统](./07-skills.md)
- BHL 细节：[08 BHL 混合链路](./08-bhl.md)
- Agent 工具：[05 Agent 运行时](./05-agent-runtime.md)
- 测试/CI：[16 运行、部署与测试](./16-deployment-testing.md)
