# Agent 能力：子代理 / 长期记忆 / 主动代理 / MCP

这次给 Butler 的 AgentRuntime 补了四块能力，全部默认可用（MCP 需配置 server）。

## 1. 子代理与多智能体协作

主 Agent 拥有 `task` 工具，可以把有边界的子任务委派给隔离子代理：

* `explorer`：只读探索代码库（read/grep/glob/ls），返回文件与结论
* `reviewer`：只读代码审查，按 blocker / should-fix / nit 输出
* `worker`：执行型，改代码、跑测试，30 轮上限

```
task(prompt="找出 BHL hub 的实现位置", agent="explorer")
list_subagents()
```

自定义子代理：把 Markdown + YAML frontmatter 放到 `.butler/agents/` 或
`~/.butler/agents/`，格式与 Claude Code subagent 一致。子代理拥有独立上下文、
独立工具白名单和独立权限（不会继承父级的 bypass）。

## 2. 长期记忆（经验沉淀与召回）

每次任务结束，Agent 会把「任务 → 结果 → 状态 → 用到的工具」写入：

* SQLite `agent_experiences` 表（与 tasks 同库）
* `butler/data/butler_memory/MEMORY.md`（可读，保留最近 2000 行）

下次执行任务前，按关键词重叠召回最多 `agent.memory_limit` 条相关经验，作为
system message 注入。配置：

```yaml
agent:
  memory: true
  memory_limit: 3
  # memory_file: butler/data/butler_memory/MEMORY.md
```

## 3. 主动代理（定时任务）

```bash
butler agent schedule add "检查下载目录并整理归档" --every 2h --name 下载整理
butler agent schedule list
butler agent schedule run <job_id>      # 立即执行一次
butler agent schedule disable <job_id>
butler agent schedule remove <job_id>
butler agent schedule daemon            # 前台运行调度循环
```

任务持久化在 SQLite `agent_jobs` 表；后台线程按 `next_run` 轮询执行，
每次执行记录 `last_status` / `last_output`。`butler` 启动时自动拉起调度器：

```yaml
agent:
  scheduler_autostart: true   # 默认 false，避免后台静默消耗额度
```

## 4. MCP 工具接入

配置 MCP stdio server 后，Agent 自动获得 `mcp_<server>_<tool>` 工具：

```yaml
mcp:
  servers:
    - name: filesystem
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/root/workspace"]
```

也支持 `~/.butler/mcp.json`：

```json
{"servers": [{"name": "github", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"], "env": {"GITHUB_TOKEN": "..."}}]}
```

实现不依赖官方 `mcp` 包：通过子进程 stdio 完成 `initialize → tools/list →
tools/call`，工具参数使用 server 自己声明的 `inputSchema`。连接失败只记日志，
不会阻断 Agent 启动。
