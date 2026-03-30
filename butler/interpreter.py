import os
import subprocess
import traceback
import io
from contextlib import redirect_stdout, redirect_stderr
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)


class Interpreter:
    """
    A code interpreter core that can execute Python and Shell code.
    Inspired by Open Interpreter.
    """

    def __init__(self, working_dir=None):
        self.working_dir = working_dir or os.getcwd()
        self.output_buffer = []

    def execute_python(self, code):
        """Executes Python code and captures output."""
        logger.info(f"Executing Python code:\n{code}")
        f = io.StringIO()
        with redirect_stdout(f), redirect_stderr(f):
            try:
                # We use a shared globals dict to allow state to persist between calls if needed
                # However, for a simple implementation, we can just execute it.
                exec(code, globals())
                success = True
            except Exception:
                print(traceback.format_exc())
                success = False

        output = f.getvalue()
        return success, output

    def execute_shell(self, command):
        """Executes a shell command and captures output."""
        logger.info(f"Executing Shell command: {command}")
        try:
            import shlex

            # Try to run without shell if possible (no pipes, redirects, etc.)
            shell_chars = {
                "|",
                "&",
                ";",
                "<",
                ">",
                "$",
                "*",
                "?",
                "(",
                ")",
                "[",
                "]",
                "!",
                "#",
                "~",
            }
            use_shell = any(char in command for char in shell_chars)

            if not use_shell:
                cmd_list = shlex.split(command)
                result = subprocess.run(
                    cmd_list,
                    shell=False,
                    cwd=self.working_dir,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=self.working_dir,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                )
            output = result.stdout + result.stderr
            success = result.returncode == 0
            return success, output
        except subprocess.TimeoutExpired:
            return False, "Error: Command timed out after 300 seconds."
        except Exception as e:
            return False, f"Error executing shell command: {str(e)}"

    def run(self, language, code):
        """Entry point for running code of a specific language."""
        if language.lower() == "python":
            return self.execute_python(code)
        elif language.lower() in ["shell", "sh", "bash", "cmd", "powershell"]:
            return self.execute_shell(code)
        else:
            return False, f"Unsupported language: {language}"


# Global instance for easy access
interpreter = Interpreter()
