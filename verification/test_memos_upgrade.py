import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from skills.memos import MemosSkill, handle_request

class TestMemosSkillUpgrade(unittest.TestCase):
    def setUp(self):
        # Patch HybridLinkClient start and call
        self.patcher_start = patch('butler.core.hybrid_link.HybridLinkClient.start')
        self.patcher_call = patch('butler.core.hybrid_link.HybridLinkClient.call')

        self.mock_start = self.patcher_start.start()
        self.mock_call = self.patcher_call.start()

        # Reset singleton instance to ensure __init__ runs with patched client
        MemosSkill._instance = None
        self.memos_skill = MemosSkill()

    def tearDown(self):
        self.patcher_start.stop()
        self.patcher_call.stop()
        MemosSkill._instance = None

    def test_singleton_pattern(self):
        skill_a = MemosSkill()
        skill_b = MemosSkill()
        self.assertIs(skill_a, skill_b)

    def test_add_memo(self):
        self.mock_call.return_value = {"id": 123}

        result = self.memos_skill.add_memo(content="Test content", tags=["#test"])

        self.mock_call.assert_called_with("add_memo", {
            "content": "Test content",
            "tags": ["#test"],
            "resources": []
        })
        self.assertEqual(result, {"id": 123})

    def test_update_memo(self):
        self.mock_call.return_value = "success"

        result = self.memos_skill.update_memo(
            memo_id=123,
            content="Updated content",
            tags=["#test", "#update"],
            is_pinned=1,
            is_archived=0
        )

        self.mock_call.assert_called_with("update_memo", {
            "id": 123,
            "content": "Updated content",
            "tags": ["#test", "#update"],
            "is_pinned": 1,
            "is_archived": 0
        })
        self.assertEqual(result, "success")

    def test_handle_request_update(self):
        self.mock_call.return_value = "success"

        res = handle_request("update", id=123, content="Patched text", is_pinned=1)

        self.mock_call.assert_called_with("update_memo", {
            "id": 123,
            "content": "Patched text",
            "is_pinned": 1
        })
        self.assertEqual(res, "备忘录已更新。")

    def test_ai_tag_predict(self):
        mock_nlu = MagicMock()
        mock_nlu.ask_llm.return_value = "#生活 #日常"

        mock_jarvis = MagicMock()
        mock_jarvis.nlu_service = mock_nlu

        res = handle_request("ai_tag_predict", content="今天天气好晴朗", jarvis_app=mock_jarvis)

        self.assertEqual(res, ["#生活", "#日常"])
        mock_nlu.ask_llm.assert_called_once()

    def test_ai_magic_wand_summary(self):
        mock_nlu = MagicMock()
        mock_nlu.ask_llm.return_value = "极简摘要：测试内容"

        mock_jarvis = MagicMock()
        mock_jarvis.nlu_service = mock_nlu

        res = handle_request("ai_magic_wand", content="长文本...", mode="summary", jarvis_app=mock_jarvis)

        self.assertEqual(res, "极简摘要：测试内容")

if __name__ == '__main__':
    unittest.main()
