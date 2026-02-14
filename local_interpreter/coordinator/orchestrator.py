import os
import re
import importlib
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List, Union
from ..tools.tool_decorator import TOOL_REGISTRY
from ..tools.file_models import File, FileModification

# 用于结构化 AI 响应的 Pydantic 模型
class PythonCode(BaseModel):
    """表示要执行的一块 Python 代码。"""
    thought: str = Field(..., description="运行此代码的原因和思考过程。")
    tool_type: str = "python"
    code: str = Field(..., description="要执行的 Python 代码。")

class ExternalToolCall(BaseModel):
    """表示对注册的外部程序的调用。"""
    thought: str = Field(..., description="调用此工具的原因和思考过程。")
    tool_type: str = "external"
    tool_name: str = Field(..., description="要调用的外部工具的唯一名称。")
    args: List[str] = Field(default_factory=list, description="传递给工具的参数列表。")

class FinalResponse(BaseModel):
    """表示任务完成时对用户的最终响应。"""
    thought: str = Field(..., description="对已完成工作的简要总结。")
    tool_type: str = "final"
    message: str = Field(..., description="发送给用户的最终消息。")

# AI 可以选择响应这些结构中的任何一个
AIResponse = Union[PythonCode, ExternalToolCall, FinalResponse]

def load_all_tools():
    """
    动态导入 'tools' 目录中的所有模块以填充 TOOL_REGISTRY。
    这应该在启动时运行一次。
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
    生成针对执行模式和可用工具定制的系统提示词。
    """
    prompt_header = """
你是一个能够控制计算机以实现用户目标的自主 AI 代理。
你以迭代循环的方式运行：
1. **分析**用户请求和当前状态（包括之前的输出或截图）。
2. **思考**下一步的最佳行动。
3. **行动**：通过生成工具调用（Python 代码或外部工具）。
4. **观察**行动的结果。
5. **重复**直到任务完成，然后提供 `FinalResponse`。
"""

    if os_mode:
        tools_section = "**可用工具：**\n"
        # 在 OS 模式下，我们允许访问所有内容，包括 shell 和文件
        for tool_name, tool_data in TOOL_REGISTRY.items():
            tools_section += f"- `{tool_name}{tool_data['signature']}`: {tool_data['docstring']}\n"

        prompt_footer = """
**操作系统模式说明：**
- 系统会为你提供用户屏幕的截图。
- 使用 GUI 工具（`move_mouse`, `click`, `type_text`）与视觉元素交互。
- 在更高效的情况下，使用 `run_shell` 执行终端命令，或使用 `write_file`/`read_file` 进行文件操作。
- **务必在 `thought` 字段中解释你的思考过程。**
- 如果你卡住了，请在 `FinalResponse` 中描述原因。
"""
    else:
        tools_section = "**可用 Python 工具：**\n"
        # 如果不是 OS 模式，过滤掉低级鼠标/键盘工具以保持“安全”，除非另有要求
        os_tool_names = ["move_mouse", "click", "type_text"]
        for tool_name, tool_data in TOOL_REGISTRY.items():
            if tool_name not in os_tool_names:
                tools_section += f"- `{tool_name}{tool_data['signature']}`: {tool_data['docstring']}\n"

        prompt_footer = """
**通用模式说明：**
- 你可以访问安全的 Python 工具和高性能的外部程序。
- **务必在 `thought` 字段中解释你的思考过程。**
- 运行代码后，你将收到输出。根据输出决定是否需要更多步骤。
- 完成后，使用 `FinalResponse` 进行总结。
"""

    external_tools_section = ""
    if external_tools:
        external_tools_section = "\n**可用外部程序：**\n"
        external_tools_section += "\n".join(external_tools)
        external_tools_section += "\n"

    final_instructions = """
**响应格式：**
- 你必须返回一个符合以下模式之一的单个 JSON 对象：`PythonCode`、`ExternalToolCall` 或 `FinalResponse`。
- 不要在 JSON 之外添加任何文本。
"""

    return f"{prompt_header}\n{tools_section}{external_tools_section}\n{prompt_footer}\n{final_instructions}"


class Orchestrator:
    def __init__(self):
        """
        初始化编排器：
        1. 加载所有可用工具。
        2. 设置 Deepseek API 客户端。
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
        获取对话历史记录，将其发送给 Deepseek LLM 以生成 Python 代码，
        并返回要执行的代码。

        参数：
            history: 对话历史记录。
            use_os_tools: 如果为 True，则生成用于 OS 控制的提示。
        """
        if not self.client:
            return 'print("Orchestrator not initialized. Please check API key.")'

        # 为当前模式生成适当的系统提示词
        system_prompt = generate_system_prompt(os_mode=use_os_tools)
        messages = [{"role": "system", "content": system_prompt}]

        # 多模态请求的历史记录结构不同
        if use_os_tools:
            # 历史记录中的最后一条消息预计是内容块列表
            last_user_message = history[-1]
            other_messages = history[:-1]
            messages.extend(other_messages)
            messages.append(last_user_message)
        else:
            messages.extend(history)

        try:
            model = "deepseek-vision" if use_os_tools else "deepseek-coder"

            # 检查用户的请求是否涉及文件操作
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

            # 意外响应类型的备选方案
            return 'print("错误：未能从响应中生成有效的文件操作。")'

        except Exception as e:
            print(f"调用 Deepseek API 时出错: {e}")
            return f'print("代码生成过程中出错: {e}")'

    def stream_code_generation(self, history: list, use_os_tools: bool = False, external_tools: List[str] = None):
        """
        从 Deepseek LLM 流式传输代码生成。
        在收到部分 AIResponse 模型更新时产生它们。
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

            # 使用 instructor 的 Partial 模式流式传输结构化响应
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
