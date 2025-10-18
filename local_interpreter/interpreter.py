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

    def run_approved_code(self):
        """
        Executes the code that was last generated and awaiting approval.
        This is also a generator to be consistent with the `run` method.
        """
        if not self.last_code_for_approval:
            yield "result", "No code to approve."
            return

        code = self.last_code_for_approval
        self.last_code_for_approval = None

        yield "status", "Executing approved code..."
        output, success = self._execute_code(code)
        self._add_assistant_response_to_history(code, output)

        result_message = output if success else f"An error occurred:\n{output}"
        yield "result", result_message

    def _run_os_mode(self, user_input: str):
        """Handles the workflow for Operating System Mode as a generator."""
        yield "status", "Capturing screen for OS mode..."
        screenshot_b64 = os_tools.capture_screen()

        user_message_with_image = [
            {"type": "text", "text": user_input},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
        ]
        self.conversation_history.append({"role": "user", "content": user_message_with_image})

        yield "status", "Generating OS commands..."
        generated_code = ""
        code_stream = self.orchestrator.stream_code_generation(self.conversation_history, use_os_tools=True)

        for chunk in code_stream:
            if 'print("Error' in chunk:
                self.conversation_history.pop()
                yield "result", chunk
                return
            generated_code += chunk
            yield "code_chunk", chunk

        yield "status", "\n"

        if "Error:" in generated_code:
            self.conversation_history.pop()
            yield "result", generated_code
            return

        execution_globals = {
            "move_mouse": os_tools.move_mouse,
            "click": os_tools.click,
            "type_text": os_tools.type_text,
            "capture_screen": os_tools.capture_screen,
            "open_application": power_tools.open_application,
            "open_url": power_tools.open_url,
        }

        yield "status", "Executing OS commands..."
        output, success = self._execute_code(generated_code, execution_globals=execution_globals)
        self._add_assistant_response_to_history(generated_code, output, os_command=True)

        result_message = output if success else f"An error occurred in OS Mode:\n{output}"
        yield "result", result_message

    def run(self, user_input: str):
        """
        Runs a single turn of the interpreter, yielding events as they happen.
        Events can be status updates, code chunks, or final results.
        """
        if not self.is_ready:
            yield "result", "Error: Interpreter is not ready. Please check API key and restart."
            return

        if self.os_mode:
            yield from self._run_os_mode(user_input)
            return

        self.conversation_history.append({"role": "user", "content": user_input})
        yield "status", "Generating code..."

        stream = self.orchestrator.stream_code_generation(self.conversation_history)
        last_code_yielded = ""
        final_code = None

        for partial_response in stream:
            # The content of the file is the code
            if partial_response.content:
                new_code = partial_response.content[len(last_code_yielded):]
                if new_code:
                    yield "code_chunk", new_code
                    last_code_yielded = partial_response.content
            final_code = partial_response.content

        if "Error:" in final_code:
            self.conversation_history.pop()
            yield "result", final_code
            return

        yield "status", "\n"

        if self.safety_mode:
            self.last_code_for_approval = final_code
            approval_message = f"Generated Code (awaiting approval):\n```python\n{final_code}```\n\nType `/approve` to execute."
            yield "result", approval_message
        else:
            yield "status", "Executing code..."
            output, success = self._execute_code(final_code)
            self._add_assistant_response_to_history(final_code, output)
            result_message = output if success else f"An error occurred:\n{output}"
            yield "result", result_message