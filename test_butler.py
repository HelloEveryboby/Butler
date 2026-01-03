import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import sys


from butler.main import Jarvis, Interpreter
from local_interpreter.coordinator.orchestrator import ExternalToolCall

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
        self.assertTrue(any("hello\n" in c[0][2] for c in append_calls), "Final result was not appended")

    @patch('local_interpreter.interpreter.ExternalProgramManager')
    @patch('local_interpreter.interpreter.Orchestrator')
    def test_external_cpp_program_execution(self, MockOrchestrator, MockProgramManager):
        """
        Tests the end-to-end flow of executing a registered C++ program.
        """
        # 1. Setup Mocks
        # Mock the Orchestrator to return a real ExternalToolCall instance
        mock_orchestrator_instance = MockOrchestrator.return_value
        mock_tool_call_instance = ExternalToolCall(
            tool_name="hello_program",
            args=["arg1", "arg2"]
        )
        mock_orchestrator_instance.stream_code_generation.return_value = iter([mock_tool_call_instance])

        # Mock the ProgramManager to verify it gets called correctly
        mock_program_manager_instance = MockProgramManager.return_value
        mock_program_manager_instance.execute_program.return_value = (True, "Success from C++")
        mock_program_manager_instance.get_program_descriptions.return_value = ["- Tool Name: `hello_program`..."]

        # 2. Instantiate Interpreter
        # We test the interpreter directly as it contains the core logic
        interpreter = Interpreter(safety_mode=False) # Safety mode off for direct execution
        interpreter.orchestrator = mock_orchestrator_instance
        interpreter.program_manager = mock_program_manager_instance

        # 3. Run the interpreter with a command
        command = "run the hello program with arg1 and arg2"
        # Collect the yielded events into a list to inspect them
        events = list(interpreter.run(command))

        # 4. Assertions
        # Verify that the orchestrator was called with the tool descriptions
        mock_orchestrator_instance.stream_code_generation.assert_called_once()
        call_args, call_kwargs = mock_orchestrator_instance.stream_code_generation.call_args
        self.assertIn('external_tools', call_kwargs)
        self.assertEqual(call_kwargs['external_tools'], ["- Tool Name: `hello_program`..."])

        # Verify that the program manager's execute method was called correctly
        mock_program_manager_instance.execute_program.assert_called_once_with("hello_program", ["arg1", "arg2"])

        # Verify that the final result from the C++ program is yielded
        final_result = next((item[1] for item in events if item[0] == 'result'), None)
        self.assertIsNotNone(final_result)
        self.assertEqual(final_result, "Success from C++")


if __name__ == "__main__":
    unittest.main()