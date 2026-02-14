from collections import defaultdict
from pathlib import Path
from typing import Literal, get_args

from .base import BaseTool, CLIResult, ToolError, ToolResult
from .run import maybe_truncate, run

Command = Literal[
    "view",
    "create",
    "str_replace",
    "insert",
    "undo_edit",
]
SNIPPET_LINES: int = 4


class EditTool(BaseTool):
    """
    允许代理查看、创建和编辑文件的文件系统编辑器工具。
    """

    name: Literal["str_replace_editor"] = "str_replace_editor"

    _file_history: dict[Path, list[str]]

    def __init__(self):
        self._file_history = defaultdict(list)
        super().__init__()

    async def __call__(
        self,
        *,
        command: Command,
        path: str,
        file_text: str | None = None,
        view_range: list[int] | None = None,
        old_str: str | None = None,
        new_str: str | None = None,
        insert_line: int | None = None,
        **kwargs,
    ):
        # 执行命令前请求用户许可
        print(f"是否要执行以下命令？")
        print(f"命令: {command}")
        print(f"路径: {path}")
        if file_text:
            print(f"文件内容: {file_text}")
        if view_range:
            print(f"查看范围: {view_range}")
        if old_str:
            print(f"旧字符串: {old_str}")
        if new_str:
            print(f"新字符串: {new_str}")
        if insert_line is not None:
            print(f"插入行: {insert_line}")

        user_input = input("输入 'yes' 继续，输入其他内容取消: ")

        if user_input.lower() != "yes":
            return ToolResult(
                system="命令执行被用户取消",
                error="用户未提供执行命令的权限。",
            )
        _path = Path(path)
        self.validate_path(command, _path)
        if command == "view":
            return await self.view(_path, view_range)
        elif command == "create":
            if not file_text:
                raise ToolError("对于 create 命令，参数 `file_text` 是必需的")
            self.write_file(_path, file_text)
            self._file_history[_path].append(file_text)
            return ToolResult(output=f"文件已成功创建于: {_path}")
        elif command == "str_replace":
            if not old_str:
                raise ToolError(
                    "对于 str_replace 命令，参数 `old_str` 是必需的"
                )
            return self.str_replace(_path, old_str, new_str)
        elif command == "insert":
            if insert_line is None:
                raise ToolError(
                    "对于 insert 命令，参数 `insert_line` 是必需的"
                )
            if not new_str:
                raise ToolError("对于 insert 命令，参数 `new_str` 是必需的")
            return self.insert(_path, insert_line, new_str)
        elif command == "undo_edit":
            return self.undo_edit(_path)
        raise ToolError(
            f'无法识别的命令 {command}。{self.name} 工具允许使用的命令是: {", ".join(get_args(Command))}'
        )

    def validate_path(self, command: str, path: Path):
        """
        检查路径/命令组合是否有效。
        """
        # 检查是否为绝对路径
        if not path.is_absolute():
            suggested_path = Path("") / path
            raise ToolError(
                f"路径 {path} 不是绝对路径，它应该以 `/` 开头。你可能是想指 {suggested_path}？"
            )
        # 检查路径是否存在
        if not path.exists() and command != "create":
            raise ToolError(
                f"路径 {path} 不存在。请提供一个有效的路径。"
            )
        if path.exists() and command == "create":
            raise ToolError(
                f"文件已存在于: {path}。不能使用 `create` 命令覆盖文件。"
            )
        # 检查路径是否指向目录
        if path.is_dir():
            if command != "view":
                raise ToolError(
                    f"路径 {path} 是一个目录，只有 `view` 命令可以用于目录"
                )

    async def view(self, path: Path, view_range: list[int] | None = None):
        """执行视图命令"""
        if path.is_dir():
            if view_range:
                raise ToolError(
                    "当 `path` 指向目录时，不允许使用 `view_range` 参数。"
                )

            _, stdout, stderr = await run(
                rf"find {path} -maxdepth 2 -not -path '*/\.*'"
            )
            if not stderr:
                stdout = f"这是 {path} 中深达 2 级的文件和目录（不包括隐藏项目）：\n{stdout}\n"
            return CLIResult(output=stdout, error=stderr)

        file_content = self.read_file(path)
        init_line = 1
        if view_range:
            if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
                raise ToolError(
                    "无效的 `view_range`。它应该是包含两个整数的列表。"
                )
            file_lines = file_content.split("\n")
            n_lines_file = len(file_lines)
            init_line, final_line = view_range
            if init_line < 1 or init_line > n_lines_file:
                raise ToolError(
                    f"无效的 `view_range`: {view_range}。它的第一个元素 `{init_line}` 应该在文件的行数范围内: {[1, n_lines_file]}"
                )
            if final_line > n_lines_file:
                raise ToolError(
                    f"无效的 `view_range`: {view_range}。它的第二个元素 `{final_line}` 应该小于文件的行数: `{n_lines_file}`"
                )
            if final_line != -1 and final_line < init_line:
                raise ToolError(
                    f"无效的 `view_range`: {view_range}。它的第二个元素 `{final_line}` 应该大于或等于第一个元素 `{init_line}`"
                )

            if final_line == -1:
                file_content = "\n".join(file_lines[init_line - 1 :])
            else:
                file_content = "\n".join(file_lines[init_line - 1 : final_line])

        return CLIResult(
            output=self._make_output(file_content, str(path), init_line=init_line)
        )

    def str_replace(self, path: Path, old_str: str, new_str: str | None):
        """实现str_replace命令，该命令将文件内容中的old_str替换为new_str"""
        # 读取文件内容
        file_content = self.read_file(path).expandtabs()
        old_str = old_str.expandtabs()
        new_str = new_str.expandtabs() if new_str is not None else ""

        # 检查 old_str 在文件中是否唯一
        occurrences = file_content.count(old_str)
        if occurrences == 0:
            raise ToolError(
                f"未进行更换, old_str `{old_str}` 未在中逐字出现 {path}."
            )
        elif occurrences > 1:
            file_content_lines = file_content.split("\n")
            lines = [
                idx + 1
                for idx, line in enumerate(file_content_lines)
                if old_str in line
            ]
            raise ToolError(
                f"未进行置换。old_str多次出现 `{old_str}` 行 {lines}. 请确保其唯一"
            )

        # 将old_str替换为new_str
        new_file_content = file_content.replace(old_str, new_str)

        # 将新内容写入文件
        self.write_file(path, new_file_content)

        # 将内容保存到历史记录
        self._file_history[path].append(file_content)

        # 创建已编辑节的片段
        replacement_line = file_content.split(old_str)[0].count("\n")
        start_line = max(0, replacement_line - SNIPPET_LINES)
        end_line = replacement_line + SNIPPET_LINES + new_str.count("\n")
        snippet = "\n".join(new_file_content.split("\n")[start_line : end_line + 1])

        # 准备成功消息
        success_msg = f"文件 {path} 已编辑。"
        success_msg += self._make_output(
            snippet, f"{path} 的代码片段", start_line + 1
        )
        success_msg += "检查更改并确保它们符合预期。如有必要，再次编辑该文件。"

        return CLIResult(output=success_msg)

    def insert(self, path: Path, insert_line: int, new_str: str):
        """执行insert命令，在文件内容的指定行插入new_str。"""
        file_text = self.read_file(path).expandtabs()
        new_str = new_str.expandtabs()
        file_text_lines = file_text.split("\n")
        n_lines_file = len(file_text_lines)

        if insert_line < 0 or insert_line > n_lines_file:
            raise ToolError(
                f"无效的'insert_line'参数: {insert_line}. 它应该在文件的行的范围内: {[0, n_lines_file]}"
            )

        new_str_lines = new_str.split("\n")
        new_file_text_lines = (
            file_text_lines[:insert_line]
            + new_str_lines
            + file_text_lines[insert_line:]
        )
        snippet_lines = (
            file_text_lines[max(0, insert_line - SNIPPET_LINES) : insert_line]
            + new_str_lines
            + file_text_lines[insert_line : insert_line + SNIPPET_LINES]
        )

        new_file_text = "\n".join(new_file_text_lines)
        snippet = "\n".join(snippet_lines)

        self.write_file(path, new_file_text)
        self._file_history[path].append(file_text)

        success_msg = f"文件 {path} 已编辑。"
        success_msg += self._make_output(
            snippet,
            "编辑后文件的代码片段",
            max(1, insert_line - SNIPPET_LINES + 1),
        )
        success_msg += "检查更改并确保它们符合预期(正确的缩进、无重复行等)。如有必要，再次编辑文件。"
        return CLIResult(output=success_msg)

    def undo_edit(self, path: Path):
        """执行 undo_edit 命令。"""
        if not self._file_history[path]:
            raise ToolError(f"未找到 {path} 的编辑历史。")

        old_text = self._file_history[path].pop()
        self.write_file(path, old_text)

        return CLIResult(
            output=f"成功撤销对 {path} 的最后一次编辑。{self._make_output(old_text, str(path))}"
        )

    def read_file(self, path: Path):
        """从给定路径读取文件的内容；如果发生错误，则引发 ToolError。"""
        try:
            return path.read_text()
        except Exception as e:
            raise ToolError(f"尝试读取 {path} 时遇到 {e}") from None

    def write_file(self, path: Path, file: str):
        """将文件的内容写入给定的路径；如果发生错误，则引发 ToolError。"""
        try:
            path.write_text(file)
        except Exception as e:
            raise ToolError(f"尝试写入 {path} 时遇到 {e}") from None

    def _make_output(
        self,
        file_content: str,
        file_descriptor: str,
        init_line: int = 1,
        expand_tabs: bool = True,
    ):
        """基于文件内容为 CLI 生成输出。"""
        file_content = maybe_truncate(file_content)
        if expand_tabs:
            file_content = file_content.expandtabs()
        file_content = "\n".join(
            [
                f"{i + init_line:6}\t{line}"
                for i, line in enumerate(file_content.split("\n"))
            ]
        )
        return (
            f"这是对 {file_descriptor} 运行 `cat -n` 的结果：\n"
            + file_content
            + "\n"
        )
