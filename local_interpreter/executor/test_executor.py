# This script is for testing the sandboxed code executor.
import io
from contextlib import redirect_stdout
import pytest
from .code_executor import Sandbox, SandboxError
import math

def execute_python_code(code_string: str):
    """
    A helper function to execute code using the Sandbox and capture output.
    This mimics the old interface for the sake of the existing tests.
    """
    sandbox = Sandbox()
    output_catcher = io.StringIO()

    # Mock tool functions for testing
    def get_system_stats():
        return {"cpu": "50%", "memory": "2GB"}

    def set_gpio_pin(pin, state):
        return f"Pin {pin} set to {state}"

    def list_safe_directory(path):
        if ".." in path:
            # This exception will be caught by the sandbox's exec and reported
            raise PermissionError("Directory traversal is not allowed.")
        return [f"file_in_{path}.txt"]

    # The sandbox needs access to 'math' and mock tools. We pass them as globals.
    test_globals = sandbox.create_restricted_globals()
    test_globals.update({
        'math': math,
        'get_system_stats': get_system_stats,
        'set_gpio_pin': set_gpio_pin,
        'list_safe_directory': list_safe_directory,
    })

    try:
        with redirect_stdout(output_catcher):
            sandbox.execute(code_string, globals_dict=test_globals)
        output = output_catcher.getvalue()
        return output, True
    except (SandboxError, Exception) as e:
        # If the sandbox catches an error, or any other error occurs,
        # return the error message as output for the test to check.
        return f"{type(e).__name__}: {e}", False

# Test Case 1: Code that should be allowed
def test_allowed_code():
    print("\n[Test 1] Running allowed code...")
    code_allowed = "print('The square root of 16 is:', math.sqrt(16))"
    output, success = execute_python_code(code_allowed)
    print(f"Success: {success}\nOutput: {output.strip()}")
    assert success
    assert "4.0" in output

# Test Case 2: Code that tries to access the file system (should be blocked)
def test_disallowed_file_access():
    print("\n[Test 2] Running disallowed code (file access)...")
    code_disallowed_file = "open('malicious.txt', 'w')"
    output, success = execute_python_code(code_disallowed_file)
    print(f"Success: {success}\nOutput: {output.strip()}")
    assert not success
    assert "SecurityError" in output and "禁止调用函数: open" in output

# Test Case 3: Code that tries to import a dangerous module (should be blocked)
def test_disallowed_import():
    print("\n[Test 3] Running disallowed code (import os)...")
    code_disallowed_import = "import os"
    output, success = execute_python_code(code_disallowed_import)
    print(f"Success: {success}\nOutput: {output.strip()}")
    assert not success
    assert "SecurityError" in output and "禁止导入模块: os" in output

# Test Case 4: Code that uses an allowed PC tool
def test_allowed_pc_tool():
    print("\n[Test 4] Running allowed code (PC tool)...")
    code_pc_tool = "stats = get_system_stats()\nprint(type(stats))"
    output, success = execute_python_code(code_pc_tool)
    print(f"Success: {success}\nOutput: {output.strip()}")
    assert success
    assert "<class 'dict'>" in output

# Test Case 5: Code that uses an allowed embedded tool
def test_allowed_embedded_tool():
    print("\n[Test 5] Running allowed code (Embedded tool)...")
    code_embedded_tool = "result = set_gpio_pin(17, True)\nprint(result)"
    output, success = execute_python_code(code_embedded_tool)
    print(f"Success: {success}\nOutput: {output.strip()}")
    assert success
    assert "Pin 17 set to True" in output

# Test Case 6: Code that tries to misuse a tool (directory traversal)
def test_disallowed_tool_action():
    print("\n[Test 6] Running disallowed tool action (directory traversal)...")
    code_tool_misuse = "list_safe_directory('../../..')"
    output, success = execute_python_code(code_tool_misuse)
    print(f"Success: {success}\nOutput: {output.strip()}")
    assert not success
    assert "Directory traversal is not allowed" in output