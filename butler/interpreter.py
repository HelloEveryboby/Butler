import os
import subprocess
import sys
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
        try:
            from package.core_utils.config_loader import config_loader
            self.safety_mode = config_loader.get("interpreter.safety_mode", True)
        except Exception:
            self.safety_mode = True

    def is_python_safe(self, code: str) -> bool:
        """Performs static AST analysis on incoming python code block to verify safety."""
        if not self.safety_mode:
            return True
        try:
            import ast
            tree = ast.parse(code)

            # Allow basic printing and calculations, forbid shell/process manipulation builtins
            forbidden_names = {"eval", "exec", "__import__", "getattr", "setattr", "compile"}
            forbidden_modules = {"os", "subprocess", "shutil", "sys", "socket", "pty"}

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        if name.name in forbidden_modules:
                            logger.warning(f"Interpreter: Blocked forbidden import '{name.name}'")
                            return False
                elif isinstance(node, ast.ImportFrom):
                    if node.module in forbidden_modules:
                        logger.warning(f"Interpreter: Blocked forbidden import-from '{node.module}'")
                        return False
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in forbidden_names:
                            logger.warning(f"Interpreter: Blocked forbidden call '{node.func.id}'")
                            return False
            return True
        except Exception as e:
            logger.error(f"Interpreter AST safety parse error: {e}")
            return False

    def is_destructive(self, command: str) -> bool:
        """Determines if a shell command is extremely destructive."""
        cmd_lower = command.lower().strip()
        destructive_patterns = [
            "rm -rf /", "rm -rf *", "mkfs", "dd if=", "chmod -r", "chown -r",
            ":(){ :|:& };:", "shred"
        ]
        for dp in destructive_patterns:
            if dp in cmd_lower:
                return True
        # Protect core operating system directories from critical modifications
        sensitive_dirs = ["/etc/passwd", "/etc/shadow", "/boot", "/sys", "/proc", "/dev"]
        for sd in sensitive_dirs:
            if sd in cmd_lower and any(op in cmd_lower for op in ["rm ", "mv ", ">"]):
                return True
        return False

    def requires_approval(self, command: str) -> bool:
        """Checks if a command requires explicit user approval (privilege escalation, system modification)."""
        cmd_lower = command.lower().strip()
        # Privilege escalation triggers
        priv_triggers = ["sudo ", "runas ", "psexec ", "gksudo ", "pkexec ", "administrator"]
        if any(trigger in cmd_lower for trigger in priv_triggers):
            return True
        # System modifications: registry changes
        registry_triggers = ["reg add", "reg delete", "reg import"]
        if any(trigger in cmd_lower for trigger in registry_triggers):
            return True
        # System folder writes/modifications (Windows/Linux)
        system_folders = ["/etc/", "/system/", "c:\\windows", "c:\\program files"]
        is_write_op = any(op in cmd_lower for op in ["mkdir", "rm ", "mv ", "del", "write", ">", ">>"])
        if is_write_op and any(folder in cmd_lower for folder in system_folders):
            return True
        return False

    def is_command_safe(self, command: str) -> bool:
        """Statically inspects shell commands for high-risk operations."""
        if not self.safety_mode:
            return True
        if self.is_destructive(command):
            return False
        return True

    def execute_python(self, code):
        """Executes Python code and captures output."""
        if not self.is_python_safe(code):
            return False, "Security Block: Execution of this Python code was blocked due to safety guidelines."

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

    def execute_shell(self, command, approved=False):
        """Executes a shell command and captures output, enforcing security rules and approval gates."""
        if self.safety_mode:
            if self.is_destructive(command):
                return False, "Security Block: Execution of this extremely destructive command was blocked."
            if self.requires_approval(command) and not approved:
                return False, "Approval Required: This command requires explicit user authorization (privilege escalation or system modifications detected)."

        # Check for skill interception to bypass raw command execution
        if hasattr(self, 'jarvis_app') and self.jarvis_app:
            try:
                from butler.core.skill_interceptor import SkillInterceptor
                intercepted, result = SkillInterceptor.intercept_command(command, self.jarvis_app)
                if intercepted:
                    logger.info(f"Interpreter: Shell command intercepted successfully: {result}")
                    return True, result
            except Exception as e:
                logger.error(f"Interpreter: Error during skill interception: {e}")

        logger.info(f"Executing Shell command: {command}")
        try:
            import shlex
            # Try to run without shell if possible (no pipes, redirects, etc.)
            shell_chars = {'|', '&', ';', '<', '>', '$', '*', '?', '(', ')', '[', ']', '!', '#', '~'}
            use_shell = any(char in command for char in shell_chars)

            if not use_shell:
                cmd_list = shlex.split(command)
                result = subprocess.run(
                    cmd_list,
                    shell=False,
                    cwd=self.working_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=self.working_dir,
                    capture_output=True,
                    text=True,
                    timeout=300 # 5 minute timeout
                )
            output = result.stdout + result.stderr
            success = (result.returncode == 0)
            return success, output
        except subprocess.TimeoutExpired:
            return False, "Error: Command timed out after 300 seconds."
        except Exception as e:
            return False, f"Error executing shell command: {str(e)}"

    def run(self, language, code, approved=False):
        """Entry point for running code of a specific language."""
        if language.lower() == 'python':
            return self.execute_python(code)
        elif language.lower() in ['shell', 'sh', 'bash', 'cmd', 'powershell']:
            return self.execute_shell(code, approved=approved)
        else:
            return False, f"Unsupported language: {language}"

# Global instance for easy access
interpreter = Interpreter()
