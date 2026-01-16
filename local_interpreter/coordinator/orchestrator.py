import os
import re
import importlib
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List, Union
from ..tools.tool_decorator import TOOL_REGISTRY
from ..tools.file_models import File, FileModification

# Pydantic models for structured AI responses
class PythonCode(BaseModel):
    """Represents a block of Python code to be executed."""
    tool_type: str = "python"
    code: str = Field(..., description="The Python code to execute.")

class ExternalToolCall(BaseModel):
    """Represents a call to a registered external program."""
    tool_type: str = "external"
    tool_name: str = Field(..., description="The unique name of the external tool to be called.")
    args: List[str] = Field(default_factory=list, description="A list of arguments to pass to the tool.")

# The AI can choose to respond with either of these structures
AIResponse = Union[PythonCode, ExternalToolCall]

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

def generate_system_prompt(os_mode: bool = False, external_tools: List[str] = None) -> str:
    """
    Generates a system prompt tailored to the execution mode and available tools.

    Args:
        os_mode: If True, generates a prompt for GUI automation.
        external_tools: A list of formatted strings describing available external tools.
    """
    if os_mode:
        prompt_header = """
You are an expert OS automation assistant. Your goal is to achieve the user's request in the most efficient way possible.
You can use a combination of direct commands and GUI automation.
"""
        os_tool_names = [
            "open_application", "open_url", "capture_screen", "move_mouse", "click", "type_text"
        ]
        tools_section = "**Available Tools:**\n"
        for tool_name in os_tool_names:
            if tool_name in TOOL_REGISTRY:
                tool_data = TOOL_REGISTRY[tool_name]
                tools_section += f"- `{tool_name}{tool_data['signature']}`: {tool_data['docstring']}\n"

        prompt_footer = """
**Instructions:**
- **Prioritize direct actions.** Use `open_application` or `open_url` if they can accomplish the goal directly.
- **Use GUI tools as a fallback.** If a direct action isn't possible, use the screenshot and tools to interact with the screen.
- Your response must be only the Python code required, wrapped in triple backticks (```python).
"""
        return f"{prompt_header}\n{tools_section}\n{prompt_footer}"
    else:
        prompt_header = """
You are a helpful assistant that translates natural language commands into executable actions.
You have access to two types of tools: safe Python tools and registered external programs.
"""
        os_tool_names = ["capture_screen", "move_mouse", "click", "type_text"]
        tools_section = "**Available Python Tools:**\n"
        for tool_name, tool_data in TOOL_REGISTRY.items():
            if tool_name not in os_tool_names:
                tools_section += f"- `{tool_name}{tool_data['signature']}`: {tool_data['docstring']}\n"

        external_tools_section = ""
        if external_tools:
            external_tools_section = "\n**Available External Programs (High-Performance):**\n"
            external_tools_section += "\n".join(external_tools)
            external_tools_section += "\n"

        prompt_footer = """
**Instructions:**
1.  **Analyze the request:** Decide if it's better handled by a Python script or an external program.
2.  **To execute Python code:** Respond with a JSON object matching the `PythonCode` schema.
3.  **To execute an external program:** Respond with a JSON object matching the `ExternalToolCall` schema. Use the exact `tool_name` from the list above.
4.  **Respond ONLY with the single, valid JSON object.** Do not add any other text, comments, or formatting.
"""
        return f"{prompt_header}\n{tools_section}{external_tools_section}\n{prompt_footer}"


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

    def stream_code_generation(self, history: list, use_os_tools: bool = False, external_tools: List[str] = None):
        """
        Streams the code generation from the Deepseek LLM.
        Yields partial AIResponse model updates as they are received.
        """
        if not self.client:
            yield PythonCode(code='print("Orchestrator not initialized. Please check API key.")')
            return

        system_prompt = generate_system_prompt(os_mode=use_os_tools, external_tools=external_tools)
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

            # Use instructor's Partial mode for streaming the structured response
            stream = self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_model=instructor.Partial[AIResponse],
                max_tokens=1024,
                temperature=0,
                stream=True,
            )

            for partial_response in stream:
                yield partial_response

        except Exception as e:
            print(f"Error during streaming from Deepseek API: {e}")
            yield PythonCode(code=f'print("Error: {e}")')
