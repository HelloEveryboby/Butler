# 📖 Butler 技能目录（自动生成）

> ⚠️ 本文件由 `scripts/gen_skill_catalog.py` 自动生成，请勿手动编辑。
> 重新生成：`python scripts/gen_skill_catalog.py` 或 `butler skills catalog`
>
> 调用方式：`butler skill info <技能名>` 查看详情 / `butler skill run <技能名>` 运行

共 **22** 个技能：

| 技能 | 说明 | 标签 |
| :--- | :--- | :--- |
| **AI Memory Service (AI 记忆服务)** | 基于 `ai-memory` 架构思想的本地 AI 记忆系统： - **事实来源 (Source of Truth)**：Markdown 文件 (`.butler-memory/YYYY-MM-DD-标题.md` 与 FrontMatte | — |
| **Butler Expert Skill (butler_expert)** | 精通 HelloEveryboby/Butler 智能助手系统的架构、功能、部署与开发。适用于解答关于其 AI 对话、算法库、REST API、多模式 UI、插件系统、RAG 本地知识库、语音交互等全方面的问题。 | — |
| **calculator** | 全能科学计算器与单位换算器。支持四则运算、幂运算、三角函数、对数、常量，以及长度/重量/温度/数据存储等单位换算。 | — |
| **ClipMagic** | Smart clipboard background service with AST/Regex detection. | — |
| **code_formatter** | 代码与数据格式化工具。支持 JSON、YAML、XML 的美化排版、压缩、校验，并可自动检测格式。 | — |
| **daily_fashion_stylist** | 视觉风格管家。综合分析用户的个人风格偏好、实时天气信息（温度、天气状况、风力等），提供当日穿搭建议，包括色彩搭配、单品组合和风格指导。适用于用户询问“今天穿什么”、“帮我搭配一套衣服”等场景。 | — |
| **Dream 自改进引擎 (dream)** | 递归自我改进（RSI）技能：把 Butler 的发现历史当作**回放模拟器**，在闲置时"做梦"—— 零执行成本地评估成千上万个替代探索策略，选出不退化的改进策略并重部署， 驱动自动化任务/技能组合的持续自我优化。 | — |
| **expense_tracker** | 个人记账与消费统计工具。记录收支、按类别/月份汇总、生成消费报告，数据本地 JSON 存储。 | — |
| **habit_tracker** | 习惯打卡与连续天数追踪工具。创建习惯、每日打卡、统计连续天数与完成率，本地 JSON 存储。 | — |
| **Hello CLI** | 一个用于测试 CLI 动态加载的示例技能。 | — |
| **hot_swap_test** | Butler 核心架构验证：热插拔与隔离运行示例。 | — |
| **Karpathy Guidelines** | Behavioral guidelines to reduce common LLM coding mistakes, derived from [Andrej Karpathy's observations](https://x.com/ | — |
| **office-suite-expert** | 微软 Office 官方套件全能助手。精通 Word 文档排版、Excel 数据分析与公式、PowerPoint 演示设计、Outlook 邮件管理及 OneNote 笔记整理。当用户需要创建文档、处理表格、制作幻灯片、管理邮件或整理笔记时，应启用此技能。 | — |
| **password_generator** | 安全密码与口令生成器。基于密码学安全随机数生成高熵密码、易记口令短语、PIN 码，并支持强度评估。 | — |
| **photoshop-expert** | Adobe Photoshop 图像处理专家。精通图层与蒙版、选区与抠图、调色与校色、修图与美化、文字特效、滤镜应用及基础设计。当用户需要编辑图像、合成照片、设计图形或优化图片时，应启用此技能。 | — |
| **Pixel Pet** | 极致优雅、伴随启动、基于 PyWebview 独立透明置顶微型窗口的 Butler 像素电子宠物。 | — |
| **text_analyzer** | 文本分析与统计工具。提供字数、词频、句子统计、中英文可读性评估、关键词提取等能力。 | — |
| **translator** | 一个简单的翻译技能，支持中英文互译。 | — |
| **wps-office-expert** | WPS Office 官方套件全能助手。精通 WPS 文字排版与审校、WPS 表格数据处理与函数、WPS 演示设计、WPS PDF 编辑与转换，以及 WPS AI 智能办公辅助。当用户需要处理 WPS 相关文档、表格、演示或 PDF 时，应启用此技能。 | — |
| **截图即排障** | 自动分析报错截图并提供一键修复方案。 | — |
| **文档协同创作工作流** | 引导用户通过结构化工作流进行文档协同创作。适用于编写文档、提案、技术规范、决策文档等。 | — |
| **灵动对话者** | 让 AI 化身为“小米”——一个温暖、幽默、会吐槽但永远不刻薄的人类朋友。 | — |

---

想写自己的技能？一个文件夹 = 一个技能，参考 **[SKILL_FRONTMATTER 规范](../docs/dev/SKILL_FRONTMATTER.md)** 与 [贡献指南](../docs/SKILLS_GUIDE.md)。
