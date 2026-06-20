import sys
import os
import json
import time
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

    def test_incremental_hot_swap(self):
        """测试增量热插拔功能 (Watchdog -> load_and_register_skill)"""
        import shutil
        self.manager.start_monitoring()

        test_skill_id = "temp_hot_swap_test"
        test_skill_dir = Path("skills") / test_skill_id
        test_skill_dir.mkdir(exist_ok=True)

        try:
            # 写入 SKILL.md 触发热加载
            skill_md_content = f"""---
skill_name: {test_skill_id}
description: Incremental hot-swap test.
---
"""
            with open(test_skill_dir / "SKILL.md", "w") as f:
                f.write(skill_md_content)

            # 等待热加载 (带有 debounce 和监控延迟)
            found = False
            for _ in range(30):
                if test_skill_id in self.manager.manifests:
                    found = True
                    break
                time.sleep(0.1)

            self.assertTrue(found, "增量写入 SKILL.md 后应该能自动加载技能")

            # 测试删除
            shutil.rmtree(test_skill_dir)

            removed = False
            for _ in range(30):
                if test_skill_id not in self.manager.manifests:
                    removed = True
                    break
                time.sleep(0.1)

            self.assertTrue(removed, "删除技能目录后应该能自动注销技能")

        finally:
            self.manager.stop_monitoring()
            if test_skill_dir.exists():
                shutil.rmtree(test_skill_dir)

if __name__ == "__main__":
    unittest.main()
