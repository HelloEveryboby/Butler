# Butler 用户使用指南

> 本文档是 Butler 的**唯一使用入口**，覆盖从安装后第一次启动到熟练运用全部能力的完整路径。
> 安装请走 [安装与启动指南](./start/install.md)；本指南假设你已经能运行 `butler doctor` 并通过体检。

---

## 目录

1. [三种交互方式，选一个顺手的](#1-三种交互方式)
2. [快速上手：安装后必做的 5 件事](#2-快速上手安装后必做的-5-件事)
3. [CLI 命令完整参考](#3-cli-命令完整参考)
4. [TUI 斜杠命令速查](#4-tui-斜杠命令速查)
5. [技能使用指南](#5-技能使用指南)
6. [自然语言交互示例](#6-自然语言交互示例)
7. [常见问题与排查](#7-常见问题与排查)

---

## 1. 三种交互方式

Butler 提供三种互补的交互方式，底层共享同一套功能模块：

| 方式 | 命令 | 适合谁 | 特点 |
| :--- | :--- | :--- | :--- |
| **TUI 终端界面** | `butler`（默认）或 `butler tui` | 日常使用、键盘党 | 玻璃拟态终端 UI，支持斜杠命令 + 自然语言对话 |
| **Web / 桌面 UI** | `butler web` | 偏好图形界面 | 2×2 矩阵空间，鼠标操作，可视化 DAG |
| **CLI 命令行** | `butler <子命令>` | 脚本自动化、远程 | 纯命令行，可嵌入 shell 脚本 / cron |

> 💡 **新手建议**：先 `butler init` 完成配置 → `butler tui` 体验对话和斜杠命令 → 熟悉后再用 `butler <子命令>` 写脚本。

---

## 2. 快速上手：安装后必做的 5 件事

### ① 首次配置（3 分钟）

```bash
butler init
```

交互式向导会引导你：选择 AI 服务商 → 填入 API Key → 自动校验连通性 → 给出示例任务。
跳过连通性校验：`butler init --skip-check`。

### ② 系统体检

```bash
butler doctor
```

输出会标明每一项的健康状态和「下一步建议」。任何依赖缺失、配置错误都能在这里发现。

### ③ 启动 TUI 并试一个命令

```bash
butler tui
```

进入界面后，在输入框输入斜杠命令试试：

```
/weather 上海
/encrypt ./secret.txt
/markitdown ./report.pdf
/skill_run calculator
```

输入 `/commands` 可浏览全部命令，输入 `/howto 我想查天气` 让 Butler 帮你找命令。

### ④ 浏览已安装技能

```bash
butler skill list
```

会区分 🐍 可调用技能（有 Python 入口，用户可直接运行）和 📖 Agent 技能（纯 SKILL.md 指令集，由 AI 调用）。

运行一个可调用技能：

```bash
butler skill run calculator
butler skill run format_convert --input readme.md --format docx
```

### ⑤ 用自然语言完成一个真实任务

在 TUI 对话中直接说中文，例如：

> 把当前目录下的 report.pdf 转成 Word 文档

Butler 会自动识别意图、调用对应技能并返回结果。

---

## 3. CLI 命令完整参考

所有命令统一入口都是 `butler`，无需记忆 `butler_cli.py` 或 `python -m butler`。

### 3.1 界面与服务管理

| 命令 | 说明 | 示例 |
| :--- | :--- | :--- |
| `butler` | 默认启动 TUI | `butler` |
| `butler tui` | 启动终端界面 | `butler tui` |
| `butler gui` | Tkinter 经典桌面界面 | `butler gui` |
| `butler web` | pywebview 现代桌面界面 | `butler web` |
| `butler headless` | 无头模式（后台 + API） | `butler headless --port 5001` |
| `butler start` / `butler api` | 启动 REST API 网关 | `butler start --port 5001` |
| `butler init` | 首次配置向导 | `butler init --skip-check` |
| `butler config` | 交互式配置 AI 服务商 | `butler config` |
| `butler config show` | 查看当前 AI 配置 | `butler config show` |
| `butler config check` | 配置健康检查 | `butler config check` |
| `butler doctor` | 系统诊断自检 | `butler doctor` |

### 3.2 数字员工与包管理

| 命令 | 说明 | 示例 |
| :--- | :--- | :--- |
| `butler agent list` | 列出可用数字员工角色 | `butler agent list` |
| `butler agent run <角色> <任务>` | 委派任务给员工 | `butler agent run demo-agent "读取报价并整理汇报"` |
| `butler package list` | 列出已安装包 | `butler package list` |
| `butler package install <路径>` | 安装本地技能包 | `butler package install ./my_skill` |

### 3.3 功能型命令（脚本友好）

| 命令 | 说明 | 示例 |
| :--- | :--- | :--- |
| `butler crawl --url <url>` | 爬取网页内容 | `butler crawl --url https://example.com` |
| `butler crawl --query <关键词>` | 搜索并爬取 | `butler crawl --query "Python 教程"` |
| `butler email --send --to <收件人> --subject <主题> --body <正文>` | 发送邮件 | `butler email --send --to a@b.com --subject 开会 --body 明天3点` |
| `butler email --receive` | 收取未读邮件 | `butler email --receive` |
| `butler image-search --query <关键词>` | 搜索网络图片 | `butler image-search --query 猫咪` |
| `butler encrypt --path <文件> --algo AES\|DES` | 对称加密文件 | `butler encrypt --path secret.txt --algo AES` |
| `butler decrypt --path <文件.enc> --algo AES\|DES` | 解密文件 | `butler decrypt --path secret.txt.enc --algo AES` |
| `butler weather <城市>` | 实时天气查询 | `butler weather 北京` |
| `butler convert --input <in> --output <out>` | 文档格式转换 | `butler convert --input a.pdf --output a.docx` |
| `butler translate --text <文本>` | 翻译文本 | `butler translate --text "Hello"` |
| `butler translate --file <文件>` | 翻译文件 | `butler translate --file readme.md` |
| `butler translate --url <网页>` | 翻译网页 | `butler translate --url https://example.com` |
| `butler monitor` | 系统健康监控报告 | `butler monitor` |
| `butler audit --dir <目录>` | 目录安全审计 | `butler audit --dir ./` |
| `butler audit --security` | 系统安全自检并生成报告 | `butler audit --security` |
| `butler dependency install_all` | 安装全部依赖 | `butler dependency install_all` |
| `butler dependency install --package <包名>` | 安装指定依赖 | `butler dependency install --package requests` |
| `butler file --op create --path <路径> --content <内容>` | 创建文件 | `butler file --op create --path a.txt --content hi` |
| `butler file --op read --path <路径>` | 读取文件 | `butler file --op read --path a.txt` |
| `butler file --op delete --path <路径>` | 删除文件 | `butler file --op delete --path a.txt` |
| `butler file --op list --path <目录>` | 列出目录 | `butler file --op list --path ./` |
| `butler download <url> [-o 输出目录] [-d 守护进程]` | 资源下载 | `butler download https://x.com/file.zip -o ./downloads` |

### 3.4 技能管理

| 命令 | 说明 | 示例 |
| :--- | :--- | :--- |
| `butler skill list` | 列出全部技能（区分 USER/AGENT） | `butler skill list` |
| `butler skill list -t user` | 仅列出可调用技能 | `butler skill list -t user` |
| `butler skill list -j` | JSON 输出（供脚本） | `butler skill list -j` |
| `butler skill info <技能ID>` | 查看技能详情 | `butler skill info format_convert` |
| `butler skill run <技能ID> [action] [--key value]` | 运行可调用技能 | `butler skill run calculator` |
| `butler skill install --url <SKILL.md URL>` | 从远程安装技能 | `butler skill install --url https://.../SKILL.md` |
| `butler skill install --path <本地目录>` | 从本地目录安装 | `butler skill install --path ./my_skill` |
| `butler skill uninstall <技能ID>` | 卸载原生技能 | `butler skill uninstall my_skill` |
| `butler skill roots` | 列出技能发现根目录 | `butler skill roots` |
| `butler skills catalog` | 重新生成技能目录 | `butler skills catalog` |

> 提示：技能的完整说明也可运行 `butler skill help` 查看 man page 风格文档。

### 3.5 辅助工具与插件

| 命令 | 说明 |
| :--- | :--- |
| `butler tool list` | 列出内置辅助工具（read/write/edit/bash 等） |
| `butler tool run <工具名> [--key value]` | 执行工具，如 `butler tool run read --path config.yaml` |
| `butler tool info <工具名>` | 查看工具参数与权限 |
| `butler plugin list` | 列出已安装插件 |
| `butler plugin add <插件>` | 安装插件 |
| `butler plugin info <插件>` | 查看插件详情 |
| `butler plugin remove <插件>` | 卸载插件 |

---

## 4. TUI 斜杠命令速查

在 TUI 输入框中以 `/` 开头即可调用斜杠命令，支持中文别名和模糊匹配。
输入 `/commands` 浏览全部，`/howto <描述>` 按意图推荐。

### 🌐 网络

| 命令 | 别名 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `/weather <城市>` | `wt` / `天气` | 查询天气 | `/weather 上海` |
| `/crawl_url <url>` | `crawl` / `爬` | 爬取网页 | `/crawl_url https://example.com` |
| `/crawl_query <关键词>` | `search` / `搜索` | 搜索并爬取 | `/crawl_query Python教程` |
| `/email_send <收件人> \| <主题> \| <正文>` | `mail` / `发邮件` | 发送邮件 | `/email_send a@b.com \| 通知 \| 明天开会` |
| `/email_recv` | `recv` / `收邮件` | 收取未读邮件 | `/email_recv` |
| `/img_search <关键词>` | `img` / `搜图` | 搜索图片 | `/img_search 猫咪` |
| `/translate <文本>` | `tr` / `翻译` | 翻译文本 | `/translate Hello` |
| `/translate_file <文件>` | `trf` | 翻译文件 | `/translate_file readme.txt` |
| `/translate_url <url>` | `tru` | 翻译网页 | `/translate_url https://example.com` |

### 🔐 安全

| 命令 | 别名 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `/encrypt <文件>` | `enc` / `加密` | AES 加密文件（需输入 6 位核心码） | `/encrypt secret.txt` |
| `/decrypt <文件.enc>` | `dec` / `解密` | 解密文件 | `/decrypt secret.txt.enc` |
| `/audit_security` | `audit` / `审计` | 系统安全审计 | `/audit_security` |
| `/audit_dir <目录>` | `auditdir` | 目录安全审计 | `/audit_dir /home/user` |

### 📄 文档

| 命令 | 别名 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `/convert <输入> -> <输出>` | `cv` / `转换` | 格式转换 | `/convert report.docx -> report.pdf` |
| `/file_create <路径> \| <内容>` | `fc` / `创建文件` | 创建文件 | `/file_create notes.txt \| 笔记内容` |
| `/file_read <文件>` | `fr` / `读取` | 读取文件 | `/file_read config.yaml` |
| `/file_delete <文件>` | `fd` / `删除文件` | 删除文件 | `/file_delete temp.log` |
| `/file_list <目录>` | `fl` / `ls` | 列出目录 | `/file_list /home/user` |

### ⚙️ 系统

| 命令 | 别名 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `/monitor` | `mon` / `监控` | 系统健康监控 | `/monitor` |
| `/dep_install [包名]` | `dep` / `安装依赖` | 安装 Python 包 | `/dep_install requests` |
| `/dep_all` | `depall` / `全量安装` | 安装全部依赖 | `/dep_all` |
| `/doctor` | `doc` / `体检` | 系统诊断自检 | `/doctor` |
| `/skills_list [user\|agent]` | `skills` | 列出技能 | `/skills_list user` |
| `/skill_run <技能ID> [--key value]` | `sr` / `运行技能` | 运行可调用技能 | `/skill_run butler_expert --query 架构` |
| `/skill_info <技能ID>` | `si` / `技能详情` | 查看技能详情 | `/skill_info butler_expert` |

### 🔧 辅助工具

| 命令 | 别名 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `/tool_list` | `tools` / `tl` | 列出辅助工具 | `/tool_list` |
| `/tool_run <工具名> [--key value]` | `tr` / `执行工具` | 执行工具 | `/tool_run read --path config.yaml` |
| `/tool_info <工具名>` | `ti` / `工具详情` | 查看工具参数 | `/tool_info read` |

### 💬 对话与管理

| 命令 | 别名 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `/help [命令名]` | `h` / `?` | 帮助 | `/help encrypt` |
| `/commands [关键词]` | `cmd` / `命令列表` | 浏览全部命令 | `/commands 安全` |
| `/howto <描述>` | `how` / `怎么做` | 按意图推荐命令 | `/howto 我想加密文件` |
| `/status` | `st` / `状态` | 系统状态 | `/status` |
| `/kairos` | `kai` / `性能` | KAIROS 性能调度状态 | `/kairos` |
| `/performance <high\|eco\|normal>` | `perf` / `模式` | 切换性能模式 | `/performance eco` |
| `/dream` | `dr` / `做梦` | 手动触发记忆整合 | `/dream` |
| `/focus [分钟]` | `fo` / `专注` | 专注模式（默认 25 分钟） | `/focus 30` |
| `/focus-stop` | `fostop` | 停止专注 | `/focus-stop` |
| `/clear` | `cl` / `清空` | 清空对话 | `/clear` |
| `/tasks` | `task` / `任务` | 任务看板 | `/tasks` |
| `/team` | `tm` / `团队` | 团队成员 | `/team` |
| `/memory` | `mem` / `记忆` | 记忆库视图 | `/memory` |
| `/profile` | `pf` / `画像` | 用户习惯画像 | `/profile` |
| `/exit` | `quit` / `退出` | 退出 TUI | `/exit` |

### 🧠 记忆

| 命令 | 别名 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `/memory_save <标题> \| <内容> \| [摘要]` | `memsave` | 保存记忆 | `/memory_save 决策 \| 采用 FTS5 \| 完成设计` |
| `/memory_query <关键词>` | `memquery` | 检索长期记忆 | `/memory_query FTS5 架构` |

### 🧰 技能（无需 AI 也可用）

| 命令 | 别名 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `/markitdown <文件>` | `md` / `转markdown` | 文件转 Markdown（PDF/DOCX/PPTX/XLSX/HTML…） | `/markitdown report.pdf` |
| `/docx_read <文件>` | `dr_word` | 读取 Word 文档 | `/docx_read report.docx` |
| `/docx_create <路径> \| <标题> \| <内容>` | `dc_word` | 创建 Word 文档 | `/docx_create new.docx \| 我的文档 \| 正文` |
| `/pdf_extract <文件>` | `pe` | 提取 PDF 文本 | `/pdf_extract paper.pdf` |
| `/pdf_merge <文件1>,<文件2> \| <输出>` | `pm` | 合并 PDF | `/pdf_merge a.pdf,b.pdf \| merged.pdf` |
| `/pdf_split <文件>` | `ps` | 拆分 PDF（每页一个文件） | `/pdf_split large.pdf` |
| `/archive_compress <输出> \| <目标> [\| 密码]` | `ac` / `压缩` | 7z/zip 压缩 | `/archive_compress backup.7z \| /home/user/docs` |
| `/archive_extract <压缩包> [\| 输出目录] [\| 密码]` | `ae` / `解压` | 解压 | `/archive_extract backup.7z \| /tmp/out` |
| `/archive_list <压缩包>` | `al` | 列出压缩包内容 | `/archive_list backup.7z` |
| `/uninstaller [list \| uninstall <名称>]` | `uninst` | 软件管理 | `/uninstaller list` |
| `/sys_clean [track \| clean]` | `clean` / `系统清理` | 系统垃圾清理 | `/sys_clean clean` |
| `/media_scan` | `ms` / `扫描媒体` | 扫描全盘媒体文件 | `/media_scan` |
| `/storage_hub [list \| upload \| download]` | `sh` / `云盘` | 多云盘管理 | `/storage_hub list` |
| `/clip_magic` | `cm` / `剪贴板` | 启动剪贴板智能分类服务 | `/clip_magic` |
| `/clip_history` | `cliphist` | 剪贴板历史 | `/clip_history` |
| `/sec_scan <IP>` | `sscan` / `端口扫描` | SYN 端口扫描 | `/sec_scan 127.0.0.1` |
| `/web_sec_test <URL> [\| recon\|scan\|full]` | `wst` | Web 安全测试 | `/web_sec_test https://example.com` |
| `/format_convert <输入> \| <格式>` | `fc_skill` | Markdown 转 DOCX/EPUB/图片 | `/format_convert readme.md \| docx` |
| `/skill_stop <技能名>` | `skillstop` | 停止后台技能 | `/skill_stop clip_magic` |
| `/skill_status [技能名]` | `skstat` | 技能运行状态 | `/skill_status` |
| `/sys_info` | `sinfo` | 系统硬件与资源信息 | `/sys_info` |
| `/top_procs [\| cpu\|memory]` | `top` | 占用最高的进程 | `/top_procs \| memory` |
| `/cloud_list <云盘ID> [\| 路径]` | `clist` | 列出云盘文件 | `/cloud_list onedrive_1 \| /Documents` |
| `/cloud_search <关键词>` | `csearch` | 跨云盘搜索 | `/cloud_search 报告` |
| `/cloud_transfer <源盘> \| <目标盘> \| <文件>` | `ctransfer` | 跨云盘传输 | `/cloud_transfer onedrive_1 \| webdav_1 \| report.pdf` |
| `/cloud_status <任务ID>` | `cstatus` | 传输任务状态 | `/cloud_status task_123` |
| `/cloud_duplicates` | `cdup` | 查找云盘重复文件 | `/cloud_duplicates` |
| `/track_start` | `tstart` | 安装前快照（追踪变更） | `/track_start` |
| `/track_stop` | `tstop` | 安装后生成差异报告 | `/track_stop` |
| `/track_clean` | `tclean` | 清理追踪到的残留 | `/track_clean` |
| `/uninstall_scan <软件名>` | `uscan` | 扫描卸载残留 | `/uninstall_scan firefox` |
| `/uninstall_do <软件名> [\| dry_run]` | `udo` | 深度卸载 | `/uninstall_do firefox \| dry_run` |
| `/junk_scan [\| categories]` | `jscan` | 扫描垃圾文件 | `/junk_scan` |
| `/junk_clean [\| dry_run]` | `jclean` | 清理垃圾文件 | `/junk_clean \| dry_run=false` |

### 其他内置斜杠指令

| 指令 | 说明 |
| :--- | :--- |
| `/py <code>` | 直接执行 Python 代码片段 |
| `/sh <cmd>` | 直接执行 Shell 命令 |
| `/approve` | 授权执行 AI 预生成的代码 |
| `/cleanup` | 手动触发临时文件清理与数据回收 |
| `/profile-reset` | 重置已学习的用户习惯 |

---

## 5. 技能使用指南

Butler 采用 **One Folder = One Skill** 架构。`skills/` 目录下每个文件夹就是一个技能。

### 5.1 技能的两种类型

| 类型 | 标记 | 说明 | 能否用户直接运行 |
| :--- | :--- | :--- | :--- |
| 🐍 USER（可调用） | 有 `main.py` 或 `__init__.py` | 用户可直接 `butler skill run` 调用 | ✅ |
| 📖 AGENT | 纯 `SKILL.md` 指令集 | 由 AI 在对话中自动读取使用 | ❌（通过对话触发） |

### 5.2 三步使用技能

```bash
# ① 查找技能
butler skill list

# ② 查看详情（含 SKILL.md 预览）
butler skill info <技能ID>

# ③ 运行（仅 USER 类型）
butler skill run <技能ID> [action] [--key value]
```

### 5.3 按场景选技能

| 你想做什么 | 推荐技能 | 调用方式 |
| :--- | :--- | :--- |
| 文档格式转换（PDF/Word/Excel/EPUB） | `format_convert` | `butler skill run format_convert --input a.pdf --format docx` |
| 提取 PDF/Word/PPT 文本为 Markdown | `markitdown` | `/markitdown report.pdf` |
| 压缩/解压（7z/zip/tar） | `archive_manager` | `/archive_compress out.7z \| ./docs` |
| 播放本地视频 | `video_player` | AI 对话："播放 D 盘的电影" |
| 播放音乐 / 管理歌单 | `music_player` | AI 对话："播放周杰伦的歌" |
| 屏幕截图 / 录屏 | `screen_capture` | AI 对话："截个屏" |
| 下载管理（HTTP/FTP/BT/磁力） | `download_manager` | `butler download <url>` |
| 网盘聚合（OneDrive/WebDAV/百度） | `storage_hub` | `/storage_hub list` |
| 网盘挂载为本地磁盘 | `cloud_mount` | AI 对话："把百度网盘挂载到本地" |
| 密码生成 | `password_generator` | `butler skill run password_generator` |
| 记账与消费统计 | `expense_tracker` | `butler skill run expense_tracker` |
| 习惯打卡追踪 | `habit_tracker` | `butler skill run habit_tracker` |
| 今日穿搭建议 | `daily_fashion_stylist` | AI 对话："今天穿什么" |
| 代码格式化（JSON/YAML/XML） | `code_formatter` | `butler skill run code_formatter` |
| 文本分析（词频/可读性） | `text_analyzer` | `butler skill run text_analyzer` |
| Office 套件（Word/Excel/PPT） | `office-suite-expert` | AI 对话中描述需求 |
| WPS 办公 | `wps-office-expert` | AI 对话中描述需求 |
| Photoshop 图像处理 | `photoshop-expert` | AI 对话中描述需求 |
| 系统深度卸载与清理 | `geek_uninstaller` | `/uninstaller list` |
| 剪贴板智能分类 | `clip_magic` / `ClipMagic` | `/clip_magic` |
| 端口扫描 | `SecRadar` | `/sec_scan 127.0.0.1` |
| 像素电子宠物 | `pixel_pet` | AI 对话："打开像素宠物" |
| 实时双语字幕 | `ai_subtitles` | AI 对话："开启字幕" |
| 实时音频频谱分析 | `skill_audio_core` | AI 对话："分析音频" |

### 5.4 安装新技能

```bash
# 从远程 SKILL.md 安装
butler skill install --url https://example.com/my_skill/SKILL.md

# 从本地目录安装
butler skill install --path ./my_skill_folder

# 从 stdin 安装
curl -fsSL https://example.com/SKILL.md | butler skill install
```

---

## 6. 自然语言交互示例

在 TUI 或 Web UI 的对话输入框中，直接用中文描述需求即可。以下是一些真实可触发的示例：

| 你说 | Butler 会做 |
| :--- | :--- |
| "上海今天天气怎么样？" | 调用天气查询，返回温度/湿度/风力 |
| "帮我把 report.pdf 转成 Word" | 调用格式转换，生成 report.docx |
| "用 AES 加密这个 secret.txt" | 提示输入核心码，生成 .enc 文件 |
| "把这段话翻译成英文：你好世界" | 调用翻译，返回译文 |
| "列出当前目录的文件" | 调用文件列表，显示目录内容 |
| "搜索一下猫咪的图片" | 调用图片搜索 |
| "帮我发封邮件给 a@b.com，主题是开会" | 调用邮件发送 |
| "运行系统监控" | 输出 CPU/内存/磁盘报告 |
| "列出我所有的技能" | 展示技能清单 |
| "播放本地音乐" | 启动音乐播放器 |
| "把这篇文章翻译成中文" | 调用网页/文本翻译 |
| "保存一条记忆：采用了 SQLite FTS5 方案" | 写入长期记忆库 |

> 💡 **技巧**：不知道命令名时，直接说想做什么即可。Butler 的意图识别会自动映射到对应功能。也可以用 `/howto 我想做某事` 让 Butler 推荐具体命令。

---

## 7. 常见问题与排查

### Q：`butler` 命令找不到？

确保 `bin/` 目录已加入 PATH：

```bash
# Linux/macOS（临时）
export PATH="$PWD/bin:$PATH"
# 永久生效：写入 ~/.bashrc 或 ~/.zshrc
```

或直接用 `./bin/butler` / `bin\butler.bat`。

### Q：AI 无响应 / 提示 Key 无效？

```bash
butler config          # 重新交互式配置
butler config check    # 检查配置完整性
butler doctor          # 全面体检
```

确认 `.env` 中的 `DEEPSEEK_API_KEY` 正确。

### Q：`pyaudio` 安装失败？

需要先安装 PortAudio 系统库：

```bash
# Debian/Ubuntu
sudo apt-get install portaudio19-dev
# macOS
brew install portaudio
```

### Q：端口被占用？

```bash
butler start --port 5002
```

### Q：依赖缺失？

```bash
butler dependency install_all
```

### Q：技能无法运行？

1. 先确认技能类型：`butler skill info <技能ID>`
2. 📖 AGENT 技能不能直接运行，需通过对话触发
3. 🐍 USER 技能需要有 Python 入口（`main.py` 或 `__init__.py`）

### Q：想了解某个命令的详细用法？

```bash
butler skill help          # 技能 man page
/help <命令名>              # TUI 内查看斜杠命令帮助
/commands <关键词>          # 按关键词过滤命令
/howto <你想做什么>         # 按意图推荐命令
```

### Q：配置文件在哪？

- 主配置：`.env`（项目根目录，从 `.env.example` 生成）
- 系统配置：`config/system_config.json` / `config/settings.yaml`
- 全部环境变量含义见 [完整环境变量参考](./start/env-reference.md)

### Q：如何彻底卸载？

便携模式下直接删除项目文件夹即可（所有依赖隔离在 `lib_external/` 内，不污染系统）。

---

## 延伸阅读

- [安装与启动指南](./start/install.md)
- [完整环境变量参考](./start/env-reference.md)
- [错误码规范](./dev/ERROR_CODES.md)
- [技能贡献与创建指南](./SKILLS_GUIDE.md)
- [架构深度解密](./Butler_Code_Wiki.md)
