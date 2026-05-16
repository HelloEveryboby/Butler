import re
import logging
from typing import Dict, Any, Optional, Tuple
from butler.core.intent_dispatcher import intent_registry
from butler.core.skill_manager import SkillManager

logger = logging.getLogger("LocalNLU")

class LocalNLU:
    """
    不需要 AI 驱动的本地 NLU 引擎。
    使用正则表达式和关键词匹配来提取意图和实体。
    """
    def __init__(self, skill_manager: SkillManager):
        self.skill_manager = skill_manager

    def extract_intent(self, text: str) -> Tuple[Optional[str], Dict[str, Any], str]:
        """
        尝试从文本中提取意图。
        返回: (intent_id, entities, match_type)
        match_type 可以是 'intent' 或 'skill'
        """
        text = text.strip()

        # 1. 尝试匹配已注册的 Legacy Intents (使用相似度或关键词)
        intent_id = intent_registry.match_intent_locally(text, threshold=0.8)
        if intent_id:
            entities = self._extract_entities_for_intent(intent_id, text)
            return intent_id, entities, 'intent'

        # 2. 尝试匹配 Butler Skills
        skill_id = self.skill_manager.match_skill(text)
        if skill_id:
            # 简单的实体提取逻辑：尝试从文本中提取路径或数字
            entities = self._generic_entity_extraction(text)
            return skill_id, entities, 'skill'

        return None, {}, 'none'

    def _extract_entities_for_intent(self, intent_id: str, text: str) -> Dict[str, Any]:
        """针对特定意图的硬编码提取逻辑"""
        entities = {}

        # 通用路径提取
        path_match = re.search(r'(/[a-zA-Z0-9._/-]+|[a-zA-Z]:\\[a-zA-Z0-9._\\-]+)', text)
        if path_match:
            entities['path'] = path_match.group(0)
            entities['file_path'] = path_match.group(0)

        # 提取数字列表 (例如 [1, 2, 3] 或 1, 2, 3)
        nums = re.findall(r'\d+', text)
        if nums:
            entities['numbers'] = [int(n) for n in nums]
            entities['number'] = int(nums[0])
            entities['target'] = int(nums[-1])

        # 针对排序和查找
        if intent_id in ["sort_numbers", "find_number"]:
            # 如果有带中括号的列表
            list_match = re.search(r'\[(.*?)\]', text)
            if list_match:
                entities['numbers'] = [float(n.strip()) for n in list_match.group(1).split(',') if n.strip()]

        return entities

    def _generic_entity_extraction(self, text: str) -> Dict[str, Any]:
        """通用的启发式实体提取"""
        entities = {}

        # 提取引号中的内容作为 action 或参数
        quoted = re.findall(r'["\'](.*?)["\']', text)
        if quoted:
            entities['action'] = quoted[0]
            entities['operation'] = quoted[0]
            entities['content'] = quoted[0]

        # 提取路径
        path_match = re.search(r'(/[a-zA-Z0-9._/-]+|[a-zA-Z]:\\[a-zA-Z0-9._\\-]+)', text)
        if path_match:
            entities['path'] = path_match.group(0)

        return entities

# 辅助函数用于快速测试
if __name__ == "__main__":
    from butler.core.skill_manager import SkillManager
    sm = SkillManager()
    sm.load_skills()
    nlu = LocalNLU(sm)
    print(nlu.extract_intent("帮我排序 [3, 1, 4]"))
    print(nlu.extract_intent("打开程序 'Notepad'"))
