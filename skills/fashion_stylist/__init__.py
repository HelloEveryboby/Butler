from butler.core.base_skill import BaseSkill

class FashionStylistSkill(BaseSkill):
    def __init__(self):
        super().__init__("fashion_stylist")

    def handle_request(self, action, **kwargs):
        if action == "suggest":
            # 模拟获取天气并动态生成建议
            code = """
import random
weathers = ["晴朗", "多云", "阴天", "小雨"]
temp = random.randint(15, 25)
current_weather = random.choice(weathers)

print(f"当前天气：{current_weather}，温度：{temp}℃")
if temp > 20:
    print("建议搭配：简约白色 T 恤 + 浅色牛仔裤 + 运动鞋。风格：清爽初级。")
else:
    print("建议搭配：薄卫衣 + 工装裤 + 复古板鞋。风格：视觉系休闲。")
"""
            success, output = self.execute_dynamic_script("python", code, purpose="Generate fashion suggestion based on simulated weather")
            return output if success else "无法获取穿搭建议。"

        return f"FashionStylist 不支持动作: {action}"

skill_instance = FashionStylistSkill()

def handle_request(action, **kwargs):
    return skill_instance.handle_request(action, **kwargs)
