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
