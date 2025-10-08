import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Since we are testing a part of the local_interpreter, we need to adjust the path
# to ensure the imports work correctly.
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from local_interpreter.coordinator.orchestrator import Orchestrator
from local_interpreter.tools.file_management_tools import write_file, read_file, delete_file, modify_file
from local_interpreter.tools.file_models import File, FileModification

class TestFileOperations(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp(prefix="file_ops_test_")

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    @patch('instructor.patch')
    @patch('os.getenv')
    def test_create_file_with_orchestrator(self, mock_getenv, mock_instructor_patch):
        """
        Tests that the orchestrator can correctly generate a command to create a file.
        """
        # Arrange
        mock_getenv.return_value = "DUMMY_API_KEY"

        # Mock the entire instructor-patched client
        mock_client = MagicMock()
        mock_instructor_patch.return_value = mock_client

        orchestrator = Orchestrator()

        test_file_path = os.path.join(self.test_dir, "test_file.txt")
        test_content = "Hello, this is a test."

        # Mock the response from the DeepSeek API
        mock_response = File(
            file_path=test_file_path,
            content=test_content
        )
        mock_client.chat.completions.create.return_value = mock_response

        # Act
        command = orchestrator.process_user_input([{"role": "user", "content": f"create a file named {test_file_path} with content {test_content}"}])

        # Assert
        expected_command = f'write_file(r"{test_file_path}", """{test_content}""")'
        self.assertEqual(command, expected_command)

        # Execute the command and verify the result
        exec(command, {'write_file': write_file}, {})

        self.assertTrue(os.path.exists(test_file_path))
        with open(test_file_path, 'r') as f:
            content = f.read()
        self.assertEqual(content, test_content)

    @patch('instructor.patch')
    @patch('os.getenv')
    def test_delete_file_with_orchestrator(self, mock_getenv, mock_instructor_patch):
        """
        Tests that the orchestrator can correctly generate a command to delete a file.
        """
        # Arrange
        mock_getenv.return_value = "DUMMY_API_KEY"
        mock_client = MagicMock()
        mock_instructor_patch.return_value = mock_client

        orchestrator = Orchestrator()

        test_file_path = os.path.join(self.test_dir, "test_file_to_delete.txt")
        with open(test_file_path, 'w') as f:
            f.write("delete me")
        self.assertTrue(os.path.exists(test_file_path))

        # Mock the response from the DeepSeek API
        mock_response = FileModification(
            file_path=test_file_path,
            action="delete",
            description="delete the file"
        )
        mock_client.chat.completions.create.return_value = mock_response

        # Act
        command = orchestrator.process_user_input([{"role": "user", "content": f"delete the file {test_file_path}"}])

        # Assert
        expected_command = f'delete_file(r"{test_file_path}")'
        self.assertEqual(command, expected_command)

        # Execute the command and verify the result
        exec(command, {'delete_file': delete_file}, {})

        self.assertFalse(os.path.exists(test_file_path))

    @patch('instructor.patch')
    @patch('os.getenv')
    def test_modify_file_with_orchestrator(self, mock_getenv, mock_instructor_patch):
        """
        Tests that the orchestrator can correctly generate a command to modify a file.
        """
        # Arrange
        mock_getenv.return_value = "DUMMY_API_KEY"
        mock_client = MagicMock()
        mock_instructor_patch.return_value = mock_client

        orchestrator = Orchestrator()

        test_file_path = os.path.join(self.test_dir, "test_file_to_modify.txt")
        initial_content = "initial content"
        modified_content = "modified content"
        with open(test_file_path, 'w') as f:
            f.write(initial_content)

        # Mock the response from the DeepSeek API
        mock_response = FileModification(
            file_path=test_file_path,
            action="modify",
            description=modified_content
        )
        mock_client.chat.completions.create.return_value = mock_response

        # Act
        command = orchestrator.process_user_input([{"role": "user", "content": f"modify the file {test_file_path} to have content {modified_content}"}])

        # Assert
        expected_command = f'modify_file(r"{test_file_path}", """{modified_content}""")'
        self.assertEqual(command, expected_command)

        # Execute the command and verify the result
        exec(command, {'modify_file': modify_file}, {})

        with open(test_file_path, 'r') as f:
            content = f.read()
        self.assertEqual(content, modified_content)

if __name__ == "__main__":
    unittest.main()