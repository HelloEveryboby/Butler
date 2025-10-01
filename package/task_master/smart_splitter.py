import os
import json
import requests
from dotenv import load_dotenv

class SmartSplitter:
    """
    负责提供智能任务分解功能，支持离线和在线两种模式。
    """
    def __init__(self):
        """
        初始化智能分解器，并加载API密钥。
        """
        # 加载项目根目录的.env文件以获取API密钥
        dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
        load_dotenv(dotenv_path=dotenv_path)
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

        # 离线模式的简单规则模板
        self.offline_templates = {
            "旅行": ["预订航班和酒店", "规划行程", "打包行李", "准备旅行证件"],
            "生日派对": ["确定宾客名单", "选择并预订场地", "发送邀请函", "准备蛋糕和食物"],
            "开发新功能": ["需求分析", "技术设计", "编码实现", "编写单元测试", "部署上线"],
            "打扫房间": ["整理杂物", "吸尘和拖地", "擦拭家具表面", "清洗窗户"]
        }

    def split_task_offline(self, task_title):
        """
        使用预定义的模板和规则进行离线任务分解。

        :param task_title: 用户输入的主任务标题。
        :return: 一个包含建议子任务字符串的列表。
        """
        for keyword, subtasks in self.offline_templates.items():
            if keyword in task_title:
                return subtasks
        return ["为这个任务规划详细步骤", "设置截止日期", "准备所需资源"] # 默认建议

    def split_task_online(self, task_title):
        """
        使用在线AI模型 (DeepSeek) 进行智能任务分解。

        :param task_title: 用户输入的主任务标题。
        :return: 一个包含建议子任务字符串的列表，或在出错时返回包含错误信息的列表。
        """
        if not self.deepseek_api_key:
            return ["错误：未找到 DeepSeek API 密钥。请检查您的 .env 文件。"]

        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }

        system_prompt = "你是一个任务分解助手。请将用户提供的主任务分解成一个清晰、可执行的子任务列表。请只返回一个JSON格式的列表，例如：[\"子任务1\", \"子任务2\", \"子任务3\"]。"

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task_title}
            ],
            "max_tokens": 1024,
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()

            # 尝试解析JSON响应
            result_json = response.json()
            # AI模型可能会将列表包装在一个键中，例如 {"subtasks": [...]}
            # 我们需要智能地找到这个列表
            if isinstance(result_json, dict):
                for key, value in result_json.items():
                    if isinstance(value, list):
                        return [str(item) for item in value] # 确保所有项都是字符串

            return ["错误：AI返回了非预期的JSON格式。"]

        except requests.exceptions.RequestException as e:
            return [f"错误：API 请求失败 - {e}"]
        except json.JSONDecodeError:
            return ["错误：无法解析来自API的响应。"]
        except (KeyError, IndexError):
            return ["错误：API响应格式不符合预期。"]