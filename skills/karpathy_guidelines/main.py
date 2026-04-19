import os
import logging

# 获取日志记录器
logger = logging.getLogger("KarpathyGuidelinesSkill")

PRINCIPLES = {
    "1": {
        "title": "编码前思考 (Think Before Coding)",
        "content": "不要假设。不要隐藏困惑。呈现权衡。\n\n- 明确说明假设：如果不确定，询问而不是猜测。\n- 呈现多种解释：当存在歧义时，不要默默选择。\n- 适时提出异议：如果存在更简单的方法，说出来。\n- 困惑时停下来：指出不清楚的地方并要求澄清。"
    },
    "2": {
        "title": "简洁优先 (Simplicity First)",
        "content": "用最少的代码解决问题。不要过度推测。\n\n- 不要添加要求之外的功能。\n- 不要为一次性代码创建抽象。\n- 不要添加未要求的“灵活性”或“可配置性”。\n- 不要为不可能发生的场景做错误处理。\n- 如果 200 行代码可以写成 50 行，重写它。"
    },
    "3": {
        "title": "精准修改 (Surgical Changes)",
        "content": "只碰必须碰的。只清理自己造成的混乱。\n\n- 不要“改进”相邻的代码、注释或格式。\n- 不要重构没坏的东西。\n- 匹配现有风格，即使你更倾向于不同的写法。\n- 如果注意到无关的死代码，提一下 —— 不要删除它。"
    },
    "4": {
        "title": "目标驱动执行 (Goal-Driven Execution)",
        "content": "定义成功标准。循环验证直到达成。\n\n- 将指令式任务转化为可验证的目标（如：先写测试）。\n- 对于多步骤任务，说明一个简短的计划并逐一验证。\n- 强有力的成功标准让 AI 能够独立循环执行。"
    }
}

def handle_request(action, **kwargs):
    """
    处理 Karpathy Guidelines 技能的请求。
    """
    if action == "list_principles" or action == "show_all":
        report = ["## Karpathy 开发准则核心原则："]
        for key, p in PRINCIPLES.items():
            report.append(f"### {key}. {p['title']}")
            report.append(p['content'])
        return "\n\n".join(report)

    if action == "show":
        entities = kwargs.get("entities", {})
        query = entities.get("principle_id") or kwargs.get("principle_id")

        if not query:
            # 尝试从关键词匹配
            command = kwargs.get("command", "").lower()
            if "思考" in command or "think" in command: query = "1"
            elif "简洁" in command or "simple" in command: query = "2"
            elif "修改" in command or "surgical" in command: query = "3"
            elif "目标" in command or "goal" in command: query = "4"

        if query in PRINCIPLES:
            p = PRINCIPLES[query]
            return f"### {p['title']}\n\n{p['content']}"

        return handle_request("list_principles")

    return f"错误：Karpathy Guidelines 技能不支持动作 '{action}'。"
