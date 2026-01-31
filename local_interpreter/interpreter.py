import io
from contextlib import redirect_stdout
from .coordinator.orchestrator import Orchestrator, PythonCode, ExternalToolCall, FinalResponse
from .executor.code_executor import Sandbox, SandboxError
from .tools import os_tools, power_tools
from butler.code_execution_manager import CodeExecutionManager

class Interpreter:
    """
    A class that encapsulates the local interpreter's functionality,
    providing a clean interface for other parts of the application.
    """
    def __init__(self, safety_mode: bool = True, os_mode: bool = False, max_iterations: int = 10):
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
        self.max_iterations = max_iterations
        self.last_code_for_approval = None
        self.last_tool_for_approval = None

        # A simple check to see if the orchestrator failed to init (e.g. no API key)
        if not self.orchestrator.client:
            self.is_ready = False
            print("Warning: Interpreter initialized without a valid API client.")
        else:
            self.is_ready = True
        self.sandbox = Sandbox()

    def _get_execution_globals(self) -> dict:
        """Populates the globals for code execution with available tools."""
        from .tools.tool_decorator import TOOL_REGISTRY
        execution_globals = {}
        for t_name, t_data in TOOL_REGISTRY.items():
            execution_globals[t_name] = t_data["function"]

        # Add additional power tools if needed
        execution_globals["open_application"] = power_tools.open_application
        execution_globals["open_url"] = power_tools.open_url

        return execution_globals

    def _execute_code(self, code: str, execution_globals: dict = None) -> (str, bool):
        """Helper to run code and capture output."""
        output_catcher = io.StringIO()
        success = False

        if execution_globals is None:
            execution_globals = self._get_execution_globals()

        try:
            with redirect_stdout(output_catcher):
                if self.os_mode:
                    # In OS mode, we bypass the sandbox and use exec directly
                    exec(code, execution_globals)
                else:
                    # In standard mode, we use the sandbox but still provide safe tools
                    # Note: sandbox has its own restricted builtins and importer
                    self.sandbox.execute(code, globals_dict=execution_globals)
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
        Executes the code or tool that was last generated and awaiting approval.
        Then continues the loop.
        """
        if self.last_code_for_approval:
            code = self.last_code_for_approval
            self.last_code_for_approval = None
            yield "status", "Executing approved code..."

            output, success = self._execute_code(code)
            self._add_assistant_response_to_history(code, output, os_command=self.os_mode)
            yield "result", f"Output:\n{output}"

        elif self.last_tool_for_approval:
            tool_name, args = self.last_tool_for_approval
            self.last_tool_for_approval = None
            yield "status", f"Executing approved tool: {tool_name}..."
            success, output = self.program_manager.execute_program(tool_name, args)
            assistant_response = f"Executed External Tool:\n`{tool_name} {' '.join(args)}`\nOutput:\n```\n{output}```"
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            yield "result", f"Output:\n{output}"
        else:
            yield "result", "No action to approve."
            return

        # Continue the loop automatically
        yield from self._run_loop()

    def _run_loop(self):
        """
        The core iterative loop for the interpreter.
        """
        for i in range(len(self.conversation_history), len(self.conversation_history) + self.max_iterations):
            yield "status", f"Thinking (Step {i})..."

            if self.os_mode:
                 # In OS mode, capture screen at each step
                 screenshot_b64 = os_tools.capture_screen()

                 # To prevent context window overflow, we replace older screenshots in history
                 for msg in self.conversation_history:
                     if isinstance(msg.get("content"), list):
                         for part in msg["content"]:
                             if part.get("type") == "image_url":
                                 # Replace image with a placeholder
                                 part["type"] = "text"
                                 part["text"] = "[Previous Screenshot Omitted to save space]"
                                 del part["image_url"]

                 self.conversation_history.append({
                     "role": "user",
                     "content": [
                         {"type": "text", "text": "Current Screen Observation:"},
                         {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
                     ]
                 })

            tool_descriptions = self.program_manager.get_program_descriptions()
            stream = self.orchestrator.stream_code_generation(
                self.conversation_history,
                use_os_tools=self.os_mode,
                external_tools=tool_descriptions
            )

            final_response = None
            last_yielded_thought = ""
            for partial_response in stream:
                final_response = partial_response
                if final_response.thought and final_response.thought != last_yielded_thought:
                    new_chunk = final_response.thought[len(last_yielded_thought):]
                    yield "code_chunk", new_chunk
                    last_yielded_thought = final_response.thought

                if isinstance(final_response, PythonCode) and final_response.code:
                    # Maybe yield code separately?
                    pass
                elif isinstance(final_response, ExternalToolCall) and final_response.tool_name:
                    pass

            if not final_response:
                yield "result", "Error: Failed to get a response from the AI."
                break

            if isinstance(final_response, FinalResponse):
                yield "result", f"\n**Final Answer:** {final_response.message}"
                break

            # Handle Actions
            if isinstance(final_response, PythonCode):
                final_code = final_response.code
                yield "code_chunk", f"\n```python\n{final_code}\n```\n"

                if self.safety_mode:
                    self.last_code_for_approval = final_code
                    yield "result", "\nAction requires approval. Type `/approve` to continue."
                    break
                else:
                    yield "status", "Executing..."
                    output, success = self._execute_code(final_code)
                    self._add_assistant_response_to_history(final_code, output, os_command=self.os_mode)
                    yield "result", f"Output:\n{output}"

            elif isinstance(final_response, ExternalToolCall):
                tool_name = final_response.tool_name
                args = final_response.args
                yield "code_chunk", f"\nTool Call: `{tool_name}({', '.join(args)})`\n"

                if self.safety_mode:
                    self.last_tool_for_approval = (tool_name, args)
                    yield "result", "\nAction requires approval. Type `/approve` to continue."
                    break
                else:
                    yield "status", f"Executing tool {tool_name}..."
                    success, output = self.program_manager.execute_program(tool_name, args)
                    assistant_response = f"Executed External Tool:\n`{tool_name} {' '.join(args)}`\nOutput:\n```\n{output}```"
                    self.conversation_history.append({"role": "assistant", "content": assistant_response})
                    yield "result", f"Output:\n{output}"

    def run(self, user_input: str):
        """
        Starts a new task and enters the iterative loop.
        """
        if not self.is_ready:
            yield "result", "Error: Interpreter is not ready. Please check API key."
            return

        self.conversation_history.append({"role": "user", "content": user_input})
        yield from self._run_loop()