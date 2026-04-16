# Butler Skill 开发标准规范 (v1.0)

为了确保 Butler (Jarvis) 系统的插件化生态具备高度的可维护性、安全性和一致性，所有技能 (Skills) 必须遵循本标准规范。

## 1. 目录结构标准
每个技能必须是一个独立的文件夹，放置在 `skills/` 目录下，且文件夹名称即为 `skill_id`。
```text
skills/<skill_id>/
├── manifest.json       # 技能元数据 (必须)
├── README.md           # 中文说明文档 (必须)
├── requirements.txt    # Python 依赖声明 (必须，无依赖则留空)
└── __init__.py         # 技能核心逻辑入口 (必须)
```

## 2. 配置文件标准 (manifest.json)
必须包含以下字段：
- `skill_id`: 技能唯一标识符（建议小写下划线命名）。
- `name`: 技能显示名称。
- `version`: 版本号 (语义化版本)。
- `description`: 技能功能简述。
- `entry_point`: 入口文件路径。
- `actions`: 暴露的动作列表。
- `keywords`: 唤起关键词。

示例：
```json
{
  "skill_id": "example_skill",
  "name": "示例技能",
  "version": "1.0.0",
  "description": "这是一个标准化的示例技能。",
  "entry_point": "skills/example_skill/__init__.py",
  "actions": ["action1", "action2"],
  "keywords": ["example", "demo"]
}
```

## 3. 文档标准 (README.md)
必须使用中文编写，且包含以下固定章节：
1. **定位**: 一句话描述该技能在系统中的角色。
2. **核心功能**: 列出该技能支持的具体功能点。
3. **指令集**: 详细说明如何通过自然语言或命令调用该技能的各个 Action。
4. **安全与权限**: 说明该技能是否涉及提权操作（如 `request_permission`）或高危脚本执行。
5. **环境依赖**: 运行该技能所需的外部工具（如 Docker, nmap）或硬件条件。

## 4. 代码标准 (__init__.py)
- **基类继承**: 建议继承 `butler.core.base_skill.BaseSkill` 以获得授权和审计能力。
- **入口函数**: 必须提供 `handle_request(action, **kwargs)` 函数。
- **中文注释**: 所有公共方法和核心逻辑必须包含详尽的中文 Docstring 和注释。
- **动态执行**: 任何自发生成的代码必须通过 `execute_dynamic_script` 执行以确保审计合规。

## 5. 安全准则
- 严禁在未经 `request_permission` 授权的情况下修改 `skills/` 目录以外的系统文件。
- 所有动态生成的临时文件或脚本必须在任务结束后清理，或保留在 `data/audit_logs` 中。
