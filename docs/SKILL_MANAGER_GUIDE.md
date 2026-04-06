# Butler 技能管理器与 MarkItDown 技能指南

本文档介绍了 Butler 系统新引入的**技能管理器 (Skill Manager)** 以及重构后的 **MarkItDown 技能**。

## 1. MarkItDown 技能

`markitdown` 现在已正式成为 Butler 的一个内置技能。它可以将多种格式的文档（PDF, Word, Excel, PPT, HTML, ZIP, EPub 等）精准转换为 Markdown 格式，便于 AI 分析和处理。

### 使用方法
您可以通过对话直接触发转换：
- “帮我把桌面上的 `report.pdf` 转换为 markdown。”
- “转换 `data.xlsx` 到 markdown 格式。”

## 2. 技能管理器 (Skill Manager)

技能管理器允许您管理 Butler 的扩展功能，支持从远程 Git 仓库下载并安装新的技能。

### 主要功能
- **在线安装**：通过 Git 链接一键安装第三方技能。
- **依赖自理**：安装时自动检测并运行 `pip install -r requirements.txt`。
- **卸载管理**：安全卸载不再需要的技能。
- **状态列表**：查看当前所有已安装技能的描述和启用状态。

### 在线安装示例
您可以对 Butler 说：
- “从 `https://github.com/example/new-skill` 安装技能。”

## 3. 前端界面 (Modern UI)

技能管理功能已集成到 **设置 (Settings)** 界面中。

![技能管理界面](../assets/ui_screenshots/settings_skills.png)

### 操作步骤
1. 点击左侧导航栏的 **设置** 图标。
2. 在 **技能管理** 区域，输入技能的 Git 仓库链接。
3. 点击 **安装** 按钮。
4. 安装完成后，点击 **刷新列表** 即可看到新安装的技能。

---
*注：由于系统安全策略，部分核心技能（如 markitdown, task_management）不允许通过界面卸载。*
