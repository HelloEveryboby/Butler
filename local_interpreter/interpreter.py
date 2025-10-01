import io
from contextlib import redirect_stdout
from .coordinator.orchestrator import Orchestrator
from .executor.code_executor import Sandbox, SandboxError

class Interpreter:
    """
    A class that encapsulates the local interpreter's functionality,
    providing a clean interface for other parts of the application.
    """
    def __init__(self):
        """
        Initializes the Interpreter, which includes creating an Orchestrator
        and setting up a conversation history.
        """
        self.orchestrator = Orchestrator()
        self.conversation_history = []
        # A simple check to see if the orchestrator failed to init (e.g. no API key)
        if not self.orchestrator.client:
            self.is_ready = False
            print("Warning: Interpreter initialized without a valid API client.")
        else:
            self.is_ready = True
        self.sandbox = Sandbox()

    def _execute_code(self, code: str) -> (str, bool):
        """Helper to run code in the sandbox and capture output."""
        output_catcher = io.StringIO()
        success = False
        try:
            with redirect_stdout(output_catcher):
                self.sandbox.execute(code)
            output = output_catcher.getvalue()
            success = True
        except SandboxError as e:
            output = f"Sandbox Error: {e}"
        except Exception as e:
            output = f"An unexpected error occurred: {e}"

        return output, success

    def run(self, user_input: str) -> str:
        """
        Runs a single turn of the interpreter.

        Args:
            user_input: The natural language command from the user.

        Returns:
            A string containing the result of the execution.
        """
        if not self.is_ready:
            return "Error: Interpreter is not ready. Please check API key and restart."

        # Append the user's message to the history
        self.conversation_history.append({"role": "user", "content": user_input})

        generated_code = self.orchestrator.process_user_input(self.conversation_history)

        # Early exit if code generation fails
        if "Error:" in generated_code:
            return generated_code

        output, success = self._execute_code(generated_code)

        # Append the assistant's response (the code and its output) to the history
        assistant_response = f"Executed Code:\n```python\n{generated_code}```\nOutput:\n```\n{output}```"
        self.conversation_history.append({"role": "assistant", "content": assistant_response})

        return output if success else f"An error occurred:\n{output}"