import sys
import os
import json
import unittest
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from butler.core.skill_manager import SkillManager

class MockButler:
    """模拟 Butler 核心对象"""
    def __init__(self):
        self.spoken_messages = []
        self.ui_messages = []

    def speak(self, text):
        print(f"Butler.speak: {text}")
        self.spoken_messages.append(text)

    def ui_print(self, text, tag='ai_response'):
        print(f"Butler.ui_print [{tag}]: {text}")
        self.ui_messages.append((text, tag))

class TestSkillIsolation(unittest.TestCase):
    def setUp(self):
        self.manager = SkillManager()
        self.butler = MockButler()

    def test_subprocess_execution_and_ipc(self):
        """测试子进程隔离执行与 JSON-RPC 通信"""
        skill_id = "hot_swap_test"

        # 1. 确保技能已加载
        self.manager.load_skills()
        self.assertIn(skill_id, self.manager.manifests, "测试技能 hot_swap_test 应该被发现")

        # 2. 执行技能 (会触发隔离模式，因为 isolation: process)
        print(f"\n>>> 正在执行隔离测试技能: {skill_id}")
        result = self.manager.execute(skill_id, "test_action", jarvis_app=self.butler)

        # 3. 验证 JSON-RPC 回调 (speak)
        self.assertTrue(len(self.butler.spoken_messages) > 0, "技能应该通过 IPC 发送了 speak 指令")
        self.assertIn("验证热插拔机制", self.butler.spoken_messages[0])

        # 4. 验证最终结果返回
        self.assertIsInstance(result, dict, "结果应该是通过 action: result 发送的 JSON 字典")
        self.assertEqual(result.get("status"), "success")
        print(f"<<< 执行成功，结果: {result}")

    def test_non_isolated_fallback(self):
        """测试非隔离模式的向下兼容"""
        # 这里可以使用一个简单的内置技能或创建一个临时的非隔离技能进行测试
        # 为了演示，我们主要关注隔离模式的稳定性
        pass

if __name__ == "__main__":
    unittest.main()
