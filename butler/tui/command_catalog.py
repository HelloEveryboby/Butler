# -*- coding: utf-8 -*-
"""Butler 命令目录 - 完整的命令注册、模糊搜索与意图发现系统.

解决的核心问题:
  1. 只记得命令的一部分 → 模糊匹配 + 前缀匹配 + 子串匹配
  2. 知道有这个命令但忘了名字 → "你是想说?" 拼写纠正
  3. 知道要做什么但不知道命令 → 自然语言意图→命令映射
  4. 知道命令但不知道怎么用 → 每条命令的详细用法说明
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional


@dataclass
class CommandEntry:
    """一条命令的完整描述."""
    name: str                           # 主命令名, 如 "weather"
    aliases: list[str]                  # 别名, 如 ["wt", "天", "天气"]
    category: str                       # 分类: 网络/安全/文档/系统/对话/技能
    description: str                    # 一句话说明
    usage: str                          # 用法示例
    detail: str                         # 详细说明
    tags: list[str]                     # 搜索标签 (中英文)
    example: str = ""                   # 输入示例


# ── 命令注册表 ──────────────────────────────────────────────

COMMANDS: list[CommandEntry] = [
    # ── 网络 ──
    CommandEntry(
        name="weather", aliases=["wt", "天", "天气", "tianqi"],
        category="🌐 网络",
        description="查询城市实时天气",
        usage="/weather <城市名>",
        detail="查询指定城市的当前天气状况，包括温度、湿度、风力等。\n不需要参数时会默认查询北京。",
        tags=["天气", "weather", "温度", "气温", "下雨", "刮风", "晴", "阴"],
        example="/weather 上海",
    ),
    CommandEntry(
        name="crawl_url", aliases=["crawl", "爬", "爬虫", "抓取", "fetch"],
        category="🌐 网络",
        description="爬取指定 URL 的网页内容",
        usage="/crawl_url <url>",
        detail="给定一个网页地址，爬取并提取页面文本内容。\n适合快速获取网页信息。",
        tags=["爬虫", "crawl", "抓取", "网页", "url", "fetch", "scrape"],
        example="/crawl_url https://example.com",
    ),
    CommandEntry(
        name="crawl_query", aliases=["search", "搜", "搜索爬取"],
        category="🌐 网络",
        description="通过搜索引擎搜索关键词并爬取结果",
        usage="/crawl_query <关键词>",
        detail="输入关键词，通过搜索引擎查找并爬取相关网页内容。",
        tags=["搜索", "search", "查询", "关键词", "百度", "google"],
        example="/crawl_query Python教程",
    ),
    CommandEntry(
        name="email_send", aliases=["mail", "邮件", "发邮件", "发送", "send"],
        category="🌐 网络",
        description="发送电子邮件",
        usage="/email_send <收件人> | <主题> | <正文>",
        detail="通过配置的邮箱账户发送邮件。需要先在设置中配置邮箱。\n参数用 | 分隔：收件人 | 主题 | 正文",
        tags=["邮件", "email", "发送", "写信", "mail", "send"],
        example="/email_send user@example.com | 会议通知 | 明天下午3点开会",
    ),
    CommandEntry(
        name="email_recv", aliases=["recv", "收邮件", "收件"],
        category="🌐 网络",
        description="检查并显示未读邮件",
        usage="/email_recv",
        detail="拉取邮箱中的未读邮件列表，显示发件人、主题和摘要。",
        tags=["收件", "邮件", "email", "receive", "未读"],
        example="/email_recv",
    ),
    CommandEntry(
        name="img_search", aliases=["img", "图", "搜图", "图片搜索"],
        category="🌐 网络",
        description="通过关键词搜索网络图片",
        usage="/img_search <关键词>",
        detail="根据关键词在网络上搜索相关图片。",
        tags=["图片", "image", "搜索", "搜图", "photo", "图"],
        example="/img_search 猫咪",
    ),
    CommandEntry(
        name="translate", aliases=["tr", "翻译", "fy", "译"],
        category="🌐 网络",
        description="翻译文本内容",
        usage="/translate <文本>",
        detail="将输入的文本翻译为目标语言（默认中英互译）。\n也支持翻译文件和网页。",
        tags=["翻译", "translate", "中英", "英文", "中文", "language"],
        example="/translate Hello World",
    ),
    CommandEntry(
        name="translate_file", aliases=["trf", "翻译文件"],
        category="🌐 网络",
        description="翻译整个文件内容",
        usage="/translate_file <文件路径>",
        detail="读取指定文件的全部内容并翻译，结果保存为 .translated.txt。",
        tags=["翻译", "文件", "translate", "file"],
        example="/translate_file readme.txt",
    ),
    CommandEntry(
        name="translate_url", aliases=["tru", "翻译网页"],
        category="🌐 网络",
        description="翻译网页内容",
        usage="/translate_url <url>",
        detail="爬取指定网页并翻译其内容。",
        tags=["翻译", "网页", "translate", "url"],
        example="/translate_url https://example.com",
    ),

    # ── 安全 ──
    CommandEntry(
        name="encrypt", aliases=["enc", "加密", "jiami", "lock"],
        category="🔐 安全",
        description="使用 AES 加密文件",
        usage="/encrypt <文件路径>",
        detail="使用 AES-256 对称加密算法加密指定文件。\n需要输入 6 位核心码作为加密密钥。\n加密后生成 .enc 文件。",
        tags=["加密", "encrypt", "AES", "安全", "保护", "锁"],
        example="/encrypt secret.txt",
    ),
    CommandEntry(
        name="decrypt", aliases=["dec", "解密", "jiemi", "unlock"],
        category="🔐 安全",
        description="解密已加密的文件",
        usage="/decrypt <文件路径>",
        detail="解密之前用 /encrypt 加密的文件。\n需要输入相同的 6 位核心码。",
        tags=["解密", "decrypt", "AES", "解锁", "还原"],
        example="/decrypt secret.txt.enc",
    ),
    CommandEntry(
        name="audit_security", aliases=["audit", "审计", "安全检查", "sec"],
        category="🔐 安全",
        description="执行全面系统安全审计",
        usage="/audit_security",
        detail="对系统进行全面的安全自检审计，生成安全报告。\n检查权限、配置、漏洞等。",
        tags=["审计", "安全", "audit", "检查", "漏洞", "security"],
        example="/audit_security",
    ),
    CommandEntry(
        name="audit_dir", aliases=["auditdir", "目录审计"],
        category="🔐 安全",
        description="审计指定目录",
        usage="/audit_dir <目录路径>",
        detail="对指定目录执行安全审计，检查文件权限、敏感信息等。",
        tags=["审计", "目录", "安全", "audit", "dir"],
        example="/audit_dir /home/user/projects",
    ),

    # ── 文档 ──
    CommandEntry(
        name="convert", aliases=["cv", "转换", "格式转换", "zhuanhuan"],
        category="📄 文档",
        description="转换文件格式 (如 docx→pdf)",
        usage="/convert <输入文件> -> <输出文件>",
        detail="在不同文档格式之间转换，支持 docx/pdf/html/markdown 等格式。\n用 -> 分隔输入和输出路径。",
        tags=["转换", "convert", "格式", "docx", "pdf", "markdown", "html"],
        example="/convert report.docx -> report.pdf",
    ),
    CommandEntry(
        name="file_create", aliases=["fc", "创建文件", "新建文件", "mkfile"],
        category="📄 文档",
        description="创建新文件",
        usage="/file_create <路径> | <内容>",
        detail="在指定路径创建新文件，可同时写入初始内容。\n用 | 分隔路径和内容。",
        tags=["创建", "文件", "新建", "create", "file"],
        example="/file_create notes.txt | 这是笔记内容",
    ),
    CommandEntry(
        name="file_read", aliases=["fr", "读取", "查看文件", "cat"],
        category="📄 文档",
        description="读取文件内容",
        usage="/file_read <文件路径>",
        detail="读取并显示指定文件的完整内容。",
        tags=["读取", "文件", "查看", "read", "cat", "打开"],
        example="/file_read config.yaml",
    ),
    CommandEntry(
        name="file_delete", aliases=["fd", "删除文件", "rm", "del"],
        category="📄 文档",
        description="删除指定文件",
        usage="/file_delete <文件路径>",
        detail="永久删除指定文件（不可恢复，请谨慎使用）。",
        tags=["删除", "文件", "delete", "rm", "移除"],
        example="/file_delete temp.log",
    ),
    CommandEntry(
        name="file_list", aliases=["fl", "ls", "列出", "目录列表"],
        category="📄 文档",
        description="列出目录下的文件和子目录",
        usage="/file_list <目录路径>",
        detail="列出指定目录下的所有文件和子文件夹名称。",
        tags=["列出", "目录", "list", "ls", "文件列表"],
        example="/file_list /home/user",
    ),

    # ── 系统 ──
    CommandEntry(
        name="monitor", aliases=["mon", "监控", "系统监控", "jiankong"],
        category="⚙️ 系统",
        description="运行系统健康监控",
        usage="/monitor",
        detail="检测并报告系统资源使用情况，包括 CPU、内存、磁盘等。",
        tags=["监控", "monitor", "系统", "健康", "资源", "CPU", "内存"],
        example="/monitor",
    ),
    CommandEntry(
        name="dep_install", aliases=["dep", "安装依赖", "pip", "install"],
        category="⚙️ 系统",
        description="安装 Python 依赖包",
        usage="/dep_install [包名]",
        detail="安装指定的 Python 包。不指定包名时安装核心依赖。\n也可用 dep_all 一键安装全部依赖。",
        tags=["依赖", "安装", "install", "pip", "包"],
        example="/dep_install requests",
    ),
    CommandEntry(
        name="dep_all", aliases=["depall", "全量安装", "install_all"],
        category="⚙️ 系统",
        description="一键安装全部依赖",
        usage="/dep_all",
        detail="安装 Butler 运行所需的全部依赖包。",
        tags=["依赖", "安装", "全部", "install", "all"],
        example="/dep_all",
    ),
    CommandEntry(
        name="doctor", aliases=["doc", "诊断", "体检", "检查", "check"],
        category="⚙️ 系统",
        description="运行系统诊断自检",
        usage="/doctor",
        detail="对 Butler 核心运行层、数据库、包依赖进行全面体检。\n适合排查启动问题或异常。",
        tags=["诊断", "doctor", "体检", "检查", "自检", "health"],
        example="/doctor",
    ),
    CommandEntry(
        name="skills_list", aliases=["skills", "技能列表", "skill"],
        category="⚙️ 系统",
        description="列出所有已加载的技能",
        usage="/skills_list",
        detail="显示当前已加载的所有 Butler 技能及其描述。",
        tags=["技能", "skill", "列表", "插件", "plugin"],
        example="/skills_list",
    ),

    # ── 对话/管理 ──
    CommandEntry(
        name="help", aliases=["h", "?", "帮助", "bz"],
        category="💬 对话",
        description="显示帮助信息",
        usage="/help [命令名]",
        detail="不带参数显示全部命令概览。\n带命令名显示该命令的详细用法，如 /help weather。",
        tags=["帮助", "help", "用法", "说明", "?"],
        example="/help encrypt",
    ),
    CommandEntry(
        name="commands", aliases=["cmd", "命令列表", "所有命令", "allcmd"],
        category="💬 对话",
        description="浏览所有可用命令（带搜索功能）",
        usage="/commands [关键词]",
        detail="按分类列出所有命令。加关键词可过滤。\n如 /commands 加密 只显示安全相关命令。",
        tags=["命令", "列表", "所有", "commands", "浏览"],
        example="/commands 安全",
    ),
    CommandEntry(
        name="howto", aliases=["how", "怎么做", "如何", "怎么"],
        category="💬 对话",
        description="根据你想做的事情推荐命令",
        usage="/howto <你想做什么>",
        detail="用自然语言描述你想做的事，Butler 会推荐合适的命令。\n如: /howto 我想加密一个文件",
        tags=["怎么做", "如何", "how", "推荐", "建议", "想"],
        example="/howto 我想查一下上海的天气",
    ),
    CommandEntry(
        name="status", aliases=["st", "状态", "系统状态"],
        category="💬 对话",
        description="查看 Butler 系统状态",
        usage="/status",
        detail="显示当前 Butler 运行状态、连接模式等基本信息。",
        tags=["状态", "status", "信息", "系统"],
        example="/status",
    ),
    CommandEntry(
        name="kairos", aliases=["kai", "性能", "电池"],
        category="💬 对话",
        description="查看 KAIROS 性能调度状态",
        usage="/kairos",
        detail="显示当前性能模式、电池状态、节流状态等。",
        tags=["性能", "kairos", "电池", "节流", "省电"],
        example="/kairos",
    ),
    CommandEntry(
        name="performance", aliases=["perf", "模式", "性能模式"],
        category="💬 对话",
        description="切换性能模式 (high/eco/normal)",
        usage="/performance <high|eco|normal>",
        detail="切换 Butler 的运行性能模式：\n  high - 高性能模式（耗电多）\n  eco - 低功耗模式（省电）\n  normal - 标准模式",
        tags=["性能", "模式", "performance", "省电", "高速"],
        example="/performance eco",
    ),
    CommandEntry(
        name="dream", aliases=["dr", "做梦", "记忆整理"],
        category="💬 对话",
        description="手动触发做梦引擎（记忆整合）",
        usage="/dream",
        detail="手动启动 Butler 的做梦引擎，整理和整合长期记忆。",
        tags=["做梦", "dream", "记忆", "整理", "整合"],
        example="/dream",
    ),
    CommandEntry(
        name="focus", aliases=["fo", "专注", "番茄钟", "集中"],
        category="💬 对话",
        description="启动专注模式",
        usage="/focus [分钟数]",
        detail="启动专注模式，默认 25 分钟。期间减少非紧急通知。\n相当于番茄钟功能。",
        tags=["专注", "focus", "番茄钟", "集中", "工作"],
        example="/focus 30",
    ),
    CommandEntry(
        name="focus-stop", aliases=["fostop", "停止专注"],
        category="💬 对话",
        description="停止专注模式",
        usage="/focus-stop",
        detail="提前结束专注模式，恢复正常通知。",
        tags=["专注", "停止", "取消"],
        example="/focus-stop",
    ),
    CommandEntry(
        name="clear", aliases=["cl", "清空", "cls"],
        category="💬 对话",
        description="清空对话记录",
        usage="/clear",
        detail="清空当前对话区域的所有消息。",
        tags=["清空", "clear", "cls", "清除"],
        example="/clear",
    ),
    CommandEntry(
        name="tasks", aliases=["task", "任务", "看板"],
        category="💬 对话",
        description="查看任务看板",
        usage="/tasks",
        detail="切换到任务视图，显示所有持久化业务任务。",
        tags=["任务", "task", "看板", "待办"],
        example="/tasks",
    ),
    CommandEntry(
        name="team", aliases=["tm", "团队", "队友"],
        category="💬 对话",
        description="查看团队成员",
        usage="/team",
        detail="显示当前 Butler 协作团队成员列表及状态。",
        tags=["团队", "team", "队友", "协作"],
        example="/team",
    ),
    CommandEntry(
        name="memory", aliases=["mem", "记忆", "备忘"],
        category="💬 对话",
        description="查看记忆库",
        usage="/memory",
        detail="切换到记忆视图，查看备忘录和长期记忆。",
        tags=["记忆", "memory", "备忘", "回忆"],
        example="/memory",
    ),
    CommandEntry(
        name="profile", aliases=["pf", "画像", "习惯"],
        category="💬 对话",
        description="查看用户画像",
        usage="/profile",
        detail="显示 Butler 学习到的用户偏好和习惯画像。",
        tags=["画像", "profile", "习惯", "偏好"],
        example="/profile",
    ),
    CommandEntry(
        name="exit", aliases=["quit", "q", "退出", "再见", "拜拜"],
        category="💬 对话",
        description="退出 Butler",
        usage="/exit",
        detail="安全退出 Butler TUI 界面。",
        tags=["退出", "exit", "quit", "再见", "关闭"],
        example="/exit",
    ),

    # ── 技能 (无 AI 可用) ──
    CommandEntry(
        name="markitdown", aliases=["md", "转markdown", "to_md"],
        category="🧰 技能",
        description="将文件转为 Markdown (支持 PDF/DOCX/PPTX/XLSX/HTML 等)",
        usage="/markitdown <文件路径>",
        detail="将各种格式的文件转换为 Markdown 文本。\n支持: PDF, DOCX, PPTX, XLSX, HTML, CSV, EPUB, 图片等。",
        tags=["markdown", "转换", "markitdown", "文档", "pdf", "docx"],
        example="/markitdown report.pdf",
    ),
    CommandEntry(
        name="docx_read", aliases=["dr_word", "读word", "读文档"],
        category="🧰 技能",
        description="读取 Word 文档内容",
        usage="/docx_read <文件路径>",
        detail="提取 .docx 文件的全部文本内容。",
        tags=["word", "docx", "读取", "文档"],
        example="/docx_read report.docx",
    ),
    CommandEntry(
        name="docx_create", aliases=["dc_word", "建word", "新建文档"],
        category="🧰 技能",
        description="创建新的 Word 文档",
        usage="/docx_create <输出路径> | <标题> | <内容>",
        detail="创建一个新的 .docx 文件，可指定标题和正文内容。\n参数用 | 分隔：路径 | 标题 | 内容",
        tags=["word", "docx", "创建", "新建"],
        example="/docx_create new.docx | 我的文档 | 这是正文",
    ),
    CommandEntry(
        name="pdf_extract", aliases=["pe", "提取pdf", "pdf文本"],
        category="🧰 技能",
        description="提取 PDF 文本内容",
        usage="/pdf_extract <文件路径>",
        detail="提取 PDF 文件中的全部文本。",
        tags=["pdf", "提取", "文本", "extract"],
        example="/pdf_extract paper.pdf",
    ),
    CommandEntry(
        name="pdf_merge", aliases=["pm", "合并pdf", "pdf合并"],
        category="🧰 技能",
        description="合并多个 PDF 文件",
        usage="/pdf_merge <文件1>,<文件2>,... | <输出路径>",
        detail="将多个 PDF 文件合并为一个。\n参数用 | 分隔：文件列表(逗号分隔) | 输出路径",
        tags=["pdf", "合并", "merge"],
        example="/pdf_merge a.pdf,b.pdf | merged.pdf",
    ),
    CommandEntry(
        name="pdf_split", aliases=["ps", "拆分pdf", "pdf拆分"],
        category="🧰 技能",
        description="拆分 PDF 文件",
        usage="/pdf_split <文件路径>",
        detail="将 PDF 的每一页拆分为单独的 PDF 文件。",
        tags=["pdf", "拆分", "split"],
        example="/pdf_split large.pdf",
    ),
    CommandEntry(
        name="archive_compress", aliases=["ac", "压缩", "打包", "zip"],
        category="🧰 技能",
        description="压缩文件或目录 (7z/zip)",
        usage="/archive_compress <输出路径> | <目标路径> [| 密码]",
        detail="使用 7-Zip 引擎压缩文件或目录。\n支持 .7z, .zip, .tar.gz 等格式。\n可选密码加密 (仅 .7z 支持文件名加密)。",
        tags=["压缩", "7z", "zip", "archive", "打包"],
        example="/archive_compress backup.7z | /home/user/docs",
    ),
    CommandEntry(
        name="archive_extract", aliases=["ae", "解压", "解包", "unzip"],
        category="🧰 技能",
        description="解压压缩包",
        usage="/archive_extract <压缩包路径> [| 输出目录] [| 密码]",
        detail="解压 .7z, .zip, .tar.gz 等格式的压缩包。\n可选指定输出目录和解压密码。",
        tags=["解压", "7z", "zip", "archive", "解包"],
        example="/archive_extract backup.7z | /tmp/output",
    ),
    CommandEntry(
        name="archive_list", aliases=["al", "列出压缩", "查看压缩包"],
        category="🧰 技能",
        description="列出压缩包内容",
        usage="/archive_list <压缩包路径>",
        detail="列出压缩包内的所有文件和目录，不解压。",
        tags=["压缩", "列出", "list", "archive"],
        example="/archive_list backup.7z",
    ),
    CommandEntry(
        name="uninstaller", aliases=["uninst", "卸载", "软件管理"],
        category="🧰 技能",
        description="列出/卸载已安装软件",
        usage="/uninstaller [list | uninstall <软件名>]",
        detail="列出系统中已安装的软件，或卸载指定软件。\n不带参数默认列出软件列表。",
        tags=["卸载", "uninstall", "软件", "清理"],
        example="/uninstaller list",
    ),
    CommandEntry(
        name="sys_clean", aliases=["clean", "系统清理", "垃圾清理"],
        category="🧰 技能",
        description="系统垃圾清理 (安装前后快照差异)",
        usage="/sys_clean [track | clean]",
        detail="track: 开始追踪安装变更\nclean: 清理系统垃圾\n不带参数显示帮助。",
        tags=["清理", "clean", "垃圾", "快照"],
        example="/sys_clean clean",
    ),
    CommandEntry(
        name="media_scan", aliases=["ms", "扫描媒体", "音乐扫描"],
        category="🧰 技能",
        description="扫描全盘媒体文件",
        usage="/media_scan",
        detail="扫描所有盘符和挂载点的 MP3/WAV/JPG 文件，建立媒体库。",
        tags=["媒体", "music", "扫描", "mp3", "图片"],
        example="/media_scan",
    ),
    CommandEntry(
        name="storage_hub", aliases=["sh", "云盘", "网盘"],
        category="🧰 技能",
        description="管理多云盘存储 (OneDrive/WebDAV/百度)",
        usage="/storage_hub [list | upload <路径> | download <文件>]",
        detail="管理已配置的云盘适配器，支持文件上传/下载/列表。\n不带参数列出已配置的云盘。",
        tags=["云盘", "storage", "onedrive", "webdav", "百度"],
        example="/storage_hub list",
    ),
    CommandEntry(
        name="clip_magic", aliases=["cm", "剪贴板分类", "剪贴板"],
        category="🧰 技能",
        description="启动剪贴板智能分类服务",
        usage="/clip_magic",
        detail="启动后台剪贴板监听服务，自动分类 URL/IP/代码/纯文本。",
        tags=["剪贴板", "clipboard", "分类", "classify"],
        example="/clip_magic",
    ),
    CommandEntry(
        name="sec_scan", aliases=["sscan", "端口扫描", "syn扫描"],
        category="🧰 技能",
        description="SYN 端口扫描",
        usage="/sec_scan <目标IP>",
        detail="对指定目标执行 SYN 端口扫描，发现开放端口。",
        tags=["端口", "扫描", "scan", "安全", "syn"],
        example="/sec_scan 127.0.0.1",
    ),
    CommandEntry(
        name="web_sec_test", aliases=["wst", "web安全", "web测试"],
        category="🧰 技能",
        description="Web 安全测试 (nmap + nuclei)",
        usage="/web_sec_test <目标URL> [| recon|scan|full]",
        detail="对指定目标执行 Web 安全测试。\n模式: recon(侦察), scan(扫描), full(完整)。\n默认 full。",
        tags=["web", "安全", "测试", "security", "nmap"],
        example="/web_sec_test https://example.com",
    ),
    CommandEntry(
        name="format_convert", aliases=["fc_skill", "格式转换技能"],
        category="🧰 技能",
        description="Markdown 转换为 DOCX/EPUB/图片等",
        usage="/format_convert <输入文件> | <输出格式>",
        detail="将 Markdown 文件转换为 DOCX/EPUB/图片/HTML 等格式。\n输出格式: docx, epub, png, html。",
        tags=["转换", "convert", "markdown", "docx", "epub"],
        example="/format_convert readme.md | docx",
    ),
]

# 构建快速查找索引
_BY_NAME: dict[str, CommandEntry] = {}
_BY_ALIAS: dict[str, CommandEntry] = {}

for _cmd in COMMANDS:
    _BY_NAME[_cmd.name.lower()] = _cmd
    for _alias in _cmd.aliases:
        _BY_ALIAS[_alias.lower()] = _cmd


# ── 模糊匹配引擎 ────────────────────────────────────────────

def _score_similarity(query: str, target: str) -> float:
    """计算 query 和 target 的相似度 (0~1)."""
    q, t = query.lower(), target.lower()
    if q == t:
        return 1.0
    if t.startswith(q):
        return 0.9
    if q in t:
        return 0.8
    # 序列相似度
    return SequenceMatcher(None, q, t).ratio()


def find_command(raw_input: str, limit: int = 5) -> list[tuple[CommandEntry, float]]:
    """根据用户输入模糊查找命令，返回 (命令, 匹配分) 列表，按分降序."""
    query = raw_input.strip().lower().lstrip("/")
    if not query:
        return [(c, 1.0) for c in COMMANDS[:limit]]

    scored: list[tuple[CommandEntry, float]] = []

    for cmd in COMMANDS:
        best = 0.0
        # 精确匹配名称
        if query == cmd.name.lower():
            best = 1.0
        # 精确匹配别名
        elif query in [a.lower() for a in cmd.aliases]:
            best = 0.95
        else:
            # 名称模糊
            best = max(best, _score_similarity(query, cmd.name))
            # 别名模糊
            for alias in cmd.aliases:
                best = max(best, _score_similarity(query, alias))
            # 标签匹配
            for tag in cmd.tags:
                if query in tag.lower() or tag.lower() in query:
                    best = max(best, 0.7)
            # 描述关键词
            if query in cmd.description.lower():
                best = max(best, 0.6)
            # 分类
            if query in cmd.category.lower():
                best = max(best, 0.5)

        if best > 0.3:
            scored.append((cmd, best))

    scored.sort(key=lambda x: -x[1])
    return scored[:limit]


def find_by_intent(description: str, limit: int = 5) -> list[tuple[CommandEntry, float]]:
    """根据自然语言意图描述推荐命令.

    例如: "我想加密一个文件" → encrypt
          "查天气" → weather
          "把word转成pdf" → convert
    """
    desc = description.lower()
    scored: list[tuple[CommandEntry, float]] = []

    for cmd in COMMANDS:
        score = 0.0
        # 核心词直接命中 (高权重)
        for tag in cmd.tags:
            if tag.lower() in desc:
                score += 0.4
        # 名称或别名直接命中
        for token in re.split(r"[，,、\s]+", desc):
            token = token.strip()
            if not token:
                continue
            if token == cmd.name.lower():
                score += 0.5
            for alias in cmd.aliases:
                if token == alias.lower():
                    score += 0.45
                elif token in alias.lower() or alias.lower() in token:
                    score += 0.25
        # 描述关键词
        for word in re.split(r"[，,、\s]+", desc):
            word = word.strip()
            if not word or len(word) < 2:
                continue
            if word in cmd.description.lower():
                score += 0.2
            for tag in cmd.tags:
                if word in tag.lower():
                    score += 0.15
        # 分类
        for word in re.split(r"[，,、\s]+", desc):
            word = word.strip()
            if word and word in cmd.category.lower():
                score += 0.1

        if score > 0:
            scored.append((cmd, min(score, 1.0)))

    scored.sort(key=lambda x: -x[1])
    return scored[:limit]


def get_command(name: str) -> Optional[CommandEntry]:
    """精确查找命令 (名称或别名)."""
    name = name.lower().lstrip("/")
    if name in _BY_NAME:
        return _BY_NAME[name]
    if name in _BY_ALIAS:
        return _BY_ALIAS[name]
    return None


def suggest_for_unknown(input_name: str) -> list[CommandEntry]:
    """为未知命令提供 "你是想说?" 建议."""
    results = find_command(input_name, limit=3)
    return [cmd for cmd, _score in results if _score >= 0.5]


def format_command_help(cmd: CommandEntry) -> str:
    """格式化单条命令的详细帮助."""
    aliases_str = ", ".join(cmd.aliases) if cmd.aliases else "无"
    lines = [
        f"[bold]{cmd.name}[/bold]  ({cmd.category})",
        f"  {cmd.description}",
        f"",
        f"  用法:  {cmd.usage}",
        f"  别名:  {aliases_str}",
        f"",
        f"  {cmd.detail}",
    ]
    if cmd.example:
        lines.append(f"")
        lines.append(f"  示例:  [cyan]{cmd.example}[/cyan]")
    return "\n".join(lines)


def format_command_overview(filter_key: str = "") -> str:
    """格式化命令概览（可按关键词过滤）."""
    sections: dict[str, list[CommandEntry]] = {}
    for cmd in COMMANDS:
        if filter_key:
            fk = filter_key.lower()
            matched = (
                fk in cmd.name.lower()
                or fk in cmd.category.lower()
                or fk in cmd.description.lower()
                or any(fk in t.lower() for t in cmd.tags)
                or any(fk in a.lower() for a in cmd.aliases)
            )
            if not matched:
                continue
        sections.setdefault(cmd.category, []).append(cmd)

    lines = []
    for cat, cmds in sections.items():
        lines.append(f"\n[bold]{cat}[/bold]")
        for cmd in cmds:
            alias_hint = f" (别名: {', '.join(cmd.aliases[:3])})" if cmd.aliases else ""
            lines.append(f"  [cyan]/{cmd.name:<16}[/cyan] {cmd.description}{alias_hint}")
        lines.append("")

    if not lines:
        return f"没有找到与 '{filter_key}' 相关的命令。试试 /howto <你想做什么>"

    return "\n".join(lines)
