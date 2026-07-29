"""
CommandPanel — TUI 界面（基于 Textual 8.x）

原 tkinter 版本的终端重写：
- 左侧：程序列表（搜索）/ 压缩包浏览器（树）/ 手动工具栏 / 设置
- 右侧：显示模式切换 + 连接状态 / 聊天输出（带标记/tag） / 输入框 + 操作按钮
- 截图功能降级：保存 base64 到临时文件并在输出区提示路径；点击改手动输入坐标

兼容：
    panel.set_command_callback(cb)
    panel.append_to_history(text, tag, response_id)
    panel.append_to_response(chunk, response_id)
    panel.set_input_text(text)
    panel.update_screenshot(b64)
    panel.update_link_status(connected, device)
    panel.update_listen_button_state(is_listening)
    panel.show_update_dialog(filename) -> bool
    panel.clear_history()
    panel.restart_application()
"""

from __future__ import annotations

import base64
import os
import re
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from queue import Queue, Empty
from typing import Any, Callable

try:
    from pygments import lex
    from pygments.lexers import get_lexer_by_name, guess_lexer
    PYGMENTS_INSTALLED = True
except ImportError:
    PYGMENTS_INSTALLED = False

try:
    from rich.markdown import Markdown as RichMarkdown
    from rich.syntax import Syntax
except ImportError:  # pragma: no cover - textual 依赖 rich，理论上必在
    RichMarkdown = None
    Syntax = None

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import (
    Container,
    Horizontal,
    Vertical,
    VerticalScroll,
    HorizontalScroll,
)
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    RadioButton,
    RadioSet,
    RichLog,
    Static,
    Tab,
    Tabs,
    Tree,
)
from textual.widgets.tree import TreeNode
from textual.reactive import reactive
from textual.events import Mount

from package.core_utils.log_manager import LogManager
from butler.core.event_bus import event_bus

logger = LogManager.get_logger(__name__)

TAG_STYLES = {
    "user_prompt": {"color": "#ff00ff", "bold": True},
    "ai_response": {"color": "#d4d4d4"},
    "system_message": {"color": "#00ffff", "italic": True},
    "error": {"color": "#ff0000", "bold": True},
}

DISPLAY_MODES = ["host", "usb", "both"]
DISPLAY_MODE_LABELS = {"host": "主机", "usb": "USB", "both": "双显"}


@dataclass
class _ResponseBlock:
    """流式响应片段缓冲。"""
    buffer: str = ""
    rendered_len: int = 0


class ProgramList(ListView):
    """带搜索过滤的程序列表视图。"""

    def __init__(self, programs: dict[str, Any], on_select: Callable[[str], None]):
        super().__init__()
        self._all_items = sorted(programs.keys())
        self._on_select = on_select
        self._build_items(self._all_items)

    def _build_items(self, names):
        """重建 ListItem 列表。"""
        self.clear()
        for n in names:
            li = ListItem(Label(n, markup=False))
            li.name = n
            self.append(li)

    def filter(self, term: str) -> None:
        term = (term or "").lower()
        if not term:
            self._build_items(self._all_items)
            return
        self._build_items([n for n in self._all_items if term in n.lower()])

    def on_list_view_selected(self, event) -> None:
        item = event.item
        if item and getattr(item, "name", None):
            self._on_select(item.name)


class CommandPanel(App):
    """TUI 版命令面板。Textual App 子类。"""

    CSS = """
    Screen {
        background: $panel;
    }
    #left-pane {
        width: 28%;
        border: solid $primary 70%;
        background: $surface;
    }
    #right-pane {
        width: 1fr;
    }
    #program-search {
        margin: 1 1 0 1;
    }
    #program-list {
        height: 1fr;
        margin: 0 1;
        border: none;
    }
    #archive-tree {
        height: 1fr;
        margin: 0 1;
    }
    #manual-toolbar {
        height: auto;
        margin: 1;
    }
    #manual-toolbar Button {
        width: 1fr;
        margin: 0 1;
    }
    #settings-btn {
        margin: 1;
    }
    #top-bar {
        height: auto;
        padding: 0 1;
        border-bottom: solid $primary 60%;
    }
    #display-modes {
        height: 3;
    }
    #link-status {
        align: right middle;
    }
    #output-log {
        height: 1fr;
        border: solid $primary 60%;
    }
    #input-bar {
        height: auto;
        padding: 1;
    }
    #command-input {
        width: 1fr;
    }
    .op-btn {
        min-width: 8;
        margin-left: 1;
    }
    .section-label {
        height: 1;
        margin: 1 1 0 1;
        color: $accent;
        text-style: bold;
    }
    """

    SCREEN_ID = "jarvis_tui_panel"

    # 反应式变量
    listening = reactive(False)
    link_connected = reactive(False)
    link_device = reactive("")
    display_mode = reactive("host")
    nostalgia = reactive(False)

    def __init__(
        self,
        program_mapping=None,
        programs=None,
        command_callback=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.command_callback = command_callback
        self.program_mapping = program_mapping or {}
        self.programs = programs or {}
        self.all_program_names = sorted(list(self.programs.keys()))

        self.msg_queue: Queue[tuple[str, Any]] = Queue()
        self._stop_event = threading.Event()
        self._queue_thread: threading.Thread | None = None

        # 流式响应块：response_id -> _ResponseBlock
        self._response_blocks: dict[str, _ResponseBlock] = {}

        # 当前归档 zip
        self._current_zip_path: str | None = None

        # 外部回调（jarvis_app 传入）
        self._on_exit_cb: Callable[[], None] | None = None

        # 订阅事件总线
        event_bus.subscribe("ui_output", self._queue_ui_output)
        event_bus.subscribe("voice_status", self._queue_voice_status)
        event_bus.subscribe("link_status", self._queue_link_status)
        event_bus.subscribe("screenshot_update", self._queue_screenshot_update)
        event_bus.subscribe("archive_browser_update", self._queue_archive_update)
        event_bus.subscribe("nostalgia_mode_activated", self._queue_nostalgia)

    # ------------------------ Compose ------------------------ #

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal():
            # 左栏
            with Vertical(id="left-pane"):
                yield Label("程序列表", classes="section-label")
                yield Input(placeholder="搜索程序…", id="program-search")
                yield ProgramList(self.programs, self._on_program_selected)

                yield Label("压缩包浏览器", classes="section-label")
                tree: Tree[str] = Tree("归档", id="archive-tree")
                tree.root.expand()
                yield tree

                yield Label("手动控制", classes="section-label")
                with Horizontal(id="manual-toolbar"):
                    yield Button("📸 截图", id="btn-screenshot", variant="primary")
                    yield Button("🖱 点击", id="btn-click", variant="primary")
                    yield Button("⌨ 输入", id="btn-type", variant="primary")

                yield Button("⚙ 设置", id="settings-btn", variant="default")

            # 右栏
            with Vertical(id="right-pane"):
                with Horizontal(id="top-bar"):
                    with RadioSet(id="display-modes"):
                        for mode in DISPLAY_MODES:
                            checked = mode == "host"
                            yield RadioButton(
                                DISPLAY_MODE_LABELS[mode],
                                value=checked,
                                name=mode,
                            )
                    yield Static("", id="link-status")

                yield RichLog(
                    highlight=True,
                    markup=True,
                    auto_scroll=True,
                    wrap=True,
                    id="output-log",
                )

                with Horizontal(id="input-bar"):
                    yield Input(
                        placeholder="输入命令或对话… (/help 查看命令, Enter 发送)",
                        id="command-input",
                    )
                    yield Button("发送", id="btn-send", classes="op-btn", variant="success")
                    yield Button("聆听", id="btn-listen", classes="op-btn", variant="warning")
                    yield Button("清空", id="btn-clear", classes="op-btn")
                    yield Button("重启", id="btn-restart", classes="op-btn", variant="error")

        yield Footer()

    # ------------------------ Mount / Lifecycle ------------------------ #

    def on_mount(self, event: Mount) -> None:
        # 启动队列处理循环（Textual 的 set_interval 保证在 UI 线程中执行）
        self.set_interval(0.05, self._drain_queue)
        self._update_link_display()
        self._update_listen_btn()
        self._update_display_mode_buttons()

    # ------------------------ Public API (兼容老版本) ------------------------ #

    def set_command_callback(self, callback: Callable[[str, Any], None]) -> None:
        self.command_callback = callback

    def set_on_exit(self, cb: Callable[[], None]) -> None:
        self._on_exit_cb = cb

    def append_to_history(self, text: str, tag: str = "ai_response", response_id: str | None = None) -> None:
        """追加一条消息到输出区域（线程安全，内部转发到 UI 线程）。"""
        self.call_from_thread(self._append_history_ui, text, tag, response_id)

    def append_to_response(self, text_chunk: str, response_id: str) -> None:
        """流式追加到指定响应块。"""
        self.call_from_thread(self._append_response_ui, text_chunk, response_id)

    def set_input_text(self, text: str) -> None:
        self.call_from_thread(self._set_input_text_ui, text)

    def update_screenshot(self, b64_data: str) -> None:
        """截图：保存到临时文件并输出提示。点击在 TUI 中降级为手动输入坐标。"""
        self.call_from_thread(self._update_screenshot_ui, b64_data)

    def update_link_status(self, connected: bool, device_name: str = "") -> None:
        self.call_from_thread(self._update_link_status_ui, connected, device_name)

    def update_listen_button_state(self, is_listening: bool) -> None:
        self.call_from_thread(self._update_listen_ui, is_listening)

    def clear_history(self) -> None:
        self.call_from_thread(self._clear_history_ui)

    def show_update_dialog(self, filename: str) -> bool:
        """同步阻塞式确认。TUI 中用 Yes/No 弹出对话框。

        注意：Textual 推荐异步，这里通过线程事件 + work 桥接同步返回。
        """
        result_holder: list[bool] = [False]
        done = threading.Event()

        async def _ask():
            from textual.screen import Screen
            from textual.widgets import Label as TLabel, Button as TButton

            class ConfirmScreen(Screen[bool]):
                def compose(self):
                    yield Container(
                        TLabel(f"检测到 {filename} 已修改，是否同步回压缩包？"),
                        Horizontal(
                            TButton("是(Y)", id="y", variant="success"),
                            TButton("否(N)", id="n", variant="warning"),
                            TButton("取消(C)", id="c", variant="default"),
                            classes="btns",
                        ),
                        classes="dlg",
                    )

                def on_button_pressed(self, ev):
                    if ev.button.id == "y":
                        self.dismiss(True)
                    elif ev.button.id == "n":
                        self.dismiss(False)
                    else:
                        self.dismiss(None)

            val = await self.push_screen(ConfirmScreen())
            result_holder[0] = bool(val)
            done.set()

        # 从任意线程都能安全推入 UI 调度
        try:
            import asyncio
            self.call_from_thread(lambda: asyncio.ensure_future(_ask()))
        except Exception:
            logger.exception("show_update_dialog 桥接失败")

        done.wait(timeout=60)
        return result_holder[0]

    def restart_application(self) -> None:
        """重启进程（同原版，使用 os.execl）。"""
        python = sys.executable
        self.exit()
        if self._on_exit_cb:
            try:
                self._on_exit_cb()
            except Exception:
                pass
        os.execl(python, python, *sys.argv)

    # ------------------------ UI 线程内的实际操作 ------------------------ #

    def _drain_queue(self) -> None:
        """50ms 周期从 msg_queue 取消息分发。"""
        try:
            while True:
                try:
                    msg_type, payload = self.msg_queue.get_nowait()
                except Empty:
                    return
                self._dispatch_queue_item(msg_type, payload)
        except Exception:
            logger.exception("drain_queue 异常")

    def _dispatch_queue_item(self, msg_type: str, payload: Any) -> None:
        if msg_type == "ui_output":
            message, tag, response_id = payload
            self._append_history_ui(message, tag, response_id)
        elif msg_type == "voice_status":
            self._update_listen_ui(payload)
        elif msg_type == "link_status":
            connected, device = payload
            self._update_link_status_ui(connected, device)
        elif msg_type == "screenshot_update":
            self._update_screenshot_ui(payload)
        elif msg_type == "archive_browser_update":
            zip_path, contents = payload
            self._update_archive_tree_ui(zip_path, contents)
        elif msg_type == "nostalgia_ui":
            self._apply_nostalgia_theme_ui()

    def _append_history_ui(self, text: str, tag: str, response_id: str | None) -> None:
        log = self.query_one("#output-log", RichLog)
        style = TAG_STYLES.get(tag, {})
        color = style.get("color")

        if response_id:
            # 流式首块：登记缓冲，先放普通文本
            block = _ResponseBlock(buffer=text, rendered_len=len(text))
            self._response_blocks[response_id] = block
            self._write_rich(log, text, tag)
            return

        # 非流式：解析 markdown 代码块
        code_block_pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
        last_end = 0
        for m in code_block_pattern.finditer(text):
            pre = text[last_end:m.start()]
            if pre.strip():
                self._write_rich(log, pre, tag)
            language = m.group(1) or "text"
            code = m.group(2)
            self._write_code(log, code, language)
            last_end = m.end()

        tail = text[last_end:]
        if tail.strip():
            self._write_rich(log, tail, tag)

        log.write("")

    def _append_response_ui(self, chunk: str, response_id: str) -> None:
        log = self.query_one("#output-log", RichLog)
        block = self._response_blocks.get(response_id)
        if block is None:
            block = _ResponseBlock()
            self._response_blocks[response_id] = block
        block.buffer += chunk
        # 简单策略：直接追加文本到末尾；不做重渲染（避免 Markdown 解析抖动）
        self._write_plain(log, chunk)

    def _write_rich(self, log: RichLog, text: str, tag: str) -> None:
        style = TAG_STYLES.get(tag, {})
        color = style.get("color")
        bold = style.get("bold", False)
        italic = style.get("italic", False)
        prefix = ""
        suffix = ""
        if bold:
            prefix += "[bold]"
            suffix = "[/bold]"
        if italic:
            prefix += "[italic]"
            suffix = "[/italic]"
        if color:
            prefix = f"[{color}]" + prefix
            suffix = suffix + f"[/{color}]"
        try:
            log.write(f"{prefix}{text}{suffix}")
        except Exception:
            log.write(text)

    def _write_plain(self, log: RichLog, text: str) -> None:
        # RichLog.write 支持 markup=True；这里写裸文本，转义方括号
        safe = text.replace("[", r"\[").replace("]", r"\]")
        try:
            log.write(safe)
        except Exception:
            log.write(text)

    def _write_code(self, log: RichLog, code: str, language: str) -> None:
        if Syntax:
            try:
                syn = Syntax(code, language, theme="monokai", line_numbers=False)
                log.write(syn)
                return
            except Exception:
                pass
        # 降级：用灰色等宽输出
        safe = code.replace("[", r"\[").replace("]", r"\]")
        log.write(f"[#888][dim]``` {language}[/dim][/#888]")
        log.write(f"[#dcdcaa]{safe}[/ #dcdcaa]")
        log.write(f"[#888][dim]```[/dim][/#888]")

    def _set_input_text_ui(self, text: str) -> None:
        inp = self.query_one("#command-input", Input)
        inp.value = text

    def _clear_history_ui(self) -> None:
        self.query_one("#output-log", RichLog).clear()
        self._response_blocks.clear()
        logger.info("Cleared history")

    def _update_screenshot_ui(self, b64_data: str) -> None:
        try:
            img_bytes = base64.b64decode(b64_data)
            fd, path = tempfile.mkstemp(prefix="jarvis_screenshot_", suffix=".png")
            with os.fdopen(fd, "wb") as f:
                f.write(img_bytes)
            self._append_history_ui(
                f"[截图] 已保存到: {path}\n"
                f"（TUI 模式下不支持 Canvas 点击；请通过输入框使用命令 'click X,Y' 触发点击）",
                "system_message",
                None,
            )
        except Exception as e:
            logger.error(f"Failed to save screenshot: {e}")
            self._append_history_ui(f"[截图] 保存失败: {e}", "error", None)

    def _update_link_status_ui(self, connected: bool, device: str) -> None:
        self.link_connected = bool(connected)
        self.link_device = device or ""
        self._update_link_display()

    def _update_listen_ui(self, is_listening: bool) -> None:
        self.listening = bool(is_listening)
        self._update_listen_btn()

    def _update_archive_tree_ui(self, zip_path: str, contents: list[str]) -> None:
        self._current_zip_path = zip_path
        tree: Tree = self.query_one("#archive-tree", Tree)
        tree.reset(os.path.basename(zip_path) or "归档")
        tree.root.expand()
        # 按 / 构建目录树
        root_node: TreeNode = tree.root
        for c in contents or []:
            parts = [p for p in c.split("/") if p]
            node = root_node
            for i, p in enumerate(parts):
                found = None
                for ch in node.children:
                    if ch.label == p:
                        found = ch
                        break
                if found is None:
                    leaf = (i == len(parts) - 1)
                    node = node.add(p, expand=not leaf, data=c if leaf else None)
                else:
                    node = found

    def _apply_nostalgia_theme_ui(self) -> None:
        self.nostalgia = True
        self.stylesheet = """
        $panel: #2b261d;
        $surface: #1a1610;
        $primary: #8b4513;
        $accent: #deb887;
        $text: #d4c5a1;
        Screen { background: $panel; color: $text; }
        """ + self.CSS
        self._append_history_ui("--- 怀旧模式已开启：一中往事 ---", "system_message", None)

    def _update_link_display(self) -> None:
        st = self.query_existing("#link-status", Static)
        if not st:
            return
        if self.link_connected:
            dev = f"({self.link_device})" if self.link_device else ""
            st.update(f"[green]●[/green] 数据链：已连接 {dev}")
        else:
            st.update(f"[dim]●[/dim] 数据链：未连接")

    def _update_listen_btn(self) -> None:
        btn = self.query_existing("#btn-listen", Button)
        if not btn:
            return
        if self.listening:
            btn.label = "停止"
            btn.variant = "error"
        else:
            btn.label = "聆听"
            btn.variant = "warning"

    def _update_display_mode_buttons(self) -> None:
        rs = self.query_existing("#display-modes", RadioSet)
        if not rs:
            return
        # RadioSet 的 pressed index 对应索引
        try:
            idx = DISPLAY_MODES.index(self.display_mode)
        except ValueError:
            idx = 0
        if rs.pressed_index != idx:
            rs.pressed_index = idx

    # ------------------------ Event handlers ------------------------ #

    @on(Input.Changed, "#program-search")
    def _on_search_changed(self, event: Input.Changed) -> None:
        lv = self.query_one("#program-list", ProgramList)
        lv.filter(event.value)

    @on(Input.Submitted, "#command-input")
    def _on_input_submit(self, event: Input.Submitted) -> None:
        self._send_text_command(event.value)

    @on(Button.Pressed, "#btn-send")
    def _on_send_pressed(self, _event: Button.Pressed) -> None:
        inp = self.query_one("#command-input", Input)
        self._send_text_command(inp.value)

    @on(Button.Pressed, "#btn-listen")
    def _on_listen_pressed(self, _event: Button.Pressed) -> None:
        self._fire("voice", None)

    @on(Button.Pressed, "#btn-clear")
    def _on_clear_pressed(self, _event: Button.Pressed) -> None:
        self.clear_history()

    @on(Button.Pressed, "#btn-restart")
    def _on_restart_pressed(self, _event: Button.Pressed) -> None:
        self.restart_application()

    @on(Button.Pressed, "#btn-screenshot")
    def _on_scr(self, _e) -> None:
        self._manual_action("screenshot")

    @on(Button.Pressed, "#btn-click")
    def _on_click(self, _e) -> None:
        # 降级：提示用户使用 click x,y 命令
        self._append_history_ui(
            "请在输入框中使用: click 100,200  (或 left_click 无参数执行当前位置)",
            "system_message",
            None,
        )
        self._manual_action("left_click")

    @on(Button.Pressed, "#btn-type")
    def _on_type(self, _e) -> None:
        inp = self.query_one("#command-input", Input)
        txt = (inp.value or "").strip()
        if not txt:
            self._append_history_ui("请先在输入框中输入文字，再按 ⌨ 输入", "system_message", None)
            return
        self._fire("manual_action", {"action": "type", "text": txt})
        inp.value = ""

    @on(Button.Pressed, "#settings-btn")
    def _on_settings(self, _e) -> None:
        from textual.containers import Container as C
        from textual.screen import ModalScreen

        font_size = reactive("medium")

        class SettingsScreen(ModalScreen[None]):
            def compose(self):
                yield C(
                    Label("字体大小（TUI 模式下为逻辑档位，终端实际字号由终端软件控制）"),
                    Horizontal(
                        Button("小", id="fs-small"),
                        Button("中", id="fs-medium", variant="primary"),
                        Button("大", id="fs-large"),
                        classes="btns",
                    ),
                    Label("提示：按 Ctrl+C 或关闭窗口退出"),
                    Button("关闭", id="close", variant="default"),
                    classes="dlg",
                )

            def on_button_pressed(self, ev):
                if ev.button.id and ev.button.id.startswith("fs-"):
                    size = ev.button.id[3:]
                    # 写回父级字号档位（UI 上实际无法放大终端字体，仅记录状态）
                    self.notify(f"字体档位：{size}（实际字号由终端控制）")
                elif ev.button.id == "close":
                    self.dismiss(None)

        self.push_screen(SettingsScreen())

    @on(RadioSet.Changed, "#display-modes")
    def _on_display_mode_changed(self, event: RadioSet.Changed) -> None:
        pressed = event.pressed
        if pressed is None:
            return
        mode = pressed.name or "host"
        self.display_mode = mode
        logger.info(f"Display mode -> {mode}")
        self._fire("display_mode_change", mode)

    @on(Tree.NodeSelected, "#archive-tree")
    def _on_archive_dbl(self, event: Tree.NodeSelected) -> None:
        data = event.node.data
        if data and self._current_zip_path:
            self._fire(
                "archive_action",
                {
                    "action": "open",
                    "zip_path": self._current_zip_path,
                    "file_in_zip": data,
                },
            )

    # ------------------------ Internal helpers ------------------------ #

    def _on_program_selected(self, program_name: str) -> None:
        logger.info(f"Executing program from menu: {program_name}")
        self._append_history_ui(f"正在执行: {program_name}", "system_message", None)
        self._fire("execute_program", program_name)

    # 命令行式操作：以 / 开头为命令，否则作为普通对话发送
    _COMMAND_HELP: list[tuple[str, str]] = [
        ("/help", "显示本帮助"),
        ("/screenshot", "截屏并保存到临时文件"),
        ("/click <x>,<y>", "在屏幕坐标 (x,y) 处左键点击"),
        ("/left_click", "在当前鼠标位置左键点击"),
        ("/type <text>", "将 text 作为键盘输入写出"),
        ("/voice", "切换语音聆听开关"),
        ("/clear", "清空输出区"),
        ("/restart", "重启应用"),
        ("/mode host|usb|both", "切换显示模式"),
        ("/program <name>", "执行程序列表中的程序"),
        ("/search <keyword>", "在程序列表中过滤关键字"),
        ("/exit", "退出 TUI"),
        ("(其他文本)", "作为对话命令发送给 Jarvis"),
    ]

    def _send_text_command(self, raw_text: str) -> None:
        cmd = (raw_text or "").strip()
        if not cmd:
            return
        inp = self.query_one("#command-input", Input)
        self._append_history_ui(f"你: {cmd}", "user_prompt", None)

        # 命令行式操作：以 / 开头
        if cmd.startswith("/"):
            if self._dispatch_slash_command(cmd):
                inp.value = ""
                return
            self._append_history_ui(
                f"未知命令: {cmd}（输入 /help 查看可用命令）", "error", None
            )
            inp.value = ""
            return

        # 普通对话
        logger.info(f"Sending text command: {cmd}")
        self._fire("text", cmd)
        inp.value = ""

    def _dispatch_slash_command(self, cmd: str) -> bool:
        """解析并执行 / 命令。返回 True 表示已识别处理。"""
        parts = cmd[1:].split(None, 1)
        if not parts:
            return False
        name = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if name in ("help", "h", "?"):
            self._show_help()
            return True
        if name in ("screenshot", "scr", "shot"):
            self._fire("manual_action", {"action": "screenshot"})
            return True
        if name == "click" and arg:
            try:
                x_s, y_s = [p.strip() for p in arg.split(",")]
                coord = (int(float(x_s)), int(float(y_s)))
                self._fire("manual_action", {"action": "left_click", "coordinate": coord})
                return True
            except Exception:
                self._append_history_ui(
                    "用法: /click <x>,<y>  例: /click 100,200", "error", None
                )
                return True
        if name == "left_click":
            self._fire("manual_action", {"action": "left_click"})
            return True
        if name == "type" and arg:
            self._fire("manual_action", {"action": "type", "text": arg})
            return True
        if name in ("voice", "listen"):
            self._fire("voice", None)
            return True
        if name == "clear":
            self._clear_history_ui()
            return True
        if name == "restart":
            self.restart_application()
            return True
        if name == "mode" and arg:
            mode = arg.lower()
            if mode in DISPLAY_MODES:
                self.display_mode = mode
                self._update_display_mode_buttons()
                self._fire("display_mode_change", mode)
                self._append_history_ui(
                    f"显示模式已切换: {DISPLAY_MODE_LABELS[mode]}", "system_message", None
                )
                return True
            self._append_history_ui(
                f"无效模式: {arg}（可选: host/usb/both）", "error", None
            )
            return True
        if name == "program" and arg:
            self._on_program_selected(arg)
            return True
        if name in ("search", "filter") and arg is not None:
            search_input = self.query_one("#program-search", Input)
            search_input.value = arg
            lv = self.query_one("#program-list", ProgramList)
            lv.filter(arg)
            self._append_history_ui(
                f"已过滤程序列表: '{arg}'", "system_message", None
            )
            return True
        if name in ("exit", "quit", "q"):
            self.exit()
            return True
        return False

    def _show_help(self) -> None:
        lines = ["可用命令（以 / 开头，区分大小写不敏感）："]
        for c, desc in self._COMMAND_HELP:
            lines.append(f"  {c:<22} {desc}")
        self._append_history_ui("\n".join(lines), "system_message", None)

    def _manual_action(self, action_type: str) -> None:
        if action_type == "type":
            # 已经由 btn-type 处理
            return
        self._fire("manual_action", {"action": action_type})

    def _fire(self, command_type: str, payload: Any) -> None:
        if self.command_callback:
            try:
                self.command_callback(command_type, payload)
            except Exception:
                logger.exception(f"command_callback 失败: {command_type}")

    # ------------------------ EventBus -> Queue bridges ------------------------ #

    def _queue_ui_output(self, message, tag, response_id):
        self.msg_queue.put(("ui_output", (message, tag, response_id)))

    def _queue_voice_status(self, is_listening):
        self.msg_queue.put(("voice_status", is_listening))

    def _queue_link_status(self, connected, device):
        self.msg_queue.put(("link_status", (connected, device)))

    def _queue_screenshot_update(self, b64_data):
        self.msg_queue.put(("screenshot_update", b64_data))

    def _queue_archive_update(self, zip_path, contents):
        self.msg_queue.put(("archive_browser_update", (zip_path, contents)))

    def _queue_nostalgia(self):
        self.msg_queue.put(("nostalgia_ui", None))
