# 备忘录技能 (Memos Skill)

这是一个仿 [usememos/memos](https://github.com/usememos/memos) 项目开发的备忘录模块，支持文字、图片、视频、音频以及 Markdown 编辑。

## 功能特性

- **多模态支持**：支持存入文字、图片、视频和音频文件。
- **Markdown 渲染**：Web 界面支持 Markdown 语法的即时预览。
- **时间轴视图**：在 Web 界面以时间轴形式展示备忘录。
- **混合架构**：
    - **Go 后端**：使用 SQLite 数据库，确保高性能的数据检索和持久化。
    - **TypeScript 前端**：提供流畅的交互体验，支持拖拽上传。
    - **Python 桥梁**：无缝集成到 Butler 技能系统。
- **C 语言终端适配**：在 `bcli` 命令行界面中支持以精美的卡片形式输出备忘录。
- **标签与搜索**：支持 `#标签` 语法和全局关键词搜索。

## 安装要求

- 已编译的 Go 后端二进制文件 (`programs/hybrid_memos/memos_service`)。
- `github.com/mattn/go-sqlite3` 驱动。

## 目录结构

- `skills/memos/`：Python 技能核心代码。
- `programs/hybrid_memos/`：Go 后端源代码及服务。
- `data/memos/`：存储 SQLite 数据库和多媒体附件。
- `frontend/view/memos.js`：前端展示逻辑。

## 使用方法

### 通过对话
- “帮我记一下，今天的天气真不错 #心情”
- “显示我最近的备忘录”
- “搜索关键词：天气”

### 通过 Web 界面
1. 打开 Butler Modern UI。
2. 点击侧边栏的“备忘录”图标。
3. 点击“新建备忘录”开始记录。
4. 支持将文件直接拖入编辑区上传。

### 通过命令行 (bcli)
在终端中输入命令，Butler 将以卡片形式返回备忘录内容。

## 开发者
由 Butler AI 驱动。
