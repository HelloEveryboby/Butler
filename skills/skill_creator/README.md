# Skill Creator (技能创建助手)

这是一个用于快速生成符合 Butler 规范的新技能模板的内置工具。

## 功能特性

- **一键生成**：自动创建技能目录及核心文件。
- **规范模板**：生成的模板包含 `manifest.json`, `__init__.py`, `README.md` 和 `requirements.txt`。
- **自动激活**：创建完成后自动在 `skills-lock.json` 中启用。

## 动作 (Actions)

### `create`
创建一个新的技能模板。

**参数：**
- `skill_id` (必选): 技能的唯一标识符（如 `my_new_skill`）。
- `name` (可选): 技能的显示名称。
- `description` (可选): 技能的功能描述。

## 使用示例

### 通过代码调用
```python
skill_manager.execute("skill_creator", "create", skill_id="weather_report", name="天气预报")
```

### 通过 CLI (重构后的 create_skill.py)
```bash
python scripts/create_skill.py
```
