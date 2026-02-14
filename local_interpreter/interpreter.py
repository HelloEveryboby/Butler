import io
from contextlib import redirect_stdout
from .coordinator.orchestrator import Orchestrator, PythonCode, ExternalToolCall, FinalResponse
from .executor.code_executor import Sandbox, SandboxError
from .tools import os_tools, power_tools
from butler.core.extension_manager import extension_manager

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
        self.extension_manager = extension_manager
        self.conversation_history = []
        self.safety_mode = safety_mode
        self.os_mode = os_mode
        self.max_iterations = max_iterations
        self.last_code_for_approval = None
        self.last_tool_for_approval = None

        # 简单检查编排器是否初始化失败（例如没有 API 密钥）
        if not self.orchestrator.client:
            self.is_ready = False
            print("警告：解释器初始化时没有有效的 API 客户端。")
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

        # Add extensions as tools
        for tool in self.extension_manager.get_all_tools():
            tool_name = tool['name']
            if tool['type'] == 'package' and hasattr(tool['module'], 'run'):
                execution_globals[tool_name] = tool['module'].run
            elif tool['type'] == 'plugin':
                execution_globals[tool_name] = tool['instance'].run
            # External programs are handled via ExternalToolCall in _run_loop

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
                    # 在 OS 模式下，我们绕过沙箱并直接使用 exec
                    exec(code, execution_globals)
                else:
                    # 在标准模式下，我们使用沙箱但仍提供安全工具
                    # 注意：沙箱有其自己的受限内置函数和导入器
                    self.sandbox.execute(code, globals_dict=execution_globals)
            output = output_catcher.getvalue()
            success = True
        except SandboxError as e:
            output = f"沙箱错误: {e}"
        except Exception as e:
            output = f"执行过程中发生意外错误: {e}"
        return output, success

    def _add_assistant_response_to_history(self, code: str, output: str, os_command: bool = False):
        """格式化并将助手的响应添加到历史记录的辅助函数。"""
        response_type = "已执行 OS 命令" if os_command else "已执行代码"
        assistant_response = f"{response_type}:\n```python\n{code}```\n输出:\n```\n{output}```"
        self.conversation_history.append({"role": "assistant", "content": assistant_response})

    def run_approved_code(self):
        """
        执行最后生成并等待批准的代码或工具。
        然后继续循环。
        """
        if self.last_code_for_approval:
            code = self.last_code_for_approval
            self.last_code_for_approval = None
            yield "status", "正在执行批准的代码..."

            output, success = self._execute_code(code)
            self._add_assistant_response_to_history(code, output, os_command=self.os_mode)
            yield "result", f"输出:\n{output}"

        elif self.last_tool_for_approval:
            tool_name, args = self.last_tool_for_approval
            self.last_tool_for_approval = None
            yield "status", f"正在执行批准的工具: {tool_name}..."
            output = self.extension_manager.execute(tool_name, *args)
            assistant_response = f"已执行外部工具:\n`{tool_name} {' '.join(args)}`\n输出:\n```\n{output}```"
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            yield "result", f"输出:\n{output}"
        else:
            yield "result", "没有待批准的操作。"
            return

        # Continue the loop automatically
        yield from self._run_loop()

    def _run_loop(self):
        """
        解释器的核心迭代循环。
        """
        for i in range(len(self.conversation_history), len(self.conversation_history) + self.max_iterations):
            yield "status", f"正在思考 (步骤 {i})..."

            if self.os_mode:
                 # 在 OS 模式下，每步捕获屏幕
                 screenshot_b64 = os_tools.capture_screen()
                 yield "screenshot", screenshot_b64

                 # 为防止上下文窗口溢出，我们替换历史记录中较旧的截图
                 for msg in self.conversation_history:
                     if isinstance(msg.get("content"), list):
                         for part in msg["content"]:
                             if part.get("type") == "image_url":
                                 # 用占位符替换图像
                                 part["type"] = "text"
                                 part["text"] = "[为节省空间，已省略之前的截图]"
                                 del part["image_url"]

                 self.conversation_history.append({
                     "role": "user",
                     "content": [
                         {"type": "text", "text": "当前屏幕观察："},
                         {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
                     ]
                 })

            # Collect descriptions from all extensions
            tool_descriptions = []
            for tool in self.extension_manager.get_all_tools():
                tool_descriptions.append(f"- `{tool['name']}`: {tool['description']}")

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
                yield "result", "错误：未能从 AI 获取响应。"
                break

            if isinstance(final_response, FinalResponse):
                yield "result", f"\n**最终回答：** {final_response.message}"
                break

            # 处理操作
            if isinstance(final_response, PythonCode):
                final_code = final_response.code
                yield "code_chunk", f"\n```python\n{final_code}\n```\n"

                if self.safety_mode:
                    self.last_code_for_approval = final_code
                    yield "result", "\n操作需要批准。输入 `/approve` 继续。"
                    break
                else:
                    yield "status", "正在执行..."
                    output, success = self._execute_code(final_code)
                    self._add_assistant_response_to_history(final_code, output, os_command=self.os_mode)
                    yield "result", f"输出:\n{output}"

            elif isinstance(final_response, ExternalToolCall):
                tool_name = final_response.tool_name
                args = final_response.args
                yield "code_chunk", f"\n工具调用: `{tool_name}({', '.join(args)})`\n"

                if self.safety_mode:
                    self.last_tool_for_approval = (tool_name, args)
                    yield "result", "\n操作需要批准。输入 `/approve` 继续。"
                    break
                else:
                    yield "status", f"正在执行工具 {tool_name}..."
                    output = self.extension_manager.execute(tool_name, *args)
                    assistant_response = f"已执行外部工具:\n`{tool_name} {' '.join(args)}`\n输出:\n```\n{output}```"
                    self.conversation_history.append({"role": "assistant", "content": assistant_response})
                    yield "result", f"输出:\n{output}"

    def run(self, user_input: str):
        """
        开始新任务并进入迭代循环。
        """
        if not self.is_ready:
            yield "result", "错误：解释器未就绪。请检查 API 密钥。"
            return

        self.conversation_history.append({"role": "user", "content": user_input})
        yield from self._run_loop()