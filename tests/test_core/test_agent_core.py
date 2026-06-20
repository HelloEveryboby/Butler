
import unittest
import os
import shutil
import json
from butler.core.task_manager import TaskManager
from butler.core.message_bus import MessageBus
from butler.core.constants import DATA_DIR

class TestButlerAgentCore(unittest.TestCase):
    def setUp(self):
        # Setup temporary directories for testing
        self.test_data_dir = DATA_DIR / "test_agent_data"
        self.test_data_dir.mkdir(parents=True, exist_ok=True)

        # Patch TaskManager and MessageBus to use test dirs
        self.task_mgr = TaskManager.get_instance()
        self.task_mgr.tasks_dir = self.test_data_dir / "tasks"
        self.task_mgr.tasks_dir.mkdir(parents=True, exist_ok=True)

        self.msg_bus = MessageBus.get_instance()
        self.msg_bus.inbox_dir = self.test_data_dir / "inbox"
        self.msg_bus.inbox_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        # Cleanup test data
        if self.test_data_dir.exists():
            shutil.rmtree(self.test_data_dir)

    def test_business_task_persistence(self):
        # Create a task
        task = self.task_mgr.create_business_task("Test Subject", "Test Desc")
        tid = task['id']
        self.assertEqual(task['subject'], "Test Subject")

        # Reload and check
        loaded_task = self.task_mgr.get_business_task(tid)
        self.assertEqual(loaded_task['description'], "Test Desc")
        self.assertEqual(loaded_task['status'], "pending")

        # Update status
        self.task_mgr.update_business_task(tid, status="completed")
        self.assertEqual(self.task_mgr.get_business_task(tid)['status'], "completed")

    def test_message_bus(self):
        # Send message
        self.msg_bus.send("sender_agent", "receiver_agent", "Hello Agent", "message")

        # Read inbox
        messages = self.msg_bus.read_inbox("receiver_agent")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['content'], "Hello Agent")
        self.assertEqual(messages[0]['from'], "sender_agent")

        # Inbox should be empty after reading
        messages_after = self.msg_bus.read_inbox("receiver_agent")
        self.assertEqual(len(messages_after), 0)

if __name__ == '__main__':
    unittest.main()
