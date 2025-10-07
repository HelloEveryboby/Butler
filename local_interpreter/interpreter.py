import io
from contextlib import redirect_stdout
from .coordinator.orchestrator import Orchestrator
from .executor.code_executor import Sandbox, SandboxError
from .tools import os_tools, power_tools

class Interpreter:
    """
    A class that encapsulates the local interpreter's functionality,
    providing a clean interface for other parts of the application.
    """
    def __init__(self, safety_mode: bool = True, os_mode: bool = False):
        """
        Initializes the Interpreter, which includes creating an Orchestrator
        and setting up a conversation history.
        """
        self.orchestrator = Orchestrator()
        self.conversation_history = []
        self.safety_mode = safety_mode
        self.os_mode = os_mode
        self.last_code_for_approval = None

        # A simple check to see if the orchestrator failed to init (e.g. no API key)
        if not self.orchestrator.client:
            self.is_ready = False
            print("Warning: Interpreter initialized without a valid API client.")
        else:
            self.is_ready = True
        self.sandbox = Sandbox()

    def _execute_code(self, code: str, execution_globals: dict = None) -> (str, bool):
        """Helper to run code and capture output."""
        output_catcher = io.StringIO()
        success = False
        try:
            with redirect_stdout(output_catcher):
                if self.os_mode:
                    # In OS mode, we bypass the sandbox and use exec directly
                    # with the provided globals (which include os_tools).
                    exec(code, execution_globals)
                else:
                    self.sandbox.execute(code)
            output = output_catcher.getvalue()
            success = True
        except SandboxError as e:
            output = f"Sandbox Error: {e}"
        except Exception as e:
            output = f"An unexpected error occurred during execution: {e}"
        return output, success

    def _add_assistant_response_to_history(self, code: str, output: str, os_command: bool = False):
        """Helper to format and add the assistant's response to history."""
        response_type = "Executed OS Commands" if os_command else "Executed Code"
        assistant_response = f"{response_type}:\n```python\n{code}```\nOutput:\n```\n{output}```"
        self.conversation_history.append({"role": "assistant", "content": assistant_response})

    def run_approved_code(self) -> str:
        """Executes the code that was last generated and awaiting approval."""
        if not self.last_code_for_approval:
            return "No code to approve."

        code = self.last_code_for_approval
        self.last_code_for_approval = None

        output, success = self._execute_code(code)
        self._add_assistant_response_to_history(code, output)

        return output if success else f"An error occurred:\n{output}"

    def _run_os_mode(self, user_input: str) -> str:
        """Handles the workflow for Operating System Mode."""
        print("--- OS MODE: Capturing screen... ---")
        screenshot_b64 = os_tools.capture_screen()

        # The user message for the orchestrator needs to include the image
        user_message_with_image = [
            {"type": "text", "text": user_input},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}
            }
        ]

        # Add the multimodal message to history
        self.conversation_history.append({"role": "user", "content": user_message_with_image})

        # Tell the orchestrator to use the OS toolset
        generated_code = self.orchestrator.process_user_input(self.conversation_history, use_os_tools=True)

        if "Error:" in generated_code:
            self.conversation_history.pop() # Remove the user message that led to the error
            return generated_code

        # Prepare the execution environment for the OS tools
        execution_globals = {
            # Low-level GUI tools
            "move_mouse": os_tools.move_mouse,
            "click": os_tools.click,
            "type_text": os_tools.type_text,
            "capture_screen": os_tools.capture_screen,
            # High-level power tools
            "open_application": power_tools.open_application,
            "open_url": power_tools.open_url,
        }

        output, success = self._execute_code(generated_code, execution_globals=execution_globals)
        self._add_assistant_response_to_history(generated_code, output, os_command=True)

        return output if success else f"An error occurred in OS Mode:\n{output}"

    def run(self, user_input: str) -> str:
        """
        Runs a single turn of the interpreter.
        If in safety mode, it returns the code for approval. Otherwise, it executes directly.
        """
        if not self.is_ready:
            return "Error: Interpreter is not ready. Please check API key and restart."

        # Branch to OS mode if enabled
        if self.os_mode:
            return self._run_os_mode(user_input)

        # Add user input to history immediately for standard mode
        self.conversation_history.append({"role": "user", "content": user_input})

        # Generate code using the full history
        generated_code = self.orchestrator.process_user_input(self.conversation_history)

        if "Error:" in generated_code:
            # If code generation fails, remove the user message that led to it
            self.conversation_history.pop()
            return generated_code

        if self.safety_mode:
            self.last_code_for_approval = generated_code
            return f"Generated Code (awaiting approval):\n```python\n{generated_code}```\n\nType `/approve` to execute."
        else:
            output, success = self._execute_code(generated_code)
            self._add_assistant_response_to_history(generated_code, output)
            return output if success else f"An error occurred:\n{output}"