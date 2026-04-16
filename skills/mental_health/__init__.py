from butler.core.base_skill import BaseSkill

class MentalHealthSkill(BaseSkill):
    def __init__(self):
        super().__init__("mental_health")

    def handle_request(self, action, **kwargs):
        user_input = kwargs.get("text") or kwargs.get("entities", {}).get("text", "")

        # 简单的情感引导逻辑
        if any(word in user_input for word in ["难过", "压力", "累", "心情不好"]):
            return "我能感觉到你现在有些疲惫。愿意和我聊聊发生了什么吗？我会一直在这里倾听。"

        return "如果你觉得心情起伏或者只是想找人说话，我随时都在。生活总有起伏，你并不孤单。"

skill_instance = MentalHealthSkill()

def handle_request(action, **kwargs):
    return skill_instance.handle_request(action, **kwargs)
