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

## 开发者提示
如果你想编写自己的技能，可以参考 `skills/skill_creator` 或使用对话命令：“帮我创建一个新技能框架。”
