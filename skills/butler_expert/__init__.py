import logging

# 获取日志记录器
logger = logging.getLogger("ButlerExpertSkill")

# Butler 专家知识库
BUTLER_KNOWLEDGE = {
    "intro": {
        "title": "项目核心定位",
        "content": "Butler 是一个功能丰富的 Python 智能助手系统。它采用模块化架构设计，不仅是一个对话式 AI，更是一个集成了强大算法库、可扩展插件系统和多种交互模式的全能型工具平台。它的核心编排器是 Jarvis 类，负责管理信息流和协调各组件。"
    },
    "modules": {
        "ai_dialogue": {
            "title": "对话式 AI",
            "content": "原理：使用 DeepSeek API 进行自然语言理解和响应生成。配置：用户需要在代码或配置文件中设置自己的 DeepSeek API Key。"
        },
        "ui_modes": {
            "title": "多模式用户界面 (UI)",
            "content": "1. 经典模式：基于 Python 标准库 Tkinter 实现的 GUI 面板，适合本地简单交互。\n2. 现代模式：一个精致的 Web UI，采用“玻璃拟态”设计风格和“无输入框”的流式交互逻辑，用户体验更佳。\n3. 高性能终端：一个基于 PTY 技术的独立弹窗终端，可以脱离主 UI 运行。"
        },
        "algorithms": {
            "title": "高级算法库与 REST API",
            "content": "内容：项目内置了一个丰富、高效且文档齐全的常用算法库。访问：算法库通过开发者友好的 REST API 公开，意味着任何编程语言都可以通过 HTTP 请求调用这些算法。"
        },
        "voice": {
            "title": "语音交互",
            "content": "功能：支持语音命令输入，并利用百度 AI 开放平台进行高质量的语音合成与输出。依赖：使用该功能需要配置百度 AI 的相关凭证。"
        },
        "rag": {
            "title": "本地知识库与记忆 (RAG)",
            "content": "核心技术：集成了阿里云开源的高性能本地向量数据库 Zvec，支持完全离线的语义搜索。能力：可以索引 PDF, Word, Markdown 等多种本地文档，提供基于语义的精准信息检索。扩展：系统也支持 Redis 作为向量存储后端。"
        },
        "automation": {
            "title": "自动化与扩展性",
            "content": "插件系统：PluginManager 动态发现并加载 plugin/ 目录下的模块。包管理：package/ 目录下的独立工具和脚本可被系统动态发现和执行。"
        },
        "others": {
            "title": "其他特色功能",
            "content": "Excel 专家：可进行专业的 Excel 创建、编辑与财务模型分析。多媒体中心：支持 MP3/WAV 音频播放和 JPG 图片查看。"
        }
    },
    "workflow": {
        "title": "架构与工作流",
        "content": "1. 输入 (Input)：通过 GUI、语音或 Web UI 输入命令。\n2. 路由 (Routing)：Jarvis 使用 DeepSeek API 执行自然语言理解，识别意图和实体。\n3. 执行 (Execution)：根据意图路由到相应的模块（Jarvis 直接处理、搜索向量数据库、或通过 PluginManager 调用插件/工具）。\n4. 响应 (Response)：将结果返回给用户。"
    },
    "troubleshooting": {
        "api": {
            "title": "API 出错",
            "content": "问题：对话式 AI 或 语音合成 不工作。解决：检查环境变量或配置文件中的 DeepSeek API Key 与百度 AI 平台凭证 (AK/SK)。"
        },
        "ui": {
            "title": "UI 启动失败",
            "content": "问题：Web UI 无法访问。解决：检查端口是否被占用，参考 docs/FRONTEND_MODERN_UI.md。"
        },
        "plugins": {
            "title": "插件/包加载失败",
            "content": "问题：新添加的插件不能使用。解决：确保插件放置在 plugin/ 或 package/ 目录下，系统启动时会自动发现。"
        },
        "excel": {
            "title": "Excel 功能异常",
            "content": "问题：处理 Excel 文件报错。解决：此功能依赖 LibreOffice，请确保系统中已正确安装。"
        }
    }
}

def handle_request(action, **kwargs):
    """
    处理 Butler 专家技能的请求。
    """
    entities = kwargs.get("entities", {})
    query = entities.get("query") or kwargs.get("query", "").lower()
    command = kwargs.get("command", "").lower()

    if action == "ask":
        return handle_ask(query or command)
    elif action == "explain":
        return handle_explain(query or command)
    elif action == "troubleshoot":
        return handle_troubleshoot(query or command)

    # 默认返回项目定位和核心功能列表
    return format_intro()

def handle_ask(query):
    """
    回答关于 Butler 的一般性问题。
    """
    if not query:
        return format_intro()

    # 简单匹配逻辑
    if any(k in query for k in ["理解", "原理", "怎么跑", "如何工作", "架构", "流程"]):
        return f"### {BUTLER_KNOWLEDGE['workflow']['title']}\n\n{BUTLER_KNOWLEDGE['workflow']['content']}"

    if any(k in query for k in ["功能", "能干什么", "特色"]):
        modules_text = "\n\n".join([f"**{m['title']}**：\n{m['content']}" for m in BUTLER_KNOWLEDGE['modules'].values()])
        return f"## Butler 核心功能模块详解\n\n{modules_text}"

    if any(k in query for k in ["脚本", "开发", "插件", "扩展", "plugin", "package"]):
        return f"### {BUTLER_KNOWLEDGE['modules']['automation']['title']}\n\n{BUTLER_KNOWLEDGE['modules']['automation']['content']}\n\n**建议**：如果是 Python 脚本，直接放在 `plugin/` 目录下即可由 `PluginManager` 自动加载。"

    return f"我是 Butler 专家。关于您的提问 '{query}'，我建议从以下核心定位了解 Butler：\n\n" + format_intro()

def handle_explain(query):
    """
    详细解释特定模块。
    """
    for key, module in BUTLER_KNOWLEDGE["modules"].items():
        if key in query or module["title"] in query:
            return f"### {module['title']}\n\n{module['content']}"

    return "请提供具体的模块名称，例如：AI对话、UI模式、语音交互、本地知识库等。"

def handle_troubleshoot(query):
    """
    故障排查指南。
    """
    if not query or "全" in query or "列表" in query:
        trouble_text = "\n\n".join([f"### {t['title']}\n{t['content']}" for t in BUTLER_KNOWLEDGE['troubleshooting'].values()])
        return f"## Butler 故障排查与常见问题\n\n{trouble_text}"

    for key, trouble in BUTLER_KNOWLEDGE["troubleshooting"].items():
        if key in query or trouble["title"] in query:
            return f"### {trouble['title']}\n\n{trouble['content']}"

    return "未能识别具体的故障类型。请尝试描述您遇到的问题，如：API出错、UI启动失败、插件加载失败等。"

def format_intro():
    """
    格式化项目核心定位信息。
    """
    intro = BUTLER_KNOWLEDGE["intro"]
    return f"### {intro['title']}\n\n{intro['content']}"
