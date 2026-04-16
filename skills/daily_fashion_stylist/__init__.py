import os
import sys
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime

# 获取日志记录器
logger = logging.getLogger("DailyFashionSkill")

def handle_request(action, **kwargs):
    """
    处理每日穿搭 (Daily Fashion Stylist) 技能的请求。
    """
    jarvis_app = kwargs.get("jarvis_app")
    entities = kwargs.get("entities", {})

    # 获取项目根目录和技能目录
    skill_dir = Path(__file__).resolve().parent
    project_root = skill_dir.parent.parent

    # 1. 确定城市
    city = entities.get("city")
    if not city and jarvis_app:
        # 尝试从 habit_manager 获取
        city = jarvis_app.habit_manager._profile["preferences"].get("city") or \
               jarvis_app.habit_manager._profile["preferences"].get("location")

    if not city:
        city = "北京"  # 默认城市

    # 2. 调用天气脚本
    weather_script = skill_dir / "scripts" / "get_weather.py"
    weather_data = {}
    try:
        res = subprocess.run([sys.executable, str(weather_script), city], capture_output=True, text=True, encoding='utf-8')
        weather_data = json.loads(res.stdout)
    except Exception as e:
        logger.error(f"获取天气数据失败: {e}")
        weather_data = {"status": "error", "message": str(e), "city": city}

    # 3. 加载参考数据
    try:
        with open(skill_dir / "references" / "weather_dressing_rules.json", 'r', encoding='utf-8') as f:
            dressing_rules = json.load(f)
        with open(skill_dir / "references" / "style_guide.json", 'r', encoding='utf-8') as f:
            style_guide = json.load(f)
    except Exception as e:
        logger.error(f"加载参考数据失败: {e}")
        dressing_rules = {}
        style_guide = {}

    # 4. 获取今日任务 (Context Awareness)
    today_str = datetime.now().strftime("%Y-%m-%d")
    tasks_content = ""
    tasks_path = project_root / "TASKS.md"
    if tasks_path.exists():
        try:
            with open(tasks_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 简单寻找包含今日日期的行
                relevant_lines = [line for line in content.split('\n') if today_str in line or "今天" in line]
                if relevant_lines:
                    tasks_content = "\n".join(relevant_lines)
        except Exception as e:
            logger.error(f"读取 TASKS.md 失败: {e}")

    # 5. 获取用户画像 (Personalization)
    user_profile = ""
    if jarvis_app:
        user_profile = jarvis_app.habit_manager.get_profile_summary()

    # 6. 构造 AI 提示词
    system_instruction = (
        "你是一位专业的虚拟造型师，精通色彩学、面料知识和流行趋势。你的任务是根据提供的天气、用户偏好和今日行程，提供全方位的穿搭建议。\n\n"
        "### 参考规则：\n"
        f"1. 天气穿搭准则：{json.dumps(dressing_rules, ensure_ascii=False)}\n"
        f"2. 风格与体型指南：{json.dumps(style_guide, ensure_ascii=False)}\n\n"
        "### 输出格式：\n"
        "严格遵循 SKILL.md 中定义的结构化格式，包含 🌤️ 天气速览、🎨 风格定调、👕 上身搭配、👖 下身搭配、💡 今日穿搭口诀。"
    )

    user_prompt = f"城市：{city}\n"
    if weather_data.get("status") == "success":
        user_prompt += f"当前天气：{json.dumps(weather_data, ensure_ascii=False)}\n"
    else:
        user_prompt += f"天气信息获取失败，请根据通用情况建议。\n"

    if tasks_content:
        user_prompt += f"今日行程/任务：\n{tasks_content}\n"

    if user_profile:
        user_prompt += f"用户个人画像：\n{user_profile}\n"

    style_pref = entities.get("style") or "休闲"
    user_prompt += f"用户当前风格偏好：{style_pref}\n"
    user_prompt += "请给出今日穿搭建议。"

    # 7. 调用 LLM 生成回复
    if jarvis_app and hasattr(jarvis_app, 'nlu_service'):
        try:
            advice = jarvis_app.nlu_service.ask_llm(user_prompt, system_prompt=system_instruction)
            return advice
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return "抱歉，生成穿搭建议时遇到了点问题。请稍后再试。"
    else:
        return "Jarvis NLU 服务不可用，无法生成建议。"
