import io
from contextlib import redirect_stdout
from .coordinator.orchestrator import Orchestrator, PythonCode, ExternalToolCall
from .executor.code_executor import Sandbox, SandboxError
from .tools import os_tools, power_tools
from butler.code_execution_manager import CodeExecutionManager

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
        self.program_manager = CodeExecutionManager()
        self.program_manager.scan_and_register()
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
        yield "status", "Generating action..."

        # Get available external tools to pass to the orchestrator
        tool_descriptions = self.program_manager.get_program_descriptions()
        stream = self.orchestrator.stream_code_generation(
            self.conversation_history,
            external_tools=tool_descriptions
        )

        final_response = None
        for partial_response in stream:
            final_response = partial_response
            if isinstance(final_response, PythonCode) and final_response.code:
                 yield "code_chunk", final_response.code
            elif isinstance(final_response, ExternalToolCall) and final_response.tool_name:
                 yield "code_chunk", f"Tool Call: {final_response.tool_name}({', '.join(final_response.args)})"


        if not final_response:
            yield "result", "Error: Failed to get a response from the AI."
            return

        yield "status", "\n"

        # --- Handle Python Code Execution ---
        if isinstance(final_response, PythonCode):
            final_code = final_response.code
            if "Error:" in final_code:
                self.conversation_history.pop()
                yield "result", final_code
                return

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

        # --- Handle External Tool Execution ---
        elif isinstance(final_response, ExternalToolCall):
            tool_name = final_response.tool_name
            args = final_response.args
            yield "status", f"Executing external tool: {tool_name}..."

            success, output = self.program_manager.execute_program(tool_name, args)

            # Add a simplified representation to conversation history
            assistant_response = f"Executed External Tool:\n`{tool_name} {' '.join(args)}`\nOutput:\n```\n{output}```"
            self.conversation_history.append({"role": "assistant", "content": assistant_response})

            result_message = output if success else f"An error occurred while running the tool:\n{output}"
            yield "result", result_message

        else:
            yield "result", f"Error: Received an unexpected response type from the AI: {type(final_response).__name__}"