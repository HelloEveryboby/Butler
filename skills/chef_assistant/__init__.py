import json
import os
from butler.core.base_skill import BaseSkill

class ChefAssistantSkill(BaseSkill):
    def __init__(self):
        super().__init__("chef_assistant")
        self.inventory_path = "data/chef_inventory.json"

    def _load_data(self):
        if os.path.exists(self.inventory_path):
            with open(self.inventory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"ingredients": [], "preferences": {}}

    def handle_request(self, action, **kwargs):
        data = self._load_data()

        if action == "list_inventory":
            items = data.get("ingredients", [])
            if not items: return "食材库目前是空的。"
            report = ["### 当前食材储备："]
            for item in items:
                report.append(f"- {item['name']}: {item['quantity']} {item['unit']} (有效期至: {item['expiry']})")
            return "\n".join(report)

        elif action == "recommend":
            ingredients = [i['name'] for i in data.get("ingredients", [])]
            flavor = data.get("preferences", {}).get("flavor_weights", {})

            # 使用动态脚本生成个性化建议（模拟 AI 逻辑）
            purpose = "Generate personalized recipe based on inventory and preferences"
            code = f"""
inventory = {ingredients}
weights = {flavor}
print(f"检测到食材: {{', '.join(inventory)}}")
print(f"参考口味偏好 (咸度: {{weights.get('salty')}}), 建议尝试：西红柿炒鸡蛋")
"""
            success, output = self.execute_dynamic_script("python", code, purpose=purpose)
            return output if success else "生成建议时出错。"

        return f"ChefAssistant 不支持动作: {action}"

skill_instance = ChefAssistantSkill()

def handle_request(action, **kwargs):
    return skill_instance.handle_request(action, **kwargs)
