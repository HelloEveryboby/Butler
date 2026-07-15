import pytest
from butler.interpreter import Interpreter
from butler.core.skill_manager import SkillManager
from unittest.mock import MagicMock
import tempfile
import os

def test_interpreter_python_safety():
    interpreter = Interpreter()
    interpreter.safety_mode = True

    # Safe Python Code
    safe_code = "a = 1 + 2\nprint(a)"
    assert interpreter.is_python_safe(safe_code)

    # Unsafe Python Code: Import os
    unsafe_code_import = "import os\nos.system('ls')"
    assert not interpreter.is_python_safe(unsafe_code_import)

    # Unsafe Python Code: ImportFrom subprocess
    unsafe_code_import_from = "from subprocess import run\nrun(['ls'])"
    assert not interpreter.is_python_safe(unsafe_code_import_from)

    # Unsafe Python Code: eval/exec
    unsafe_code_eval = "eval('1 + 2')"
    assert not interpreter.is_python_safe(unsafe_code_eval)

    # Verify execution block
    success, output = interpreter.execute_python("import os")
    assert not success
    assert "Security Block" in output

def test_interpreter_shell_safety():
    interpreter = Interpreter()
    interpreter.safety_mode = True

    # Safe commands
    assert interpreter.is_command_safe("ls -la")
    assert interpreter.is_command_safe("echo 'hello'")

    # Dangerous commands
    assert not interpreter.is_command_safe("rm -rf /")
    assert not interpreter.is_command_safe("rm -rf *")
    assert not interpreter.is_command_safe("shred -u file.txt")

    # Sensitive files
    assert not interpreter.is_command_safe("cat /etc/passwd > output.txt")

    # Verify execution block
    success, output = interpreter.execute_shell("rm -rf /")
    assert not success
    assert "Security Block" in output

    # Test requires_approval and is_destructive helper functions
    assert interpreter.is_destructive("rm -rf /")
    assert not interpreter.is_destructive("ls -la")

    assert interpreter.requires_approval("sudo apt update")
    assert interpreter.requires_approval("reg add HKLM\\Software")
    assert interpreter.requires_approval("mkdir /etc/myconfig")
    assert not interpreter.requires_approval("ls -la")

    # Test execute_shell with approval flow
    success, output = interpreter.execute_shell("sudo apt update", approved=False)
    assert not success
    assert "Approval Required" in output

    success, output = interpreter.execute_shell("mkdir /etc/newdir", approved=False)
    assert not success
    assert "Approval Required" in output

def test_skill_manager_ast_safety():
    sm = SkillManager()

    # Create a temporary safe python skill file
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(b"def handle_request():\n    return 'Hello'\n")
        safe_file = f.name

    try:
        assert sm._is_skill_safe(safe_file)
    finally:
        os.unlink(safe_file)

    # Create a temporary unsafe python skill file
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(b"import subprocess\ndef handle_request():\n    subprocess.run(['ls'])\n")
        unsafe_file = f.name

    try:
        assert not sm._is_skill_safe(unsafe_file)
    finally:
        os.unlink(unsafe_file)

def test_implicit_skill_matching():
    # Setup mock Jarvis app and skill manager
    mock_app = MagicMock()
    mock_skill_manager = MagicMock()
    mock_app.skill_manager = mock_skill_manager

    # Configure manifest for format_convert and archive_manager
    mock_skill_manager.manifests = {
        "format_convert": {
            "name": "Format Convert",
            "keywords": ["convert", "pandoc", "pdf2docx"]
        },
        "archive_manager": {
            "name": "Archive Manager",
            "keywords": ["zip", "unzip", "tar"]
        }
    }

    # Configure skill manager mock execute function to return custom status
    def mock_execute(skill_id, action, **kwargs):
        return f"Mocked execute of {skill_id} with action {action}"

    mock_skill_manager.execute.side_effect = mock_execute

    # Set up interpreter and inject mock app
    interpreter = Interpreter()
    interpreter.safety_mode = True
    interpreter.jarvis_app = mock_app

    # Test format_convert interception
    success, output = interpreter.execute_shell("pandoc input.md -o output.html")
    assert success
    assert "format_convert" in output
    assert "智能拦截成功" in output
    mock_skill_manager.execute.assert_any_call(
        "format_convert", "run",
        input="input.md", from_fmt="md", to_fmt="html", save_to="output.html",
        jarvis_app=mock_app
    )

    # Test archive_manager interception
    success, output = interpreter.execute_shell("zip -r archive.zip folder1")
    assert success
    assert "archive_manager" in output
    mock_skill_manager.execute.assert_any_call(
        "archive_manager", "run",
        action="zip", zip_path="archive.zip", targets=["folder1"],
        jarvis_app=mock_app
    )
