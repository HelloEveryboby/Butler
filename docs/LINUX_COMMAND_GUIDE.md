# Butler Linux 风格命令使用指南

> 适用于 Butler TUI / GUI 内置命令系统，所有命令在 **无 AI 模型** 下均可使用。

---

## 1. 概述

Butler 的命令系统采用 **Linux 风格** 设计，支持：

- **无前缀输入** — 直接输入命令名，无需 `/` 前缀
- **短选项** — `-f value` 或 `-fvalue`
- **长选项** — `--flag value` 或 `--flag=value`
- **位置参数** — `cmd arg1 arg2`（自动映射到必填选项）
- **管道** — `cmd1 | grep keyword | head 10`
- **重定向** — `cmd > output.txt`
- **帮助** — `cmd --help` 或 `cmd -h`
- **引号** — `-t "标题含空格"`（支持双引号和单引号）
- **向后兼容** — 旧的 `/` 前缀命令仍可使用

---

## 2. 语法说明

### 2.1 基本格式

```
命令名 [选项] [参数]
```

示例：
```bash
markitdown -i report.pdf
archive_compress -o backup.7z -t /home/user/docs -p secret
```

### 2.2 选项格式

| 格式 | 示例 | 说明 |
|---|---|---|
| 短选项 + 空格 | `-o output.pdf` | 推荐写法 |
| 短选项连写 | `-ooutput.pdf` | 紧凑写法 |
| 长选项 + 空格 | `--output output.pdf` | 可读性更好 |
| 长选项等号 | `--output=output.pdf` | 脚本友好 |
| 布尔开关 | `--no-dry-run` | 不需要值，存在即为 true |
| 位置参数 | `uninstall_scan firefox` | 自动映射到必填选项 |

### 2.3 管道

将前一个命令的输出作为后一个命令的输入：

```bash
pdf_extract -i paper.pdf | grep "关键词"
uninstaller | head 5
sys_info | grep CPU
top_procs -s memory | head 10
```

**支持的管道命令：**

| 命令 | 功能 | 示例 |
|---|---|---|
| `grep <关键词>` | 按关键词过滤行 | `\| grep error` |
| `grep -i <关键词>` | 忽略大小写过滤 | `\| grep -i warning` |
| `head [N]` | 取前 N 行（默认 10） | `\| head 5` |
| `tail [N]` | 取后 N 行（默认 10） | `\| tail 3` |
| `wc` | 统计行数 | `\| wc` |
| `sort` | 按字母排序 | `\| sort` |

### 2.4 重定向

将命令输出写入文件：

```bash
sys_info > system_snapshot.txt
top_procs -s memory > top_memory.txt
pdf_extract -i paper.pdf > paper_text.txt
```

### 2.5 帮助

任意命令加 `--help` 或 `-h` 查看详细用法：

```bash
archive_compress --help
pdf_merge -h
```

输出示例：
```
用法: archive_compress [选项] [参数]

  压缩文件或目录 (7z/zip)

选项:
  -o, --output              输出压缩包路径 (必填)
  -t, --target              要压缩的文件/目录 (必填)
  -p, --password            加密密码 (可选)

示例:
  archive_compress -o backup.7z -t /docs

  -h, --help     显示此帮助信息
```

---

## 3. 完整命令参考

### 3.1 文档处理

#### markitdown — 文件转 Markdown

将 PDF/DOCX/PPTX/XLSX/HTML/CSV/EPUB/图片等格式转为 Markdown。

```bash
markitdown -i <输入文件> [-o <输出文件>]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-i, --input` | 输入文件路径 | 是 |
| `-o, --output` | 输出文件（默认输出到聊天区） | 否 |

```bash
markitdown -i report.pdf
markitdown -i slides.pptx -o slides.md
markitdown -i report.pdf > report.md
```

---

#### docx_read — 读取 Word 文档

```bash
docx_read -i <文件路径>
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-i, --input` | Word 文档路径 | 是 |

```bash
docx_read -i report.docx
docx_read -i report.docx | grep "章节"
```

---

#### docx_create — 创建 Word 文档

```bash
docx_create -o <输出路径> [-t <标题>] [-c <内容>]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-o, --output` | 输出文件路径 | 是 |
| `-t, --title` | 文档标题 | 否 |
| `-c, --content` | 正文内容 | 否 |

```bash
docx_create -o new.docx -t "我的文档" -c "这是正文内容"
docx_create -o report.docx -t "季度报告" -c "本季度业绩..."
```

---

#### pdf_extract — 提取 PDF 文本

```bash
pdf_extract -i <文件路径>
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-i, --input` | PDF 文件路径 | 是 |

```bash
pdf_extract -i paper.pdf
pdf_extract -i paper.pdf | grep "abstract"
pdf_extract -i paper.pdf > paper.txt
```

---

#### pdf_merge — 合并 PDF

```bash
pdf_merge -i <文件1,文件2,...> -o <输出路径>
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-i, --inputs` | 输入文件列表（逗号分隔） | 是 |
| `-o, --output` | 合并后输出路径 | 是 |

```bash
pdf_merge -i a.pdf,b.pdf,c.pdf -o merged.pdf
pdf_merge --inputs=ch1.pdf,ch2.pdf --output=book.pdf
```

---

#### pdf_split — 拆分 PDF

```bash
pdf_split -i <文件路径> [-o <输出目录>]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-i, --input` | 要拆分的 PDF 文件 | 是 |
| `-o, --output-dir` | 输出目录（可选） | 否 |

```bash
pdf_split -i large.pdf
pdf_split -i large.pdf -o ./pages/
```

---

#### format_convert — 格式转换

将 Markdown 转为 DOCX/EPUB/PNG/HTML。

```bash
format_convert -i <输入文件> -f <输出格式>
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-i, --input` | 输入文件 | 是 |
| `-f, --format` | 输出格式：`docx`/`epub`/`png`/`html` | 是 |

```bash
format_convert -i readme.md -f docx
format_convert -i readme.md -f epub
format_convert -i readme.md -f html
```

---

### 3.2 压缩归档

#### archive_compress — 压缩文件

```bash
archive_compress -o <输出路径> -t <目标> [-p <密码>]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-o, --output` | 输出压缩包路径 | 是 |
| `-t, --target` | 要压缩的文件/目录 | 是 |
| `-p, --password` | 加密密码（可选） | 否 |

```bash
archive_compress -o backup.7z -t /home/user/docs
archive_compress -o secret.7z -t /docs -p mypassword
archive_compress -o project.zip -t ./project/
```

---

#### archive_extract — 解压文件

```bash
archive_extract -i <压缩包> [-d <输出目录>] [-p <密码>]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-i, --input` | 压缩包路径 | 是 |
| `-d, --dest` | 输出目录（可选） | 否 |
| `-p, --password` | 解压密码（可选） | 否 |

```bash
archive_extract -i backup.7z
archive_extract -i backup.7z -d /tmp/output
archive_extract -i secret.7z -p mypassword
```

---

#### archive_list — 列出压缩包内容

```bash
archive_list -i <压缩包>
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-i, --input` | 压缩包路径 | 是 |

```bash
archive_list -i backup.7z
archive_list -i backup.7z | grep ".pdf"
```

---

### 3.3 系统管理

#### uninstaller — 软件列表

```bash
uninstaller [--action list]
```

```bash
uninstaller
uninstaller --action list
uninstaller | head 10
uninstaller | grep firefox
```

---

#### uninstall_scan — 残留扫描

扫描指定软件卸载后的残留文件。

```bash
uninstall_scan -n <软件名>
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-n, --name` | 软件名 | 是 |

```bash
uninstall_scan -n firefox
uninstall_scan firefox
```

---

#### uninstall_do — 深度卸载

调用卸载程序 + 清理残留。

```bash
uninstall_do -n <软件名> [--no-dry-run]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-n, --name` | 软件名 | 是 |
| `--no-dry-run` | 实际执行删除（默认仅模拟） | 否 |

```bash
uninstall_do -n firefox                    # 模拟卸载
uninstall_do -n firefox --no-dry-run       # 实际卸载
```

---

#### junk_scan — 垃圾扫描

```bash
junk_scan [--categories <类型>]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `--categories` | 过滤类型（逗号分隔） | 否 |

```bash
junk_scan
junk_scan --categories cache,temp
junk_scan | head 20
```

---

#### junk_clean — 垃圾清理

```bash
junk_clean [--no-dry-run] [--categories <类型>]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `--no-dry-run` | 实际删除（默认仅模拟） | 否 |
| `--categories` | 过滤类型 | 否 |

```bash
junk_clean                           # 模拟清理
junk_clean --no-dry-run              # 实际清理
junk_clean --no-dry-run --categories cache
```

---

#### sys_info — 系统信息

```bash
sys_info
```

```bash
sys_info
sys_info > snapshot.txt
sys_info | grep CPU
```

---

#### top_procs — Top 进程

```bash
top_procs [-s cpu|memory] [-n <数量>]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-s, --sort` | 排序方式：`cpu`/`memory`（默认 cpu） | 否 |
| `-n, --limit` | 显示数量（默认 15） | 否 |

```bash
top_procs
top_procs -s memory
top_procs -s cpu -n 5
top_procs -s memory | head 5
```

---

### 3.4 安装追踪（3 步流程）

用于追踪软件安装过程中的系统变更，安装后精确清理残留。

#### track_start — 安装前快照（第 1 步）

```bash
track_start
```

在安装软件**之前**执行，捕获系统当前状态。

---

#### track_stop — 安装后差异（第 2 步）

```bash
track_stop
```

在安装软件**之后**执行，捕获安装后快照并生成差异报告。

---

#### track_clean — 执行清理（第 3 步）

```bash
track_clean
```

根据差异报告清理安装残留。

**完整流程示例：**
```bash
track_start              # 1. 安装前快照
# ... 安装软件 ...
track_stop               # 2. 生成差异报告
track_clean              # 3. 清理残留
```

---

### 3.5 媒体与存储

#### media_scan — 媒体扫描

```bash
media_scan
```

扫描所有盘符/挂载点的 MP3/WAV/JPG 文件。

---

#### storage_hub — 云盘列表

```bash
storage_hub [--action list]
```

```bash
storage_hub
storage_hub --action list
```

---

#### cloud_list — 列出云盘文件

```bash
cloud_list -d <云盘ID> [-p <路径>]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-d, --drive` | 云盘 ID | 是 |
| `-p, --path` | 路径（默认 `/`） | 否 |

```bash
cloud_list -d onedrive_1
cloud_list -d onedrive_1 -p /Documents
cloud_list -d webdav_1 -p /photos
```

---

#### cloud_search — 跨云盘搜索

```bash
cloud_search -q <关键词>
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-q, --query` | 搜索关键词 | 是 |

```bash
cloud_search -q 报告
cloud_search -q "annual report"
cloud_search -q .pdf | head 10
```

---

#### cloud_transfer — 跨云盘传输

```bash
cloud_transfer -s <源盘> -d <目标盘> -f <文件名> [--src-path <路径>] [--dst-path <路径>]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-s, --src` | 源云盘 ID | 是 |
| `-d, --dst` | 目标云盘 ID | 是 |
| `-f, --file` | 文件名 | 是 |
| `--src-path` | 源路径（默认 `/`） | 否 |
| `--dst-path` | 目标路径（默认 `/`） | 否 |

```bash
cloud_transfer -s onedrive_1 -d webdav_1 -f report.pdf
cloud_transfer -s onedrive_1 -d webdav_1 -f report.pdf --src-path /Documents
```

---

#### cloud_status — 传输状态

```bash
cloud_status -t <任务ID>
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-t, --task` | 传输任务 ID | 是 |

```bash
cloud_status -t task_1234567890
```

---

#### cloud_duplicates — 查找重复文件

```bash
cloud_duplicates
```

扫描所有云盘，找出同名同大小的重复文件。

---

### 3.6 剪贴板服务

#### clip_magic — 启动剪贴板服务

```bash
clip_magic
```

启动后台剪贴板监听服务，自动分类 URL/IP/代码/纯文本。

---

#### skill_stop — 停止服务

```bash
skill_stop -n <技能名>
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-n, --name` | 技能名：`clip_magic`/`focus`/`pixel_pet` | 是 |

```bash
skill_stop -n clip_magic
skill_stop -n focus
```

---

#### skill_status — 查看服务状态

```bash
skill_status [-n <技能名>]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-n, --name` | 技能名（不填则列出全部） | 否 |

```bash
skill_status                    # 列出所有后台技能
skill_status -n clip_magic      # 查询指定技能
```

---

#### clip_history — 剪贴板历史

```bash
clip_history
```

查看 ClipMagic 最近分类的剪贴板内容。

---

### 3.7 安全测试

#### sec_scan — 端口扫描

```bash
sec_scan -t <目标IP> [-p <端口范围>]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-t, --target` | 目标 IP | 是 |
| `-p, --ports` | 端口范围（如 `1-1000`） | 否 |

```bash
sec_scan -t 127.0.0.1
sec_scan -t 192.168.1.1 -p 1-1000
sec_scan -t 10.0.0.1 | grep open
```

---

#### web_sec_test — Web 安全测试

```bash
web_sec_test -t <URL> [-m recon|scan|full]
```

| 选项 | 说明 | 必填 |
|---|---|---|
| `-t, --target` | 目标 URL | 是 |
| `-m, --mode` | 模式：`recon`/`scan`/`full`（默认 `full`） | 否 |

```bash
web_sec_test -t https://example.com
web_sec_test -t https://example.com -m recon
web_sec_test -t https://example.com -m scan
```

**模式说明：**

| 模式 | 功能 |
|---|---|
| `recon` | nmap 侦察，发现开放端口和服务 |
| `scan` | nuclei 漏洞扫描 |
| `full` | 侦察 + 扫描 + 完整检查清单 |

---

## 4. 高级用法

### 4.1 组合管道

```bash
# 提取 PDF 文本并搜索关键词
pdf_extract -i paper.pdf | grep "machine learning"

# 列出软件并取前 5 个
uninstaller | head 5

# 查看内存占用最高的 3 个进程
top_procs -s memory | head 3

# 统计垃圾文件数量
junk_scan | wc

# 排序云盘文件列表
cloud_list -d onedrive_1 | sort
```

### 4.2 输出重定向

```bash
# 保存系统信息到文件
sys_info > system_snapshot.txt

# 保存 Top 进程到文件
top_procs -s memory > top_memory.txt

# 保存 PDF 文本到文件
pdf_extract -i paper.pdf > paper_text.txt
```

### 4.3 在 TUI 工具箱中使用

1. 打开 TUI → 工具箱 → **🧰 技能** Tab
2. 点击对应按钮，系统会提示输入参数
3. 按提示输入 Linux 风格选项（如 `-i file.pdf`）
4. 按 Enter 执行

### 4.4 在 GUI 中使用

1. 在对话区找到 **🧰 本地技能** 面板
2. 点击快捷卡片，命令自动填入输入框
3. 补充参数后按 Enter 发送

---

## 5. 命令速查表

| 命令 | 功能 | 示例 |
|---|---|---|
| `markitdown` | 文件转 Markdown | `markitdown -i report.pdf` |
| `docx_read` | 读取 Word | `docx_read -i report.docx` |
| `docx_create` | 创建 Word | `docx_create -o new.docx -t "标题"` |
| `pdf_extract` | 提取 PDF 文本 | `pdf_extract -i paper.pdf` |
| `pdf_merge` | 合并 PDF | `pdf_merge -i a.pdf,b.pdf -o merged.pdf` |
| `pdf_split` | 拆分 PDF | `pdf_split -i large.pdf` |
| `format_convert` | 格式转换 | `format_convert -i readme.md -f docx` |
| `archive_compress` | 压缩 | `archive_compress -o backup.7z -t /docs` |
| `archive_extract` | 解压 | `archive_extract -i backup.7z` |
| `archive_list` | 列出压缩包 | `archive_list -i backup.7z` |
| `uninstaller` | 软件列表 | `uninstaller` |
| `uninstall_scan` | 残留扫描 | `uninstall_scan -n firefox` |
| `uninstall_do` | 深度卸载 | `uninstall_do -n firefox --no-dry-run` |
| `junk_scan` | 垃圾扫描 | `junk_scan` |
| `junk_clean` | 垃圾清理 | `junk_clean --no-dry-run` |
| `sys_info` | 系统信息 | `sys_info` |
| `top_procs` | Top 进程 | `top_procs -s memory` |
| `track_start` | 安装前快照 | `track_start` |
| `track_stop` | 安装后差异 | `track_stop` |
| `track_clean` | 执行清理 | `track_clean` |
| `media_scan` | 媒体扫描 | `media_scan` |
| `storage_hub` | 云盘列表 | `storage_hub` |
| `cloud_list` | 云盘文件 | `cloud_list -d onedrive_1` |
| `cloud_search` | 云盘搜索 | `cloud_search -q 报告` |
| `cloud_transfer` | 跨盘传输 | `cloud_transfer -s onedrive_1 -d webdav_1 -f report.pdf` |
| `cloud_status` | 传输状态 | `cloud_status -t task_123` |
| `cloud_duplicates` | 查找重复 | `cloud_duplicates` |
| `clip_magic` | 启动剪贴板 | `clip_magic` |
| `skill_stop` | 停止服务 | `skill_stop -n clip_magic` |
| `skill_status` | 服务状态 | `skill_status` |
| `clip_history` | 剪贴板历史 | `clip_history` |
| `sec_scan` | 端口扫描 | `sec_scan -t 127.0.0.1` |
| `web_sec_test` | Web 安全测试 | `web_sec_test -t https://example.com` |

---

## 6. 向后兼容

- 旧的 `/` 前缀命令仍然可用：`/markitdown -i report.pdf`
- 不含选项的简单位置参数仍然可用：`uninstall_scan firefox`
- 旧的 `|` 分隔多参数格式已废弃，请使用 `-f` 选项格式

---

## 7. OS 原生命令（跨平台）

Butler 内置 **106 个跨平台 OS 命令适配器**，支持直接输入 Linux/Windows/macOS 原生命令，自动检测操作系统并路由到对应实现。

### 7.1 工作原理

```
用户输入 ls → 检测到 Linux → 执行 ls
用户输入 ls → 检测到 Windows → 执行 cmd /c dir
用户输入 dir → 检测到 Linux → 执行 ls -la
用户输入 dir → 检测到 Windows → 执行 cmd /c dir
```

无论你在哪个平台，都可以使用任一平台的命令名，Butler 自动翻译。

### 7.2 支持的命令分类

#### 文件操作

| 命令 | Linux | Windows | macOS |
|---|---|---|---|
| `ls` | ls | dir | ls |
| `ll` | ls -la | dir | ls -la |
| `cat` | cat | type | cat |
| `cp` | cp | copy | cp |
| `mv` | mv | move | mv |
| `rm` | rm | del | rm |
| `mkdir` | mkdir -p | mkdir | mkdir -p |
| `touch` | touch | type nul | touch |
| `pwd` | pwd | cd | pwd |
| `ln` | ln -s | mklink | ln -s |
| `chmod` | chmod | icacls | chmod |
| `dir` | ls -la | dir | ls -la |
| `type` | cat | type | cat |
| `copy` | cp | copy | cp |
| `move` | mv | move | mv |
| `del` | rm | del | rm |

#### 搜索

| 命令 | 功能 | 示例 |
|---|---|---|
| `find` | 查找文件 | `find / -name "*.py"` |
| `locate` | 快速定位 | `locate config.yaml` |
| `which` | 查找命令路径 | `which python` |
| `whereis` | 查找命令和源码 | `whereis gcc` |
| `grep` | 文本搜索 | `grep "error" log.txt` |
| `rg` | ripgrep 搜索 | `rg "pattern" /src` |
| `findstr` | Windows 文本搜索 | `findstr "port" config.txt` |
| `where` | Windows 命令查找 | `where python` |

#### 进程管理

| 命令 | 功能 | 示例 |
|---|---|---|
| `ps` | 列出进程 | `ps aux` |
| `top` | 实时进程 | `top` |
| `kill` | 终止进程 | `kill 1234` |
| `killall` | 按名终止 | `killall firefox` |
| `tasklist` | Windows 进程列表 | `tasklist` |
| `taskkill` | Windows 终止进程 | `taskkill /pid 1234` |

#### 网络

| 命令 | 功能 | 示例 |
|---|---|---|
| `ping` | 网络连通性 | `ping 8.8.8.8` |
| `ifconfig` | 网络接口 | `ifconfig` |
| `ipconfig` | Windows 网络配置 | `ipconfig` |
| `netstat` | 网络连接 | `netstat` |
| `ss` | 现代网络连接 | `ss -tlnp` |
| `curl` | HTTP 请求 | `curl https://api.example.com` |
| `wget` | 下载文件 | `wget https://example.com/file.zip` |
| `ssh` | 远程登录 | `ssh user@host` |
| `scp` | 远程拷贝 | `scp file user@host:/path` |
| `nslookup` | DNS 查询 | `nslookup example.com` |
| `dig` | DNS 查询 | `dig example.com` |
| `traceroute` | 路由追踪 | `traceroute example.com` |

#### 系统信息

| 命令 | 功能 | 示例 |
|---|---|---|
| `uname` | 系统信息 | `uname -a` |
| `uptime` | 运行时间 | `uptime` |
| `free` | 内存使用 | `free -h` |
| `lscpu` | CPU 信息 | `lscpu` |
| `lsusb` | USB 设备 | `lsusb` |
| `whoami` | 当前用户 | `whoami` |
| `env` | 环境变量 | `env` |
| `hostname` | 主机名 | `hostname` |
| `date` | 日期时间 | `date` |
| `systeminfo` | Windows 系统信息 | `systeminfo` |

#### 文本处理

| 命令 | 功能 | 示例 |
|---|---|---|
| `echo` | 输出文本 | `echo "hello"` |
| `sed` | 流编辑 | `sed 's/old/new/g' file` |
| `awk` | 文本处理 | `awk '{print $1}' file` |
| `sort` | 排序 | `sort file.txt` |
| `uniq` | 去重 | `sort file \| uniq` |
| `wc` | 行/词/字节统计 | `wc -l file.txt` |
| `diff` | 文件比较 | `diff a.txt b.txt` |
| `head` | 取前 N 行 | `head -20 file` |
| `tail` | 取后 N 行 | `tail -5 file` |
| `cut` | 列切割 | `cut -d: -f1 /etc/passwd` |
| `tr` | 字符替换 | `tr 'a-z' 'A-Z'` |
| `tee` | 双向输出 | `cmd \| tee log.txt` |
| `xargs` | 参数传递 | `find . -name "*.py" \| xargs grep "test"` |
| `jq` | JSON 处理 | `cat data.json \| jq .name` |

#### 包管理

| 命令 | Linux | Windows | macOS |
|---|---|---|---|
| `apt` | apt | winget | brew |
| `brew` | brew | winget | brew |
| `pip` | pip | pip | pip3 |

#### 压缩/归档

| 命令 | 功能 | 示例 |
|---|---|---|
| `tar` | tar 归档 | `tar -czf archive.tar.gz /dir` |
| `zip` | zip 压缩 | `zip -r archive.zip /dir` |
| `unzip` | zip 解压 | `unzip archive.zip` |
| `gzip` | gzip 压缩 | `gzip file.txt` |

#### macOS 专属

| 命令 | 功能 | 示例 |
|---|---|---|
| `open` | 打开文件/URL | `open https://example.com` |
| `pbcopy` | 复制到剪贴板 | `echo "text" \| pbcopy` |
| `pbpaste` | 从剪贴板粘贴 | `pbpaste` |
| `say` | 语音朗读 | `say "hello"` |
| `defaults` | 系统偏好设置 | `defaults read com.apple.dock` |

#### Windows 专属

| 命令 | 功能 | 示例 |
|---|---|---|
| `dir` | 列出目录 | `dir C:\Users` |
| `type` | 显示文件 | `type config.txt` |
| `tasklist` | 进程列表 | `tasklist` |
| `taskkill` | 终止进程 | `taskkill /im firefox.exe` |
| `systeminfo` | 系统信息 | `systeminfo` |
| `clip` | 复制到剪贴板 | `dir \| clip` |

#### 服务管理

| 命令 | Linux | Windows | macOS |
|---|---|---|---|
| `systemctl` | systemctl | sc | launchctl |
| `crontab` | crontab | schtasks | crontab |
| `sudo` | sudo | runas | sudo |
| `nohup` | nohup | start /b | nohup |

### 7.3 OS 命令管道和重定向

OS 命令完全支持管道和重定向：

```bash
# 管道
ls -la /tmp | grep "log"
ps aux | head 10
cat config.yaml | grep port
find / -name "*.py" | head 20
ls | sort | uniq

# 重定向
ls > files.txt
ps aux > processes.txt
whoami > user.txt

# 组合管道
cat log.txt | grep "ERROR" | head 5
ls -la | sort | head 10 > top_files.txt
```

### 7.4 查看所有支持的 OS 命令

```bash
os_help          # 列出所有 106 个 OS 命令
os_help 文件     # 按分类过滤
```

### 7.5 OS 命令 --help

```bash
ls --help
grep --help
ping --help
```

### 7.6 跨平台命令解释器 (cmd_explain)

**核心功能：输入任一命令名，自动显示其功能说明 + 三平台翻译 + 参数语义 + 使用示例**

```bash
# 基础用法
cmd_explain -c ls              # 解释 ls 命令
explain -c grep                # 别名: explain

# 附参数说明
cmd_explain -c rm -a '-rf'     # 解释 rm 命令, 并说明 -rf 参数
cmd_explain -c tar -a '-czf out.tar.gz src'  # 解释 tar 命令及参数
cmd_explain -c grep -a '-r pattern src/'

# 也支持 / 前缀
/cmd_explain -c ls
/explain -c chmod
```

**输出包含：**
- 📖 命令功能描述（中文）
- ━━━ 跨平台翻译━━━：Linux / Windows / macOS 三平台的等效命令
- ━━━ 参数解释━━━：输入参数的语义含义，以及该语义在三平台的对应写法（如 recursive → Linux -r / Windows /s / macOS -R）
- ━━━ 常用参数速查━━━：该命令最常见的选项说明
- ━━━ 常见用法━━━：3-5 条典型使用示例

### 7.7 跨平台命令翻译器 (cmd_translate)

**核心功能：把一条完整命令（含参数）自动翻译成指定平台或全部三平台**

```bash
# 翻译到全部三平台
cmd_translate -c 'ls -la /home'           # Linux 风格 → 三平台
cmd_translate -c 'dir /s /b *.log'        # Windows 风格 → 三平台
cmd_translate -c 'grep -r error app.log'

# 翻译到指定平台 (-t: linux / windows / macos)
cmd_translate -c 'dir /s' -t linux        # Windows dir /s → Linux
cmd_translate -c 'taskkill /f /im chrome.exe' -t macos
cmd_translate -c 'findstr /s /i error' -t linux

# 也支持 / 前缀
/cmd_translate -c 'ls -la' -t windows
```

**典型输出：**
```
🔄 跨平台翻译: ls -la /home

  LINUX     👉  ls -la /home
  WINDOWS   👉  cmd /c dir -la /home
  MACOS     👉  ls -la /home
```

### 7.8 批量命令跨平台对比 (cmd_compare / compare)

**核心功能：一次比较多条命令，在一张表格里同时看它们在三平台的实现差异**

```bash
# 方式一: 空格分隔多条命令
cmd_compare 'ls -la' 'grep pattern file' 'ping 8.8.8.8' 'rm -rf cache'

# 方式二: 逗号分隔命令名
cmd_compare ls, grep, find, curl, tar
compare -l 'ls -la, dir, findstr, taskkill'

# 也支持 / 前缀
/cmd_compare 'ls -la' 'cat file' 'ps aux'
/compare -l 'ping, curl, wget, scp'
```

**典型输出表格：**
```
📋 命令跨平台对比表

  输入                │ LINUX             │ WINDOWS                     │ macOS
  ───────────────────────────────────────────────────────────────────────────
  ls -la            │ ls -la            │ cmd /c dir -la              │ ls -la
  grep pattern file │ grep pattern file │ cmd /c findstr pattern file │ grep pattern file
  ping 8.8.8.8      │ ping -c 4 8.8.8.8 │ cmd /c ping -n 4 8.8.8.8    │ ping -c 4 8.8.8.8
  rm -rf cache/     │ rm -rf cache/     │ cmd /c del -rf cache/       │ rm -rf cache/

💡 无论你使用哪个平台, 输入任一命令名, Butler 会自动翻译执行。
```

---

## 8. 底层执行命令

Butler 还提供直接执行 Python 和 Shell 的底层命令：

### py — 执行 Python 代码

```bash
py -c "print('hello world')"
py -c "import os; print(os.getcwd())"
py -f script.py
```

### sh — 执行 Shell 命令

```bash
sh -c "echo hello && ls -la"
sh -c "pip install requests"
```

---

## 9. 命令总览

| 类别 | 命令数 | 说明 |
|---|---|---|
| Butler 技能命令 | 34 | 文档/压缩/系统/安全/云盘/剪贴板 |
| Butler 网络命令 | 9 | 天气/爬虫/邮件/翻译/图片搜索 |
| Butler 安全命令 | 4 | 加密/解密/审计 |
| Butler 文档命令 | 5 | 格式转换/文件操作 |
| Butler 系统命令 | 5 | 监控/依赖/诊断/技能列表 |
| Butler 对话命令 | 15 | 帮助/状态/专注/任务/记忆等 |
| **跨平台命令解释工具** | **8** | cmd_explain / explain / cmd_translate / cmd_compare / compare / os_help / oslist / oscommands |
| OS 原生命令 | 106 | 跨平台 Linux/Win/macOS |
| **总计** | **186** | |
