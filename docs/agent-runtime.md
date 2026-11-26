# 原生 Agent 运行时（AgentRuntime）

Butler 现在用 **LLM 原生 tool calling 循环**执行任务，而不是「意图分类 + 字典派发」。
本文说明改了什么、怎么配置、怎么验证。

## 之前的问题

| 路径 | 旧行为 |
| --- | --- |
| `butler agent run` | `butler/agent/` 的 Planner 按关键词返回硬编码三步；Executor 找不到包就返回拟真假文本；第一步就 `该包被禁用` |
| 聊天主循环 | `Butler._autonomous_agent_loop` 让 LLM 输出 intent + entities，再查表派发；LLM 不能自主连续调用工具 |
| `AgentRuntime` | 实现完整（循环/权限/子代理/MCP/压缩），但 `ButlerAgentBridge` 从未被实例化，且 `_create_llm_handler()` 漏了 `return handler`，等于永远拿不到 LLM |

## 现在的结构

```text
用户输入
   │
   ├─ Butler 聊天 ──► ButlerAgentBridge ─┐
   │                                     ├─► AgentRuntime 循环
   └─ butler agent run ──► Agent ────────┘        │
                                                  ├─ LLM（OpenAI 兼容：DeepSeek/OpenAI/Ollama…）
                                                  ├─ 工具：read/write/edit/bash/glob/grep…
                                                  ├─ 工具：Butler 技能（calculator、xlsx_recalc…）
                                                  └─ 每轮 tool 结果回灌 → 继续，直到 end_turn
```

* `butler/core/agent_runtime/skill_tools.py`：把 `SkillManager` 的技能注册成标准工具
  （名字清洗、`action`/`kwargs` 参数透传、`entities` 兼容旧式技能、结果收敛）。
* `butler/agent/agent.py`：`Agent.run_task` 直接驱动 `AgentRuntime`，任务状态写入
  SQLite `tasks` 表（表缺失时自动补建）。
* `butler/core/agent_runtime/butler_adapter.py`：技能工具注入、权限模式、系统提示词、
  `echo_assistant` 开关；修复 LLM 回调未返回的 bug。
* `butler/butler_app.py`：`Butler.__init__` 创建 `agent_bridge`；`_autonomous_agent_loop`
  优先走新运行时，异常时自动回退旧流程。

## 配置（`config/config.yaml`）

```yaml
agent:
  runtime: true            # 聊天主路径使用 AgentRuntime
  max_turns: 25            # 单任务最大轮次
  max_skill_tools: 40      # 注册为工具的技能上限，0 = 不限制
  permission_mode: default # default | accept_edits | auto | plan | bypass_permissions
  auto_confirm: true       # 无 UI 时自动批准非只读工具（自毁命令始终拒绝）
  expose_intents: false    # 额外把意图处理器注册为工具
```

技能工具默认是 `require_confirm`：GUI 走原有确认弹窗，headless/CLI 由
`auto_confirm` 决定，`rm -rf /`、`mkfs`、`dd if=` 等命令永远拒绝。

## 验证

```bash
# 单元 + e2e（174 个 Agent 相关用例）
python -m pytest tests/unit/test_agent_native_loop.py \
    tests/unit/test_agent_runtime_context.py \
    tests/unit/test_agent_runtime_tools.py \
    tests/integration/test_agent_runtime_e2e.py -q

# 真实跑一个任务（需要已配置 LLM）
butler agent run supervisor "把当前目录的 Python 文件列出来并统计行数"
```

输出会显示 `任务状态 / 轮次 / 工具调用链 / 成果汇报`，同时写入 `tasks` 表。

## 已知限制

* 必须有可用的 LLM 提供商；没有 Key 时 `butler agent run` 会明确报错，不会再假装完成。
* 技能是否可执行取决于其依赖是否安装；缺依赖时工具会返回真实错误，由 LLM 决定换方案。
* 40 个技能工具 + 11 个内置工具会让首轮请求偏大；可用 `agent.max_skill_tools` 限流，
  或用 `agent.expose_intents` 控制是否再叠加意图工具。
