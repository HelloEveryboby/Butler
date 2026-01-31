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
    thought: str = Field(..., description="Your reasoning for why you are running this code.")
    tool_type: str = "python"
    code: str = Field(..., description="The Python code to execute.")

class ExternalToolCall(BaseModel):
    """Represents a call to a registered external program."""
    thought: str = Field(..., description="Your reasoning for why you are calling this tool.")
    tool_type: str = "external"
    tool_name: str = Field(..., description="The unique name of the external tool to be called.")
    args: List[str] = Field(default_factory=list, description="A list of arguments to pass to the tool.")

class FinalResponse(BaseModel):
    """Represents the final response to the user when the task is complete."""
    thought: str = Field(..., description="A brief summary of what you have accomplished.")
    tool_type: str = "final"
    message: str = Field(..., description="The final message to send to the user.")

# The AI can choose to respond with either of these structures
AIResponse = Union[PythonCode, ExternalToolCall, FinalResponse]

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
    """
    prompt_header = """
You are an autonomous AI agent capable of controlling a computer to achieve user goals.
You operate in an iterative loop:
1. **Analyze** the user request and current state (including previous outputs or screenshots).
2. **Think** about the next best step.
3. **Act** by generating a tool call (Python code or external tool).
4. **Observe** the results of your action.
5. **Repeat** until the task is complete, then provide a `FinalResponse`.
"""

    if os_mode:
        tools_section = "**Available Tools:**\n"
        # In OS mode, we give access to EVERYTHING including shell and files
        for tool_name, tool_data in TOOL_REGISTRY.items():
            tools_section += f"- `{tool_name}{tool_data['signature']}`: {tool_data['docstring']}\n"

        prompt_footer = """
**Operating System Mode Instructions:**
- You are provided with a screenshot of the user's screen.
- Use GUI tools (`move_mouse`, `click`, `type_text`) to interact with visual elements.
- Use `run_shell` to execute terminal commands or `write_file`/`read_file` for file operations when more efficient.
- **Always explain your thought process in the `thought` field.**
- If you are stuck, describe why in a `FinalResponse`.
"""
    else:
        tools_section = "**Available Python Tools:**\n"
        # Filter out low-level mouse/keyboard tools if not in OS mode to keep it "safe" unless requested
        os_tool_names = ["move_mouse", "click", "type_text"]
        for tool_name, tool_data in TOOL_REGISTRY.items():
            if tool_name not in os_tool_names:
                tools_section += f"- `{tool_name}{tool_data['signature']}`: {tool_data['docstring']}\n"

        prompt_footer = """
**General Mode Instructions:**
- You have access to safe Python tools and high-performance external programs.
- **Always explain your thought process in the `thought` field.**
- After running code, you will receive the output. Use it to decide if you need more steps.
- When finished, use `FinalResponse` to summarize.
"""

    external_tools_section = ""
    if external_tools:
        external_tools_section = "\n**Available External Programs:**\n"
        external_tools_section += "\n".join(external_tools)
        external_tools_section += "\n"

    final_instructions = """
**Response Format:**
- You MUST respond with a single JSON object matching one of the schemas: `PythonCode`, `ExternalToolCall`, or `FinalResponse`.
- Do not add any text outside the JSON.
"""

    return f"{prompt_header}\n{tools_section}{external_tools_section}\n{prompt_footer}\n{final_instructions}"


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
