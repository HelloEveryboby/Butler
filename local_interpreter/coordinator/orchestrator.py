import os
import re
import importlib
import instructor
from openai import OpenAI
from ..tools.tool_decorator import TOOL_REGISTRY
from ..tools.file_models import File, FileModification

def load_all_tools():
    """
    Dynamically imports all modules in the 'tools' directory to populate the TOOL_REGISTRY.
    This should be run once at startup.
    """
    tools_dir = os.path.dirname(__file__)
    tools_path = os.path.join(os.path.dirname(tools_dir), "tools")

    for filename in os.listdir(tools_path):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"local_interpreter.tools.{filename[:-3]}"
            try:
                importlib.import_module(module_name)
            except Exception as e:
                print(f"Error loading tool module {module_name}: {e}")

def generate_system_prompt(os_mode: bool = False) -> str:
    """
    Generates a system prompt tailored to the execution mode (standard or OS).

    Args:
        os_mode: If True, generates a prompt for GUI automation.
                 Otherwise, generates the standard code generation prompt.
    """
    if os_mode:
        prompt_header = """
You are an expert OS automation assistant. Your goal is to achieve the user's request in the most efficient way possible.
You can use a combination of direct commands and GUI automation.
"""
        # Define the full suite of OS tools, both high-level and low-level
        os_tool_names = [
            "open_application", "open_url",  # High-level "power" tools
            "capture_screen", "move_mouse", "click", "type_text" # Low-level GUI tools
        ]
        tools_section = "**Available Tools:**\n"
        for tool_name in os_tool_names:
            if tool_name in TOOL_REGISTRY:
                tool_data = TOOL_REGISTRY[tool_name]
                tools_section += f"- `{tool_name}{tool_data['signature']}`: {tool_data['docstring']}\n"

        prompt_footer = """
**Instructions:**
- **Prioritize direct actions.** Use `open_application` or `open_url` if they can accomplish the goal directly.
- **Use GUI tools as a fallback.** If a direct action isn't possible, use the screenshot and tools like `move_mouse`, `click`, and `type_text` to interact with the screen.
- Your response must be only the Python code required. Do not add any explanation or formatting.
- Wrap the code in triple backticks (```python).
"""
    else:
        prompt_header = """
You are a helpful assistant that translates natural language commands into executable Python code.
You have access to a set of safe tools to interact with the system.
"""
        # Filter out OS-specific tools for the standard prompt
        os_tool_names = ["capture_screen", "move_mouse", "click", "type_text"]
        tools_section = "**Available Tools:**\n"
        for tool_name, tool_data in TOOL_REGISTRY.items():
            if tool_name not in os_tool_names:
                tools_section += f"- `{tool_name}{tool_data['signature']}`: {tool_data['docstring']}\n"

        prompt_footer = """
**Instructions:**
- Choose the best tool for the job.
- Only output the raw Python code to be executed. Do not add any explanation or formatting.
- Wrap the code in triple backticks (```python).
- If you cannot generate code for a command, output the word "Error" inside backticks.
"""
    return f"{prompt_header}\n{tools_section}\n{prompt_footer}"


class Orchestrator:
    def __init__(self):
        """
        Initializes the Orchestrator:
        1. Loads all available tools.
        2. Sets up the Deepseek API client.
        """
        try:
            load_all_tools()
            from dotenv import load_dotenv
            load_dotenv()
            self.api_key = os.getenv("DEEPSEEK_API_KEY")
            if not self.api_key:
                raise ValueError("DEEPSEEK_API_KEY not found in environment variables.")

            # Patch the OpenAI client with instructor
            self.client = instructor.patch(
                OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com"),
                mode=instructor.Mode.JSON,
            )
        except Exception as e:
            print(f"Error initializing Orchestrator: {e}")
            self.client = None

    def process_user_input(self, history: list, use_os_tools: bool = False) -> str:
        """
        Takes the conversation history, sends it to the Deepseek LLM to generate Python code,
        and returns the code to be executed.

        Args:
            history: The conversation history.
            use_os_tools: If True, generates a prompt for OS control.
        """
        if not self.client:
            return 'print("Orchestrator not initialized. Please check API key.")'

        # Generate the appropriate system prompt for the current mode
        system_prompt = generate_system_prompt(os_mode=use_os_tools)
        messages = [{"role": "system", "content": system_prompt}]

        # The history for multimodal requests is structured differently
        if use_os_tools:
            # The last message in the history is expected to be a list of content blocks
            last_user_message = history[-1]
            other_messages = history[:-1]
            messages.extend(other_messages)
            messages.append(last_user_message)
        else:
            messages.extend(history)

        try:
            model = "deepseek-vision" if use_os_tools else "deepseek-coder"

            # Check if the user's request involves file operations
            if "file" in " ".join([m["content"] for m in history if isinstance(m["content"], str)]).lower():
                response_model = FileModification
            else:
                response_model = File

            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_model=response_model,
                max_tokens=1024,
                temperature=0,
            )

            if isinstance(response, FileModification):
                if response.action == "create":
                    return f'write_file(r"{response.file_path}", """{response.description}""")'
                elif response.action == "delete":
                    return f'delete_file(r"{response.file_path}")'
                elif response.action == "modify":
                    return f'modify_file(r"{response.file_path}", """{response.description}""")'
            elif isinstance(response, File):
                return f'write_file(r"{response.file_path}", """{response.content}""")'

            # Fallback for unexpected response types
            return 'print("Error: Could not generate a valid file operation from the response.")'

        except Exception as e:
            print(f"Error calling Deepseek API: {e}")
            return f'print("Error during code generation: {e}")'

    def stream_code_generation(self, history: list, use_os_tools: bool = False):
        """
        Streams the code generation from the Deepseek LLM using instructor.
        Yields partial code model updates as they are received.
        """
        if not self.client:
            yield 'print("Orchestrator not initialized. Please check API key.")'
            return

        system_prompt = generate_system_prompt(os_mode=use_os_tools)
        messages = [{"role": "system", "content": system_prompt}]

        if use_os_tools:
            last_user_message = history[-1]
            other_messages = history[:-1]
            messages.extend(other_messages)
            messages.append(last_user_message)
        else:
            messages.extend(history)

        try:
            model = "deepseek-vision" if use_os_tools else "deepseek-coder"

            # Use instructor's Partial mode for streaming
            response_model = File

            stream = self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_model=instructor.Partial[response_model],
                max_tokens=1024,
                temperature=0,
                stream=True,
            )

            for partial_response in stream:
                yield partial_response

        except Exception as e:
            print(f"Error during streaming from Deepseek API: {e}")
            # Yield a final object that represents the error
            yield File(file_path="error.py", content=f'print("Error: {e}")')
