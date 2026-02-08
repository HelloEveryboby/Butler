import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import sys


from butler.main import Jarvis
from local_interpreter.interpreter import Interpreter
from local_interpreter.coordinator.orchestrator import ExternalToolCall, FinalResponse

class TestButler(unittest.TestCase):

    def setUp(self):
        """Set up a mock root for the Jarvis instance."""
        self.mock_root = MagicMock()

    @patch('local_interpreter.tools.os_tools.pyautogui')
    @patch.object(Jarvis, '_initialize_long_memory')
    @patch.object(Interpreter, 'run')
    def test_streaming_response(self, mock_interpreter_run, mock_init_long_memory, mock_pyautogui):
        """
        Tests that the streaming response from the interpreter is handled correctly.
        """
        # 1. Setup mocks
        mock_init_long_memory.return_value = None

        # This is the stream of events the interpreter will yield
        mock_stream = [
            ("status", "Generating code..."),
            ("code_chunk", "print('hello')"),
            ("result", "hello\n"),
        ]
        mock_interpreter_run.return_value = iter(mock_stream)

        # 2. Instantiate Jarvis and its panel
        jarvis = Jarvis(self.mock_root)
        jarvis.interpreter.is_ready = True # Ensure the interpreter is ready
        jarvis.panel = MagicMock()
        jarvis.panel.append_to_response = MagicMock()

        # 3. Call the method that handles the streaming
        jarvis.stream_interpreter_response("test command")

        # 4. Verify the calls to the panel
        # We need to check the calls made via `root.after`
        calls = self.mock_root.after.call_args_list
        self.assertGreater(len(calls), 0, "root.after should have been called")

        # Check the call for the code chunk
        append_calls = [c for c in calls if c[0][1] == jarvis.panel.append_to_response]
        self.assertTrue(any("print('hello')" in c[0] for c in append_calls), "Code chunk was not appended")
        # Check result
        result_calls = [c for c in calls if c[0][1] == jarvis.panel.append_to_response and "\n\nhello\n\n" in c[0][2]]
        self.assertGreater(len(result_calls), 0, "Final result was not appended")

    @patch('butler.core.extension_manager.ExtensionManager.scan_all')
    @patch('local_interpreter.interpreter.Orchestrator')
    def test_external_program_execution(self, MockOrchestrator, mock_scan_all):
        """
        Tests the end-to-end flow of executing a registered external program.
        """
        # 1. Setup Mocks
        # Mock the Orchestrator to return a real ExternalToolCall instance
        mock_orchestrator_instance = MockOrchestrator.return_value
        mock_tool_call_instance = ExternalToolCall(
            thought="Testing external program",
            tool_name="hello_program",
            args=["arg1", "arg2"]
        )
        # Mocking the iterative loop: first a tool call, then finished
        mock_orchestrator_instance.stream_code_generation.side_effect = [
            iter([mock_tool_call_instance]),
            iter([FinalResponse(thought="Finished", message="Task complete")])
        ]

        # 2. Instantiate Interpreter
        interpreter = Interpreter(safety_mode=False)

        # 3. Manually mock the extension_manager's methods after instantiation
        interpreter.extension_manager = MagicMock()
        interpreter.extension_manager.execute.return_value = "Success from External Program"
        mock_tools = [{"name": "hello_program", "description": "A test program.", "type": "program"}]
        interpreter.extension_manager.get_all_tools.return_value = mock_tools

        interpreter.orchestrator = mock_orchestrator_instance

        # 4. Run the interpreter with a command
        command = "run the hello program with arg1 and arg2"
        events = list(interpreter.run(command))

        # 5. Assertions
        # Verify the orchestrator was called with the tool descriptions
        self.assertGreaterEqual(mock_orchestrator_instance.stream_code_generation.call_count, 1)
        call_args, call_kwargs = mock_orchestrator_instance.stream_code_generation.call_args
        self.assertIn('external_tools', call_kwargs)
        # The formatting of descriptions in interpreter.py changed slightly
        self.assertEqual(call_kwargs['external_tools'], ["- `hello_program`: A test program."])

        # Verify the extension manager's execute method was called correctly
        interpreter.extension_manager.execute.assert_called_once_with("hello_program", "arg1", "arg2")

        # Verify the tool output result is yielded
        tool_output = next((item[1] for item in events if item[0] == 'result' and "Success from External Program" in item[1]), None)
        self.assertIsNotNone(tool_output)
        self.assertIn("Success from External Program", tool_output)

        # Verify the final completion message is yielded
        final_msg = next((item[1] for item in events if item[0] == 'result' and "**Final Answer:**" in item[1]), None)
        self.assertIsNotNone(final_msg)
        self.assertIn("Task complete", final_msg)

    @patch.object(Jarvis, '_initialize_long_memory')
    def test_data_storage_persistence(self, mock_init_long_memory):
        """
        Tests that data saved using the DataStorageManager persists across different Jarvis instances.
        """
        from butler.data_storage import data_storage_manager
        from butler.core.extension_manager import extension_manager
        # 1. Setup mock and first Jarvis instance
        mock_init_long_memory.return_value = None

        # Setup mock storage
        storage = {}
        def mock_save(plugin, key, val): storage[f"{plugin}:{key}"] = val
        def mock_load(plugin, key): return storage.get(f"{plugin}:{key}")

        with patch.object(data_storage_manager, 'save', side_effect=mock_save), \
             patch.object(data_storage_manager, 'load', side_effect=mock_load):

            jarvis1 = Jarvis(self.mock_root)
            user_profile_plugin1 = extension_manager.plugin_manager.get_plugin("UserProfilePlugin")
            self.assertIsNotNone(user_profile_plugin1, "UserProfilePlugin should be loaded")

            # 2. Save data using the first instance
            user_name = "test_user"
            save_command = f"remember my name is {user_name}"
            save_args = {"name": user_name}
            save_result = user_profile_plugin1.run(save_command, save_args)
            self.assertTrue(save_result.success)
            self.assertIn(f"Okay, I've remembered your name is {user_name}", save_result.result)

            # 3. Create a new Jarvis instance to simulate a restart
            jarvis2 = Jarvis(self.mock_root)
            user_profile_plugin2 = extension_manager.plugin_manager.get_plugin("UserProfilePlugin")
            self.assertIsNotNone(user_profile_plugin2, "UserProfilePlugin should be loaded in the new instance")

            # 4. Retrieve the data using the second instance
            load_command = "what is my name"
            load_args = {}
            load_result = user_profile_plugin2.run(load_command, load_args)
            self.assertTrue(load_result.success)
            self.assertIn(f"Your name is {user_name}", load_result.result)

    @patch.object(Jarvis, '_initialize_long_memory')
    def test_approve_edited_code(self, mock_init_long_memory):
        """Tests that /approve command extracts edited code from the UI."""
        mock_init_long_memory.return_value = None
        jarvis = Jarvis(self.mock_root)
        jarvis.interpreter.last_code_for_approval = "original_code()"
        jarvis.interpreter.is_ready = True

        # Mock the panel and its text widget
        jarvis.panel = MagicMock()
        jarvis.panel.output_text.get.return_value = "Some text before\n```python\nedited_code()\n```\nSome text after"

        # Mock stream_interpreter_response to check if it gets the edited code
        with patch.object(jarvis, 'stream_interpreter_response') as mock_stream:
            jarvis.handle_user_command("/approve", {})

            # Check if last_code_for_approval was updated
            self.assertEqual(jarvis.interpreter.last_code_for_approval, "edited_code()")
            mock_stream.assert_called_once_with("/approve", approved=True)


if __name__ == "__main__":
    unittest.main()
