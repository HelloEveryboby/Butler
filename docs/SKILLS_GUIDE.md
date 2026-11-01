# Butler 技能系统使用指南

Butler 支持强大的“即插即用”技能扩展系统。你可以轻松地将其他人编写的技能集成到你的 Butler 中。

## 如何安装新技能

### 1. 手动投放 (最简单)
如果你得到了一个技能文件夹或 `.zip` 压缩包：
- 将该文件夹或 `.zip` 文件直接放入项目根目录下的 `skills/` 文件夹中。
- Butler 会自动检测、解压 (如果是 zip) 并加载该技能。

### 2. 通过对话命令安装
你可以直接对 Butler 说：
- “帮我从 URL 安装这个技能：`https://github.com/user/my-skill.git`”
- “导入位于 `/path/to/my-skill` 的本地技能。”

### 3. CLI 安装
使用命令行工具安装：
```bash
python butler_cli.py manage_skills install --url <git_url>
```

## 技能目录结构要求
一个有效的技能通常包含以下文件之一：
- `SKILL.md`: (推荐) 包含技能描述和 AI 调用指令。
- `manifest.json`: 传统元数据定义。
- `__init__.py` 或 `main.py`: 技能的 Python 执行逻辑。
- `requirements.txt`: 技能所需的依赖包 (Butler 会自动安装)。

## 技能发现根目录与优先级

Butler 兼容 DeepSeek Harness (dsh) 与 Claude Code 的标准 Agent Skills 布局。启动时按以下顺序发现技能，**同名技能由先出现的根目录接管** (first-wins)：

| 优先级 | 来源 | 路径 | 发现规则 |
| --- | --- | --- | --- |
| 0 | Butler 原生 | `<项目>/skills/` | 支持分类子目录 (深度 2) 与扁平 `.md` |
| 50-52 | 插件包 | `<项目>/plugins/<plugin>/` | `skills/`、`commands/`、`agents/` |
| 100 | dsh 项目级 | `<项目>/.dsh/skills/` | 仅直接子项 |
| 200 | Agents 项目级 | `<项目>/.agents/skills/` | 仅直接子项 |
| 210 | Claude 项目级 | `<项目>/.claude/skills/` | 仅直接子项 |
| 400 | dsh 用户级 | `~/.dsh/skills/`（可用 `DSH_HOME` 覆盖） | 仅直接子项 |
| 500 | Agents 用户级 | `~/.agents/skills/`（可用 `DSH_AGENTS_HOME` 覆盖） | 仅直接子项 |
| 510 | Claude 用户级 | `~/.claude/skills/` | 仅直接子项 |

外部根支持两种形态：目录 bundle (`<name>/SKILL.md`) 与扁平文件 (`<name>.md`)。查看当前生效的根目录：

```bash
python butler_cli.py skill roots
```

## 调用可见性 (dsh 兼容)

`SKILL.md` frontmatter 支持 dsh 的调用策略字段：

```yaml
---
name: my-skill
description: ...
disable-model-invocation: true   # 模型不可见（不会进入系统提示词/Function Calling）
user-invocable: false            # 用户不可直接运行 (skill run 会被拒绝)
---
```

布尔值接受 `true/false/yes/no/on/off/1/0`。使用 camelCase 拼写（如 `disableModelInvocation`）或非法布尔值会导致该技能整体失效。

## 插件包导入 (dsh / Claude Code)

Butler 采用**导入式兼容**：解析插件包中的声明式资产并导入技能系统，**不会执行 Cordis 的 TS/JS 运行时代码**。

识别的格式：

- dsh 包：`package.json` 中的 `"dsh": {"bundle": {"patch": "./cordis.patch.yml"}}`
- Claude 插件：`.claude-plugin/plugin.json`
- 资产目录：`skills/`、`commands/`、`agents/`（`commands`/`agents` 中的扁平 `.md` 会以 `<plugin>-<name>` 前缀注册）
- `hooks/hooks.json`、`.mcp.json` 仅记录在插件元数据中，不会被自动执行

```bash
# 安装（支持本地目录 / zip / tar / git / npm 包名）
python butler_cli.py plugin add ./my-plugin
python butler_cli.py plugin add https://github.com/owner/repo.git
python butler_cli.py plugin add @scope/pkg --force

python butler_cli.py plugin list
python butler_cli.py plugin info my-plugin
python butler_cli.py plugin remove my-plugin
```

插件安装到 `plugins/<name>/`，元数据写入 `.butler-plugin.json`。也可直接把插件目录放入 `plugins/`，Butler 会自动识别。

## CLI 速查

```bash
python butler_cli.py skill list            # 列出全部技能（含来源）
python butler_cli.py skill list -j         # JSON 输出 source / 可见性
python butler_cli.py skill info <id>       # 查看来源、调用策略与指令
python butler_cli.py skill run <id>        # 运行 USER 技能
python butler_cli.py skill uninstall <id>  # 卸载 skills/ 下的原生技能
python butler_cli.py skill roots           # 查看发现根目录
```

## 开发者提示
如果你想编写自己的技能，可以参考 `skills/skill_creator` 或使用对话命令：“帮我创建一个新技能框架。”
