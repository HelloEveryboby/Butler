# Butler · 项目简介

> 本地优先（Local-First）的 AI 数字员工操作系统：把大模型、混合编程模块、桌面/终端/Web 界面和插件生态编排成一个可长期运行的个人工作平台。
>
> 仓库：<https://github.com/HelloEveryboby/Butler> ｜ 版本：`2.0.0` ｜ 分支：`main`（当前提交 `f6ee9d5`）｜ Python `>=3.10`

---

## 一句话介绍

Butler 不只是一个聊天机器人，而是一套"能力操作系统"：同一份功能实现，同时暴露给 **CLI、TUI、Web、REST API 和 AI 大模型工具调用**，人怎么操作、AI 就怎么操作，语义完全一致。

## 核心特性

| 特性 | 说明 |
| :--- | :--- |
| 混合编程（BHL） | 通过 `HybridHub / HybridLink` 把 C / C++ / Go / Rust 模块接入同一条 JSON-RPC 链路，重计算可下沉到原生代码，缺工具链时自动回退 Python |
| 双轨能力体系 | **核心能力注册表**承载内置一等功能；**Skills** 只负责可插拔扩展与第三方插件，二者同时注册为 LLM 工具，模型按功能名单自由选择 |
| 多入口一致 | 一个动作只有一份业务实现；命令行、终端 UI、Web 前端、REST 与 AI 工具共用同一能力声明，避免行为漂移 |
| 本地优先记忆 | Redis → Zvec → SQLite 多级降级，离线可用；另有短期/长期记忆、习惯库与"做梦"整合 |
| KAIROS 自动化 | 做梦引擎、自愈系统、主动代理、专注模式、Cron、集群，支持后台自主工作 |
| 插件生态 | 直接消费 dsh / Claude Code 插件包（声明式资产），支持 MCP，无需安装 dsh 官方软件 |

## 内置核心能力（11 项）

| 能力 | 功能 | 命令行入口 |
| :--- | :--- | :--- |
| `reading` 朗读 | 任意可显示文本与多种文档格式（txt/md/docx/pdf/网页）朗读；小说对白自动分角色男/女声、按语境调节语速与停顿、读到哪里用颜色框标出、关闭后从上次位置续读 | `butler read` |
| `scanner` 文档扫描 | 本地文件或拍照转电子版；透视矫正、去阴影；彩色笔迹保留，支持彩色/灰度/黑白/铅笔/碳笔模式；单页默认输出 PDF，可继续转换格式 | `butler scan` |
| `versioning` 版本管理 | 文稿、PDF、Word 每次保存自动建立 Git 记录点，按时间点查看前后 diff、回滚；图片与视频走内容寻址的制品版本库 | `butler version` |
| `commands` 命令记录器 | Linux/GNU 风格标准命令目录，分门别类并标注用途；AI 执行前先查标准命令，未记录或高频命令自动补录 | `butler cmd` |
| `dsh` 插件市场 | 搜索、安装、启停 dsh 插件；支持本地目录、zip/tar、git、npm 包与市场索引 | `butler dsh` |
| `documents` 文档工具 | MarkItDown、DOCX/PDF 处理、格式转换、Excel 重算、反向转换 | `documents` 能力 / TUI |
| `audio` 语音音频 | 语音识别、语音服务、AI 实时字幕 | `audio` 能力 |
| `skills_admin` 技能管理 | 创建、发现、同步技能，维护技能锁文件 | `skills_admin` 能力 |
| `media` 媒体 | 视频/音乐播放、媒体管理、压缩转码、截图录屏 | `media` 能力 |
| `system` 系统维护 | 清理、卸载、压缩归档、存储中心、安全测试 | `system` 能力 |
| `network` 网络传输 | 下载、Aria2 管理、云盘挂载、媒体嗅探 | `network` 能力 |

> 其余第三方厂商集成、实验功能与开发辅助仍以 **Skills** 形式存在（当前 22 个），保持"内置 = 能力，扩展 = 技能"的分工。

## 架构速览

```text
入口层   CLI · TUI · Tkinter/Webview · REST API · AI Function Calling
            │
编排层   Butler 主编排器 · AgentRuntime 工具循环 · 意图分发 · 工作流
            │
能力层   核心能力注册表（11 项）  +  Skills 技能系统（可插拔）
            │
服务层   记忆 · 语音 · 文档 · 媒体 · 网络 · 系统 · 事件/消息总线
            │
混合层   BHL：C / C++ / Go / Rust 原生模块 + Python 回退
```

## 快速开始

```bash
git clone https://github.com/HelloEveryboby/Butler.git
cd Butler
pip install -r requirements.txt

# 启动主程序（默认 TUI）
python -m butler

# 或仅使用命令行
butler read novel.docx --play
butler scan ./photo.jpg --mode color -o out.pdf
butler version save report.docx -m "第二稿"
butler cmd search 朗读
butler dsh search pdf
```

更多运行方式（GUI / Web / headless / REST）与配置说明见 `docs/` 与 Code Wiki。

## 质量保障

- 新增 10 个测试文件，覆盖能力注册表、朗读文本解析、扫描、版本库、命令记录器及三类新迁移能力
- CI：`ruff`（行宽 100）、核心模块 `mypy`、`pytest tests/unit`
- 重依赖一律延迟导入并降级，精简环境可运行核心链路

## 适用场景

- 长时间听书 / 听网页 / 听文档，且要求对白有角色感与断点续听
- 纸质笔记、彩色勾画、素描铅笔稿的电子化与格式流转
- 文稿与多媒体文件的高频改稿留痕、对比与回滚
- 希望"人用的命令"与"AI 用的命令"完全统一的自动化工作台
- 想直接复用 dsh / Claude 插件生态，而不引入额外官方运行时
