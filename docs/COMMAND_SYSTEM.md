# Butler 命令行与指令系统全攻略 (Command System Guide)

本指南旨在帮助您快速掌握 Butler 系统提供的双重交互能力：**硬核命令行 (CLI)** 与 **智能文字命令行 (Natural Language Commands)**。

---

## 1. 硬核命令行 (Hardcore CLI)

对于开发者、运维人员或喜欢自动化脚本的用户，我们提供了统一的入口：`butler_cli.py`。

### 基础用法
```bash
python butler_cli.py [子命令] [参数]
```

### 可用子命令与示例

| 子命令 | 功能描述 | 示例用法 |
| :--- | :--- | :--- |
| `crawl` | 网页爬取与多媒体搜索 | `python butler_cli.py crawl --url http://example.com` |
| `email` | 发送、接收与管理邮件 | `python butler_cli.py email --receive` |
| `image-search` | 图片搜索与本地图库管理 | `python butler_cli.py image-search --query "风景"` |
| `encrypt` | 对称加密文件 (AES/DES) | `python butler_cli.py encrypt --path a.txt --algo AES` |
| `decrypt` | 对称解密文件 | `python butler_cli.py decrypt --path a.txt.enc --algo AES` |
| `weather` | 查询城市实时天气 | `python butler_cli.py weather 北京` |
| `translate` | 文字、文件或网页翻译 | `python butler_cli.py translate --text "Hello"` |
| `convert` | 文档格式转换 (PDF, Word等) | `python butler_cli.py convert --input a.pdf --output a.docx` |
| `monitor` | 系统健康与资源占用报告 | `python butler_cli.py monitor` |
| `audit` | 高性能日志扫描与审计 | `python butler_cli.py audit --dir ./logs` |
| `dependency` | 管理环境与安装依赖库 | `python butler_cli.py dependency install_all` |
| `file` | 基础文件读写与列表操作 | `python butler_cli.py file --op list --path ./` |

---

## 2. 智能文字命令行 (Text Command Line)

您可以直接在聊天窗口输入自然语言，Butler 的 AI 引擎会自动将其解析为对应的功能指令。中文支持极其灵活，多种组合效果一致。

### 触发示例 (中英对比)

| 目标功能 | 中文文字指令示例 (文字命令行) | CLI 等效参数 |
| :--- | :--- | :--- |
| **网页爬虫** | “爬取一下这个网页 http://xxx.com”<br>“抓取关于'跑车'的图片” | `crawl --url` <br> `crawl --query` |
| **邮件管理** | “帮我发封邮件给 test@qq.com，主题是开会”<br>“看一下我有多少未读邮件” | `email --send` <br> `email --receive` |
| **图片搜索** | “搜一下周杰伦的照片”<br>“在当前文件夹里找找带'猫'的图片” | `image-search --query`<br>`image-search --path` |
| **文件加解密** | “把 test.docx 加密一下”<br>“用 DES 算法加密这个文件” | `encrypt --path` <br> `encrypt --algo` |
| **天气查询** | “上海今天天气怎么样？”<br>“查查深圳的天气” | `weather [city]` |
| **文件转换** | “帮我把这个 pdf 转换成 word” | `convert --input --output` |
| **翻译** | “把这段话翻译成中文：Stay hungry, stay foolish” | `translate --text` |
| **系统监控** | “系统运行状况如何？”<br>“生成一份健康报告” | `monitor` |

### 核心优势
- **意图识别**：无论你说“爬”、“抓”、“获取”还是“采集”，AI 都会精准映射到 `crawl` 意图。
- **参数提取**：AI 会自动从你的话中提取文件名、网址、城市名等实体，无需记忆复杂的参数名。

---

## 3. 极客斜杠指令 (Slash Commands)

在聊天窗口中，还可以使用以下高性能内置指令：

- `/py [code]`：进入 Python 代码解释器模式，直接执行代码。
- `/sh [cmd]`：进入 Shell 模式，直接执行系统命令。
- `/profile`：查看当前 AI 为您学习到的个人习惯与偏好。
- `/profile-reset`：重置所有已学习的习惯。
- `/cleanup`：手动触发系统临时文件清理与数据回收。

---

## 4. 总结

- 如果您在写脚本，请使用 **`butler_cli.py`**。
- 如果您在日常对话，请使用 **文字命令行**。
- 它们在底层调用的是同一套高效率的功能模块，为您提供一致的体验。
