import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import sys


from butler.main import Jarvis, Interpreter

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

    def test_fuzzy_find_best_match(self):
        from butler import algorithms
        candidates = ["open notepad", "run calculator", "start browser"]
        query = "open notpad" # Typo in 'notepad'
        best_match, distance = algorithms.find_best_match(query, candidates)
        self.assertEqual(best_match, "open notepad")
        self.assertEqual(distance, 1)

        query = "run calculater" # Typo in 'calculator'
        best_match, distance = algorithms.find_best_match(query, candidates)
        self.assertEqual(best_match, "run calculator")
        self.assertEqual(distance, 1)

if __name__ == "__main__":
    unittest.main()