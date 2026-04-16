import logging
from butler.core.base_skill import BaseSkill

class MentalHealthSkill(BaseSkill):
    """
    心理疏导老师技能类。
    定位：私人心理医生。
    功能：侧重于情绪价值，引导用户说出内心真实的想法，帮助其走出负面情绪。
    """
    def __init__(self):
        super().__init__("mental_health")
        self.logger = logging.getLogger("MentalHealth")

    def handle_request(self, action, **kwargs):
        """
        统一请求处理入口。
        """
        user_input = kwargs.get("text") or kwargs.get("entities", {}).get("text", "")

        # 情感分析与引导逻辑
        negative_keywords = ["难过", "压力", "累", "心情不好", "迷茫", "想放弃", "崩溃"]

        if any(word in user_input for word in negative_keywords):
            return (
                "🌿 我感受到了你当下的那份重量。其实，感到疲惫或低落是非常正常的，"
                "这说明你一直在非常努力地生活。\\n\\n"
                "如果可以的话，试着闭上眼深呼吸三次。愿意具体跟我说说让你觉得最有压力的那件事吗？"
                "我会一直在这里陪着你。"
            )

        if action == "support":
            return (
                "🌟 记住，你不需要时刻都保持完美或坚强。每一个小小的进步都值得被肯定。"
                "如果你现在觉得思绪混乱，我们可以一起理一理。你想从哪里开始聊起？"
            )

        return "如果你觉得心情起伏或者只是想找人说话，我随时都在。我会是你最耐心的听众。"

# 实例化技能
skill_instance = MentalHealthSkill()

def handle_request(action, **kwargs):
    """
    对接 Butler SkillManager 的标准入口函数。
    """
    return skill_instance.handle_request(action, **kwargs)
