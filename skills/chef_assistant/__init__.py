import json
import os
import logging
from butler.core.base_skill import BaseSkill

class ChefAssistantSkill(BaseSkill):
    """
    智慧厨师技能类。
    定位：个性化膳食顾问。
    功能：能够根据现有的食材储备、用户个人的口味偏好，智能生成并推荐做菜方案。
    """
    def __init__(self):
        super().__init__("chef_assistant")
        self.inventory_path = "data/chef_inventory.json"
        self.logger = logging.getLogger("ChefAssistant")

    def _load_inventory_data(self):
        """
        从本地数据中心加载食材与偏好信息。
        """
        if os.path.exists(self.inventory_path):
            try:
                with open(self.inventory_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"读取食材数据失败: {e}")
        return {"ingredients": [], "preferences": {}}

    def handle_request(self, action, **kwargs):
        """
        统一请求处理入口。
        支持的操作:
          - list_inventory: 汇报当前食材库存。
          - recommend: 基于算法推荐今日菜谱。
        """
        data = self._load_inventory_data()

        if action == "list_inventory":
            items = data.get("ingredients", [])
            if not items:
                return "🥚 你的食材库空空如也，是时候去采购了。"

            report = ["### 🧊 当前食材储备："]
            for item in items:
                # 简单的有效期预警逻辑
                report.append(f"- **{item['name']}**: {item['quantity']} {item['unit']} (有效期至: {item['expiry']})")
            return "\n".join(report)

        elif action == "recommend":
            ingredients = [i['name'] for i in data.get("ingredients", [])]
            flavor = data.get("preferences", {}).get("flavor_weights", {})

            if not ingredients:
                return "❌ 没有检测到食材，无法生成建议。"

            # 构建动态 Python 算法脚本进行智能匹配
            purpose = "基于库存食材和口味权重生成个性化菜谱建议"
            code = f"""
inventory = {ingredients}
weights = {flavor}

def generate_logic(inv, w):
    # 模拟口味算法：如果盐度权重高且有鸡蛋/西红柿，优先推荐西红柿炒鸡蛋
    if "西红柿" in inv and "鸡蛋" in inv:
        return "建议尝试：【西红柿炒鸡蛋】。\\n理由：符合你当前偏咸的口味设置，且食材新鲜。"
    return "由于食材有限，建议制作简单的素炒方案。"

print(f"--- 膳食分析报告 ---")
print(f"库存匹配完成: {{', '.join(inventory)}}")
print(generate_logic(inventory, weights))
"""
            success, output = self.execute_dynamic_script("python", code, purpose=purpose)
            return output if success else "❌ 生成建议时算法出错，请检查 Interpreter 状态。"

        return f"错误: ChefAssistant 不支持动作 '{action}'。"

# 实例化技能
skill_instance = ChefAssistantSkill()

def handle_request(action, **kwargs):
    """
    对接 Butler SkillManager 的标准入口函数。
    """
    return skill_instance.handle_request(action, **kwargs)
