# -*- coding: utf-8 -*-
"""Butler TUI 主入口 - 启动完整的终端用户界面."""

import sys
import os
import time
import threading
import logging
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

lib_path = project_root / "lib_external"
if lib_path.exists():
    import site
    site.addsitedir(str(lib_path))

from textual.app import App
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header, Footer, Input, Button, Label, ListView, ListItem,
    Tab, Tabs, Tree, DataTable, Static, RadioButton, RadioSet,
    Select, Switch, ProgressBar,
)
from textual.widgets.tree import TreeNode
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from textual import on, work
from rich.markdown import Markdown as RichMarkdown

from butler.core.environment import run_preflight_check
from butler.core.event_bus import event_bus

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("ButlerTUI")


class ButlerTUI(App):
    """Butler 完整终端用户界面."""

    CSS = """
    Screen {
        background: $panel;
        color: $text;
    }
    #sidebar {
        width: 24;
        background: $surface;
        border-right: solid $primary 50%;
        padding: 1 0;
    }
    #sidebar-label {
        height: 2;
        padding: 0 1;
        color: $accent;
        text-style: bold;
    }
    #nav-list {
        height: 1fr;
        border: none;
        padding: 0 1;
    }
    #main-area {
        width: 1fr;
    }
    #chat-header {
        height: auto;
        padding: 0 1;
        border-bottom: solid $primary 50%;
    }
    #chat-output {
        height: 1fr;
        padding: 1;
        border: solid $primary 50%;
        background: $surface;
    }
    #chat-input-bar {
        height: auto;
        padding: 1;
        border-top: solid $primary 50%;
    }
    #chat-input {
        width: 1fr;
    }
    #cmd-hints {
        height: auto;
        max-height: 10;
        padding: 0 1;
        background: $surface-darken-2;
        border-top: solid $accent 40%;
        display: none;
    }
    .hint-line {
        height: 1;
        padding: 0 1;
    }
    .hint-name {
        color: $accent;
        text-style: bold;
    }
    .hint-desc {
        color: $text-muted;
    }
    .hint-usage {
        color: $success;
    }
    .hint-line.hint-selected {
        background: $accent 30%;
        text-style: bold;
    }
    #status-bar {
        height: auto;
        padding: 0 1;
        background: $surface-darken-1;
        border-top: solid $primary 40%;
    }
    .nav-item {
        padding: 0 2;
    }
    .nav-item.active {
        background: $primary;
        color: $text;
    }
    .tool-section {
        padding: 1;
    }
    .tool-section-title {
        color: $accent;
        text-style: bold;
        padding: 0 1;
    }
    .tool-row {
        height: auto;
        padding: 0 1;
    }
    .tool-label {
        width: 15;
    }
    .tool-input {
        width: 1fr;
    }
    .execute-btn {
        width: 12;
    }
    .status-ok {
        color: $success;
    }
    .status-warn {
        color: $warning;
    }
    .status-err {
        color: $error;
    }
    """

    # Reactive state
    current_view = reactive("chat")
    status_message = reactive("就绪")

    def __init__(self):
        super().__init__()
        self.jarvis = None
        self.command_callback = None
        self._msg_queue = []
        self._queue_lock = threading.Lock()
        self._stop_event = threading.Event()
        # 实时命令建议状态
        self._hint_results: list = []
        self._hint_index = -1
        self._nav_items = [
            ("💬 对话", "chat"),
            ("📊 仪表板", "dashboard"),
            ("🔧 工具箱", "tools"),
            ("🧠 记忆", "memory"),
            ("📋 任务", "tasks"),
            ("🛠️ 技能", "skills"),
            ("📦 包管理", "packages"),
            ("🤖 员工", "agents"),
            ("⏰ 时光机", "timemachine"),
            ("⚙️ 设置", "settings"),
        ]

    def compose(self):
        yield Header(show_clock=True)

        with Horizontal():
            # Sidebar
            with Vertical(id="sidebar"):
                yield Label("Butler v2.0", id="sidebar-label")
                nav_list = ListView(id="nav-list")
                for icon_name, key in self._nav_items:
                    li = ListItem(Label(icon_name, markup=False))
                    li.nav_key = key
                    nav_list.append(li)
                yield nav_list

                # Status mini-panel
                yield Static("", id="status-mini")

            # Main area
            with Vertical(id="main-area"):
                # Chat view (default)
                with Vertical(id="view-chat"):
                    with Horizontal(id="chat-header"):
                        yield Label("💬 Butler 对话", id="chat-title")
                        yield Static("", id="chat-status")

                    yield VerticalScroll(id="chat-output")

                    # 实时命令建议面板 (输入 / 时显示)
                    yield Vertical(id="cmd-hints")

                    with Horizontal(id="chat-input-bar"):
                        yield Input(
                            placeholder="输入命令或对话... (/help 帮助, /howto 意图搜索, /commands 浏览)",
                            id="chat-input",
                        )
                        yield Button("发送", id="btn-send", variant="success")
                        yield Button("清空", id="btn-clear", variant="default")

                # Dashboard view
                with Vertical(id="view-dashboard", visible=False):
                    yield Label("📊 系统仪表板", classes="tool-section-title")
                    with Horizontal():
                        yield Static("", id="dash-system")
                        yield Static("", id="dash-memory")
                    yield Label("📋 最近任务", classes="tool-section-title")
                    yield DataTable(id="dash-tasks-table")

                # Tools view
                with Vertical(id="view-tools", visible=False):
                    yield Label("🔧 Butler 工具箱", classes="tool-section-title")
                    yield Tabs(
                        Tab("🌐 网络", id="tools-network"),
                        Tab("🔐 安全", id="tools-security"),
                        Tab("📄 文档", id="tools-doc"),
                        Tab("⚙️ 系统", id="tools-system"),
                        Tab("🧰 技能", id="tools-skills"),
                    )
                    yield VerticalScroll(id="tools-content")

                # Memory view
                with Vertical(id="view-memory", visible=False):
                    yield Label("🧠 Butler 记忆库", classes="tool-section-title")
                    yield Tabs(
                        Tab("📝 备忘录", id="memos-tab"),
                        Tab("📚 长期记忆", id="long-mem-tab"),
                        Tab("💭 最近对话", id="recent-tab"),
                    )
                    yield VerticalScroll(id="memory-content")

                # Tasks view
                with Vertical(id="view-tasks", visible=False):
                    yield Label("📋 任务看板", classes="tool-section-title")
                    with Horizontal():
                        yield Button("➕ 新建任务", id="btn-new-task", variant="primary")
                        yield Button("🔄 刷新", id="btn-refresh-tasks")
                    yield DataTable(id="tasks-table")

                # Skills view
                with Vertical(id="view-skills", visible=False):
                    yield Label("🛠️ 技能管理", classes="tool-section-title")
                    with Horizontal():
                        yield Button("🔄 刷新技能", id="btn-refresh-skills")
                        yield Input(placeholder="搜索技能...", id="skill-search")
                    yield Tree("技能列表", id="skills-tree")

                # Packages view
                with Vertical(id="view-packages", visible=False):
                    yield Label("📦 包管理", classes="tool-section-title")
                    with Horizontal():
                        yield Button("📋 列出包", id="btn-list-pkgs")
                        yield Input(placeholder="包路径 (安装用)", id="pkg-path")
                        yield Button("📥 安装", id="btn-install-pkg", variant="primary")
                    yield DataTable(id="pkgs-table")

                # Agents view
                with Vertical(id="view-agents", visible=False):
                    yield Label("🤖 数字员工管理", classes="tool-section-title")
                    with Horizontal():
                        yield Button("🔄 刷新员工", id="btn-refresh-agents")
                    yield Tree("员工列表", id="agents-tree")
                    with Horizontal():
                        yield Input(placeholder="员工角色", id="agent-role")
                        yield Input(placeholder="委派任务描述", id="agent-task")
                        yield Button("▶️ 执行任务", id="btn-run-agent", variant="primary")

                # TimeMachine view
                with Vertical(id="view-timemachine", visible=False):
                    yield Label("⏰ 时光机", classes="tool-section-title")
                    with Horizontal():
                        yield Button("🔄 刷新快照", id="btn-refresh-tm")
                        yield Select([], id="tm-category")
                    yield DataTable(id="tm-table")

                # Settings view
                with Vertical(id="view-settings", visible=False):
                    yield Label("⚙️ Butler 设置", classes="tool-section-title")
                    yield Tabs(
                        Tab("🎨 主题", id="tab-theme"),
                        Tab("🔑 API 配置", id="tab-api"),
                        Tab("🔊 语音", id="tab-voice"),
                        Tab("💾 存储", id="tab-storage"),
                    )
                    yield VerticalScroll(id="settings-content")

        # Status bar
        with Horizontal(id="status-bar"):
            yield Static("● 就绪", id="status-text")
            yield Static("", id="status-right")

        yield Footer()

    def on_mount(self):
        self.set_interval(0.05, self._drain_queue)
        self._update_status("初始化中...")
        self._set_view("chat")
        self._init_chat_output()
        self._init_tools_view()
        self._init_dashboard()
        self._init_memory_view()
        self._init_tasks_view()
        self._init_skills_view()
        self._init_packages_view()
        self._init_agents_view()
        self._init_timemachine_view()
        self._init_settings_view()
        self._update_status("Butler TUI 就绪")

    # ------------------------ View Management ------------------------ #

    def _set_view(self, view_key: str):
        self.current_view = view_key
        for view_id in [
            "view-chat", "view-dashboard", "view-tools",
            "view-memory", "view-tasks", "view-skills",
            "view-packages", "view-agents", "view-timemachine", "view-settings"
        ]:
            v = self.query_existing(f"#{view_id}")
            if v:
                v.display = view_id == f"view-{view_key}"
        # Update nav highlight
        nav = self.query_existing("#nav-list", ListView)
        if nav:
            for i, (_, key) in enumerate(self._nav_items):
                li = nav.get_child_at(i)
                if li:
                    if key == view_key:
                        li.add_class("active")
                    else:
                        li.remove_class("active")

    @on(ListView.Selected, "#nav-list")
    def _on_nav_selected(self, event):
        li = event.item
        key = getattr(li, "nav_key", None)
        if key:
            self._set_view(key)

    # ------------------------ Chat ------------------------ #

    def _init_chat_output(self):
        output = self.query_existing("#chat-output", VerticalScroll)
        if output:
            output.mount(Label(""))
        self._append_chat("🎯 Butler AI 助手 v2.0 已就绪", "system")
        self._append_chat("命令帮助:", "system")
        self._append_chat("  /help          查看所有命令分类概览", "system")
        self._append_chat("  /help <命令>   查看某命令的详细用法 (支持模糊匹配)", "system")
        self._append_chat("  /commands [词] 按分类浏览/过滤命令", "system")
        self._append_chat("  /howto <描述>  用自然语言描述你想做的事，推荐命令", "system")
        self._append_chat("  输入错了? 不确定命令名? 直接输入，Butler 会推荐相似命令。", "system")

    def _append_chat(self, text: str, tag: str = "normal"):
        color_map = {
            "user": "#00ffff",
            "ai": "#d4d4d4",
            "system": "#888888",
            "error": "#ff4444",
            "ok": "#44ff44",
            "normal": "#cccccc",
        }
        color = color_map.get(tag, "#cccccc")

        output = self.query_existing("#chat-output", VerticalScroll)
        if output:
            prefix = ""
            if tag == "user":
                prefix = "[bold cyan]你:[/bold cyan] "
            elif tag == "ai":
                prefix = "[bold yellow]Butler:[/bold yellow] "
            elif tag == "system":
                prefix = "[dim]ⓘ [/dim]"
            elif tag == "error":
                prefix = "[bold red]✖ [/bold red]"
            elif tag == "ok":
                prefix = "[bold green]✔ [/bold green]"

            try:
                label = Label(f"[{color}]{prefix}{text}[/{color}]")
                output.mount(label)
            except Exception:
                label = Label(f"{prefix}{text}")
                output.mount(label)

    @on(Input.Submitted, "#chat-input")
    def _on_chat_submit(self, event):
        text = event.value.strip()
        if not text:
            return
        self._hide_hints()
        self._handle_chat_input(text)
        event.input.value = ""

    @on(Input.Changed, "#chat-input")
    def _on_input_changed(self, event: Input.Changed):
        """实时命令建议 - 输入 / 时即时显示匹配的命令."""
        text = event.value
        # 非命令输入，隐藏建议
        if not text.startswith("/"):
            self._hide_hints()
            return
        # 已输入空格表示命令名已完成，进入参数阶段，不再建议
        cmd_part = text[1:]
        if " " in cmd_part:
            self._hide_hints()
            return
        cmd_part = cmd_part.strip()

        from butler.tui.command_catalog import find_command
        results = find_command(cmd_part, limit=8)
        if results:
            self._hint_results = [c for c, _ in results]
            self._hint_index = 0
            self._render_hints()
        else:
            self._hide_hints()

    def _render_hints(self):
        """渲染命令建议列表到 #cmd-hints 面板."""
        panel = self.query_existing("#cmd-hints", Vertical)
        if not panel:
            return
        # 清除旧条目
        for child in list(panel.children):
            child.remove()
        # 挂载新条目
        lines = []
        for i, cmd in enumerate(self._hint_results):
            selected = (i == self._hint_index)
            marker = "▶ " if selected else "  "
            lines.append(Static(
                f"{marker}[bold]/{cmd.name:<14}[/bold] [dim]{cmd.description}[/dim]  [green]{cmd.usage}[/green]",
                classes="hint-line" + (" hint-selected" if selected else ""),
            ))
        if lines:
            panel.mount(*lines)
        panel.display = True

    def _hide_hints(self):
        """隐藏命令建议面板."""
        panel = self.query_existing("#cmd-hints", Vertical)
        if panel:
            panel.display = False
            for child in list(panel.children):
                child.remove()
        self._hint_results = []
        self._hint_index = -1

    def _apply_hint(self, cmd):
        """应用选中的建议，填入输入框."""
        inp = self.query_existing("#chat-input", Input)
        if inp:
            inp.value = f"/{cmd.name} "
            inp.focus()
            try:
                inp.cursor_position = len(inp.value)
            except Exception:
                pass
        self._hide_hints()

    def on_key(self, event):
        """键盘导航: Up/Down 选择, Tab 应用, Esc 关闭."""
        panel = self.query_existing("#cmd-hints", Vertical)
        if not panel or not panel.display or not self._hint_results:
            return
        if event.key == "up":
            self._hint_index = (self._hint_index - 1) % len(self._hint_results)
            self._render_hints()
            event.stop()
        elif event.key == "down":
            self._hint_index = (self._hint_index + 1) % len(self._hint_results)
            self._render_hints()
            event.stop()
        elif event.key == "tab":
            if 0 <= self._hint_index < len(self._hint_results):
                self._apply_hint(self._hint_results[self._hint_index])
                event.stop()
        elif event.key == "escape":
            self._hide_hints()
            event.stop()

    @on(Button.Pressed, "#btn-send")
    def _on_send_click(self, _event):
        inp = self.query_existing("#chat-input", Input)
        if inp:
            text = inp.value.strip()
            if text:
                self._handle_chat_input(text)
                inp.value = ""

    @on(Button.Pressed, "#btn-clear")
    def _on_clear_chat(self, _event):
        output = self.query_existing("#chat-output", VerticalScroll)
        if output:
            for child in list(output.children):
                child.remove()
        self._append_chat("对话已清空", "system")

    def _handle_chat_input(self, text: str):
        self._append_chat(text, "user")

        # Check if we have a pending tool waiting for input
        pending = self._pending_tool
        if pending:
            self._pending_tool = None
            self._update_status("就绪")
            # 获取预设参数 (如 action)
            preset = getattr(self, "_pending_tool_params", None) or {}
            # 解析多参数 | 分隔输入
            if "|" in text and pending.startswith("skill_"):
                parts = [p.strip() for p in text.split("|")]
                if pending == "skill_docx_create":
                    params = {"action": "create", "output": parts[0] if len(parts) > 0 else "",
                              "title": parts[1] if len(parts) > 1 else "",
                              "content": parts[2] if len(parts) > 2 else ""}
                elif pending == "skill_pdf_merge":
                    params = {"action": "merge", "files": parts[0] if parts else "",
                              "output": parts[1] if len(parts) > 1 else ""}
                elif pending == "skill_format_convert":
                    params = {"action": "run", "input": parts[0] if parts else "",
                              "to_fmt": parts[1] if len(parts) > 1 else "docx"}
                elif pending == "skill_archive_compress":
                    params = {"action": "compress", "archive_path": parts[0] if parts else "",
                              "targets": parts[1] if len(parts) > 1 else "",
                              "password": parts[2] if len(parts) > 2 else ""}
                elif pending == "skill_archive_extract":
                    params = {"action": "extract", "archive_path": parts[0] if parts else "",
                              "output_dir": parts[1] if len(parts) > 1 else "",
                              "password": parts[2] if len(parts) > 2 else ""}
                elif pending == "skill_web_sec_test":
                    params = {"action": "test", "target": parts[0] if parts else "",
                              "mode": parts[1] if len(parts) > 1 else "full"}
                else:
                    params = self._parse_tool_input(pending, text)
                    params.update(preset)
            else:
                # 单参数输入
                params = self._parse_tool_input(pending, text)
                params.update(preset)
            self._pending_tool_params = {}
            self._execute_tool(pending, params)
            return

        if text.startswith("/"):
            # Check if it's a tool command first
            tool_handled = self._try_tool_command(text)
            if not tool_handled:
                self._handle_slash_command(text)
            return

        # Send to Jarvis if available
        if self.command_callback:
            try:
                self.command_callback("text", text)
            except Exception as e:
                self._append_chat(f"错误: {e}", "error")
        else:
            # Demo mode: simulate response
            self._simulate_jarvis_response(text)

    def _try_tool_command(self, text: str) -> bool:
        """尝试将命令解析为工具调用."""
        parts = text[1:].split(None, 1)
        if not parts:
            return False
        name = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        # Tool command mapping
        tool_map = {
            "crawl_url": ("crawl_url", lambda a: {"url": a}),
            "crawl_query": ("crawl_query", lambda a: {"query": a}),
            "email_send": ("email", lambda a: self._parse_email_input(a, "send")),
            "email_recv": ("email", lambda a: {"action": "receive"}),
            "img_search": ("img_search", lambda a: {"query": a}),
            "img_local": ("img_local", lambda a: {"path": a}),
            "weather": ("weather", lambda a: {"city": a}),
            "translate": ("translate", lambda a: {"text": a}),
            "translate_file": ("translate_file", lambda a: {"path": a}),
            "translate_url": ("translate_url", lambda a: {"url": a}),
            "encrypt": ("encrypt", lambda a: {"path": a}),
            "decrypt": ("decrypt", lambda a: {"path": a}),
            "audit_security": ("audit_security", lambda a: {}),
            "audit_dir": ("audit_dir", lambda a: {"path": a}),
            "convert": ("convert", lambda a: self._parse_convert_input(a)),
            "file_create": ("file", lambda a: self._parse_file_input(a, "create")),
            "file_read": ("file", lambda a: {"op": "read", "path": a}),
            "file_delete": ("file", lambda a: {"op": "delete", "path": a}),
            "file_list": ("file", lambda a: {"op": "list", "path": a}),
            "monitor": ("monitor", lambda a: {}),
            "dep_install": ("dependency", lambda a: {"op": "install", "package": a} if a else {"op": "install"}),
            "dep_all": ("dependency", lambda a: {"op": "install_all"}),
            "dep_setup": ("dependency", lambda a: {"op": "setup_runtime"}),
            "doctor": ("doctor", lambda a: {}),
            "skills_list": ("skills_list", lambda a: {}),
            "skills_find": ("skills_list", lambda a: {}),
            # ── 技能命令 (无 AI 可用) ──
            "markitdown": ("skill_markitdown", lambda a: {"path": a}),
            "docx_read": ("skill_docx", lambda a: {"action": "read", "file_path": a}),
            "docx_create": ("skill_docx", lambda a: self._parse_pipe_input(a, ["output", "title", "content"], {"action": "create"})),
            "pdf_extract": ("skill_pdf", lambda a: {"action": "extract_text", "file_path": a}),
            "pdf_merge": ("skill_pdf", lambda a: self._parse_pipe_input(a, ["files", "output"], {"action": "merge"})),
            "pdf_split": ("skill_pdf", lambda a: {"action": "split", "file_path": a}),
            "archive_compress": ("skill_archive", lambda a: self._parse_pipe_input(a, ["archive_path", "targets", "password"], {"action": "compress"})),
            "archive_extract": ("skill_archive", lambda a: self._parse_pipe_input(a, ["archive_path", "output_dir", "password"], {"action": "extract"})),
            "archive_list": ("skill_archive", lambda a: {"action": "list_contents", "archive_path": a}),
            "uninstaller": ("skill_uninstaller", lambda a: self._parse_skill_action(a, "list")),
            "sys_clean": ("skill_sys_clean", lambda a: self._parse_skill_action(a, "help")),
            "media_scan": ("skill_media_scan", lambda a: {}),
            "storage_hub": ("skill_storage_hub", lambda a: self._parse_skill_action(a, "list")),
            "clip_magic": ("skill_clip_magic", lambda a: {}),
            "sec_scan": ("skill_sec_scan", lambda a: {"target": a}),
            "web_sec_test": ("skill_web_sec_test", lambda a: self._parse_pipe_input(a, ["target", "mode"], {"action": "test"})),
            "format_convert": ("skill_format_convert", lambda a: self._parse_pipe_input(a, ["input", "to_fmt"], {"action": "run"})),
            # ── 技能控制命令 ──
            "skill_stop": ("skill_stop", lambda a: {"skill": a}),
            "skill_status": ("skill_status", lambda a: {"skill": a}),
            "clip_history": ("skill_clip_history", lambda a: {}),
            "uninstall_scan": ("skill_uninstall_scan", lambda a: {"name": a}),
            "uninstall_do": ("skill_uninstall_do", lambda a: self._parse_pipe_input(a, ["name", "dry_run"], {})),
            "junk_scan": ("skill_junk_scan", lambda a: self._parse_skill_action(a, "scan")),
            "junk_clean": ("skill_junk_clean", lambda a: self._parse_pipe_input(a, ["dry_run"], {})),
            "sys_info": ("skill_sys_info", lambda a: {}),
            "top_procs": ("skill_top_procs", lambda a: self._parse_pipe_input(a, ["sort_by"], {})),
            "cloud_list": ("skill_cloud_list", lambda a: self._parse_pipe_input(a, ["drive", "path"], {})),
            "cloud_search": ("skill_cloud_search", lambda a: {"query": a}),
            "cloud_transfer": ("skill_cloud_transfer", lambda a: self._parse_pipe_input(a, ["src_drive", "dst_drive", "file_name", "source_path", "dst_path"], {})),
            "cloud_status": ("skill_cloud_status", lambda a: {"task_id": a}),
            "cloud_duplicates": ("skill_cloud_duplicates", lambda a: {}),
            "track_start": ("skill_track_start", lambda a: {}),
            "track_stop": ("skill_track_stop", lambda a: {}),
            "track_clean": ("skill_track_clean", lambda a: {}),
        }

        if name in tool_map:
            tool_name, parser = tool_map[name]
            params = parser(arg)
            self._execute_tool(tool_name, params)
            return True
        return False

    def _parse_tool_input(self, tool_name: str, text: str) -> dict:
        """解析用户对 pending tool 的输入."""
        if tool_name in ("crawl_url",):
            return {"url": text}
        elif tool_name in ("img_search",):
            return {"query": text}
        elif tool_name in ("img_local",):
            return {"path": text}
        elif tool_name in ("weather",):
            return {"city": text}
        elif tool_name in ("encrypt", "decrypt", "audit_dir"):
            return {"path": text}
        elif tool_name in ("translate",):
            return {"text": text}
        elif tool_name == "email":
            return self._parse_email_input(text, "send")
        elif tool_name == "convert":
            return self._parse_convert_input(text)
        elif tool_name == "file":
            return self._parse_file_input(text, "list")
        elif tool_name == "dependency":
            parts = text.split(None, 1)
            op = parts[0] if parts else "install"
            pkg = parts[1] if len(parts) > 1 else ""
            return {"op": op, "package": pkg}
        return {}

    def _parse_email_input(self, text: str, action: str) -> dict:
        """解析邮件输入 (格式: to | subject | body)."""
        parts = [p.strip() for p in text.split("|")]
        result = {"action": action}
        if len(parts) >= 1:
            result["to"] = parts[0]
        if len(parts) >= 2:
            result["subject"] = parts[1]
        if len(parts) >= 3:
            result["body"] = parts[2]
        return result

    def _parse_convert_input(self, text: str) -> dict:
        """解析转换输入 (格式: input -> output 或 input output)."""
        if "->" in text:
            parts = [p.strip() for p in text.split("->", 1)]
        else:
            parts = text.split(None, 1)
        return {"input": parts[0] if len(parts) > 0 else "", "output": parts[1] if len(parts) > 1 else ""}

    def _parse_file_input(self, text: str, default_op: str) -> dict:
        """解析文件输入 (格式: operation | path [| content])."""
        parts = [p.strip() for p in text.split("|")]
        op = parts[0] if parts else default_op
        path = parts[1] if len(parts) > 1 else ""
        content = parts[2] if len(parts) > 2 else ""
        return {"op": op, "path": path, "content": content}

    def _parse_pipe_input(self, text: str, keys: list, base: dict) -> dict:
        """用 | 分隔参数，按 keys 顺序映射到 dict (合并 base)."""
        result = dict(base)
        if not text:
            return result
        parts = [p.strip() for p in text.split("|")]
        for i, key in enumerate(keys):
            if i < len(parts) and parts[i]:
                result[key] = parts[i]
        return result

    def _parse_skill_action(self, text: str, default_action: str) -> dict:
        """解析技能的 action 参数 (格式: action | arg1 | arg2)."""
        if not text:
            return {"action": default_action}
        parts = [p.strip() for p in text.split("|")]
        result = {"action": parts[0] if parts else default_action}
        for i, part in enumerate(parts[1:], 1):
            result[f"arg{i}"] = part
        return result

    def _handle_slash_command(self, cmd: str):
        parts = cmd[1:].split(None, 1)
        if not parts:
            return
        name = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        from butler.tui.command_catalog import get_command, suggest_for_unknown, format_command_help, format_command_overview, find_by_intent

        # ── 特殊元命令 (不注册在目录里) ──
        if name in ("help", "h", "?", "帮助", "bz"):
            if arg:
                # /help <命令名> → 详细帮助
                entry = get_command(arg)
                if entry:
                    self._append_chat(format_command_help(entry), "system")
                else:
                    # 模糊搜索
                    suggestions = suggest_for_unknown(arg)
                    if suggestions:
                        lines = [f"未找到命令 '{arg}'，相似命令:"]
                        for s in suggestions:
                            lines.append(f"  /{s.name}  —  {s.description}")
                        lines.append(f"\n输入 /help <命令名> 查看详细用法")
                        self._append_chat("\n".join(lines), "system")
                    else:
                        self._append_chat(f"未找到命令 '{arg}'，输入 /commands 浏览所有命令", "error")
            else:
                self._append_chat(format_command_overview(), "system")
            return

        if name in ("commands", "cmd", "命令列表", "所有命令", "allcmd"):
            self._append_chat(format_command_overview(arg), "system")
            return

        if name in ("howto", "how", "怎么做", "如何", "怎么"):
            if not arg:
                self._append_chat("用法: /howto <你想做什么>\n示例: /howto 我想加密一个文件", "system")
                return
            results = find_by_intent(arg, limit=3)
            if results:
                lines = [f"根据「{arg}」，推荐以下命令:"]
                for cmd_entry, score in results:
                    stars = "★" * max(1, int(score * 5))
                    lines.append(f"  [cyan]/{cmd_entry.name}[/cyan]  {cmd_entry.description}  {stars}")
                    lines.append(f"    用法: {cmd_entry.usage}")
                lines.append(f"\n输入 /help <命令名> 查看详细用法")
                self._append_chat("\n".join(lines), "system")
            else:
                self._append_chat(f"没有找到匹配「{arg}」的命令，试试 /commands 浏览所有命令", "error")
            return

        # ── 在目录中查找命令 ──
        entry = get_command(name)
        if entry:
            self._dispatch_catalog_command(entry, arg)
        else:
            # 未知命令 → "你是想说?" 建议
            suggestions = suggest_for_unknown(name)
            if suggestions:
                lines = [f"未知命令: /{name}"]
                lines.append(f"你是想说?")
                for s in suggestions:
                    lines.append(f"  [cyan]/{s.name}[/cyan]  —  {s.description}")
                lines.append(f"\n输入 /commands 浏览所有命令，或 /howto <描述> 按意图搜索")
                self._append_chat("\n".join(lines), "error")
            else:
                self._append_chat(
                    f"未知命令: /{name}\n输入 /help 查看命令列表，/commands 浏览分类，或 /howto <你想做什么> 按意图搜索",
                    "error"
                )

    def _dispatch_catalog_command(self, entry, arg: str):
        """根据目录条目分发命令执行."""
        from butler.tui.command_catalog import CommandEntry
        name = entry.name

        # ── 无参数命令，缺少参数时提示 ──
        if name == "weather":
            self._tool_weather(arg or "北京")
        elif name == "encrypt":
            if arg:
                self._tool_encrypt(arg)
            else:
                self._append_chat(f"用法: {entry.usage}\n示例: {entry.example}", "system")
        elif name == "decrypt":
            if arg:
                self._tool_decrypt(arg)
            else:
                self._append_chat(f"用法: {entry.usage}\n示例: {entry.example}", "system")
        elif name == "translate":
            if arg:
                self._tool_translate(arg)
            else:
                self._append_chat(f"用法: {entry.usage}\n示例: {entry.example}", "system")
        elif name == "performance":
            if arg:
                mode = arg.lower()
                if self.command_callback:
                    self.command_callback("text", f"/performance {mode}")
                self._append_chat(f"性能模式切换请求: {mode}", "system")
            else:
                self._append_chat(f"用法: /performance <high|eco|normal>\n{entry.detail}", "system")
        elif name == "focus":
            duration = int(arg) if arg else 25
            if self.command_callback:
                self.command_callback("text", f"/focus {duration}")
            self._append_chat(f"专注模式已启动 ({duration} 分钟)", "system")
        elif name == "focus-stop":
            if self.command_callback:
                self.command_callback("text", "/focus-stop")
            self._append_chat("专注模式已停止", "system")
        elif name == "dream":
            if self.command_callback:
                self.command_callback("text", "/dream")
            self._append_chat("正在启动做梦引擎...", "system")
        elif name == "clear":
            self._on_clear_chat(None)
        elif name == "status":
            self._show_status()
        elif name == "kairos":
            self._show_kairos()
        elif name == "tasks":
            self._set_view("tasks")
        elif name == "team":
            self._append_chat("团队成员列表 (需 Jarvis 运行时)", "system")
        elif name == "profile":
            self._append_chat("用户画像 (需 Jarvis 运行时)", "system")
        elif name == "memory":
            self._set_view("memory")
        elif name == "doctor":
            self._tool_doctor()
        elif name in ("exit", "quit", "q"):
            self.exit()
        else:
            # 工具类命令 → 走 _try_tool_command
            tool_handled = self._try_tool_command(f"/{name} {arg}".strip())
            if not tool_handled:
                self._append_chat(f"命令 /{name} 已注册但暂未实现 TUI 快捷调用，请使用 /help {name} 查看替代方式", "system")

    def _simulate_jarvis_response(self, text: str):
        self._append_chat(
            f"[演示模式] Butler 收到: '{text}'。\n"
            f"启动完整 Butler 运行时后将启用真实 AI 对话能力。",
            "ai"
        )

    def _show_status(self):
        status = (
            "📊 Butler 系统状态:\n"
            f"  - UI 模式: TUI (终端)\n"
            f"  - 运行时: {'已连接' if self.jarvis else '未连接'}\n"
            f"  - 当前视图: {self.current_view}\n"
        )
        self._append_chat(status, "system")

    def _show_kairos(self):
        msg = "🌟 KAIROS 状态 (需要完整运行时):\n  - 性能模式: NORMAL\n  - 电池: --\n  - 节流: --\n  - 协作队友: --"
        self._append_chat(msg, "system")

    # ------------------------ Tools View ------------------------ #

    _current_tools_tab = "tools-network"

    def _init_tools_view(self):
        self._update_tools_content("tools-network")

    def _update_tools_content(self, tab_id: str):
        self._current_tools_tab = tab_id
        content = self.query_existing("#tools-content", VerticalScroll)
        if not content:
            return
        for child in list(content.children):
            child.remove()

        form_html = self._build_tools_form(tab_id)
        content.mount(Label(form_html))

        # Add interactive buttons for the active tab
        self._mount_tool_buttons(content, tab_id)

    def _build_tools_form(self, tab_id: str) -> str:
        if tab_id == "tools-network":
            return (
                "[bold cyan]🌐 网络工具[/bold cyan]\n\n"
                "[bold]爬虫:[/bold]\n"
                "  URL输入爬取:  /crawl_url <url>\n"
                "  关键词搜索爬取:  /crawl_query <keyword>\n\n"
                "[bold]邮件:[/bold]\n"
                "  发送邮件:  /email_send <to> <subject> <body>\n"
                "  接收邮件:  /email_recv\n\n"
                "[bold]图片搜索:[/bold]\n"
                "  关键词搜图:  /img_search <keyword>\n"
                "  本地图片识别:  /img_local <path>\n\n"
                "[bold]天气:[/bold]\n"
                "  查询天气:  /weather <city>\n\n"
                "[bold]翻译:[/bold]\n"
                "  翻译文本:  /translate <text>\n"
                "  翻译文件:  /translate_file <path>\n"
                "  翻译网页:  /translate_url <url>\n"
            )
        elif tab_id == "tools-security":
            return (
                "[bold yellow]🔐 安全工具[/bold yellow]\n\n"
                "[bold]文件加密:[/bold]\n"
                "  AES加密:  /encrypt <path>\n"
                "  AES解密:  /decrypt <path>\n\n"
                "[bold]安全审计:[/bold]\n"
                "  全面安全审计:  /audit_security\n"
                "  目录审计:  /audit_dir <path>\n"
            )
        elif tab_id == "tools-doc":
            return (
                "[bold green]📄 文档工具[/bold green]\n\n"
                "[bold]格式转换:[/bold]\n"
                "  文件转换:  /convert <input> <output>\n\n"
                "[bold]文件管理:[/bold]\n"
                "  创建文件:  /file_create <path> [content]\n"
                "  读取文件:  /file_read <path>\n"
                "  删除文件:  /file_delete <path>\n"
                "  列出目录:  /file_list <path>\n"
            )
        elif tab_id == "tools-system":
            return (
                "[bold magenta]⚙️ 系统工具[/bold magenta]\n\n"
                "[bold]系统监控:[/bold]\n"
                "  运行监控:  /monitor\n\n"
                "[bold]依赖管理:[/bold]\n"
                "  安装依赖:  /dep_install [package]\n"
                "  全量安装:  /dep_all\n\n"
                "[bold]系统诊断:[/bold]\n"
                "  一键诊断:  /doctor\n\n"
                "[bold]技能管理:[/bold]\n"
                "  列出技能:  /skills_list\n"
                "  查找技能:  /skills_find <keyword>\n"
            )
        elif tab_id == "tools-skills":
            return (
                "[bold cyan]🧰 技能工具箱 (无需 AI)[/bold cyan]\n\n"
                "[bold]文档处理:[/bold]\n"
                "  转 Markdown:  /markitdown <文件>\n"
                "  读 Word:      /docx_read <文件>\n"
                "  建 Word:      /docx_create <路径> | <标题> | <内容>\n"
                "  提取 PDF:     /pdf_extract <文件>\n"
                "  合并 PDF:     /pdf_merge <文件1,文件2> | <输出>\n"
                "  拆分 PDF:     /pdf_split <文件>\n"
                "  格式转换:     /format_convert <输入> | <格式>\n\n"
                "[bold]压缩归档:[/bold]\n"
                "  压缩:   /archive_compress <输出> | <目标> [| 密码]\n"
                "  解压:   /archive_extract <压缩包> [| 输出目录] [| 密码]\n"
                "  列出:   /archive_list <压缩包>\n\n"
                "[bold]系统管理:[/bold]\n"
                "  软件列表:    /uninstaller list\n"
                "  残留扫描:    /uninstall_scan <软件名>\n"
                "  深度卸载:    /uninstall_do <软件名> [| dry_run]\n"
                "  垃圾扫描:    /junk_scan\n"
                "  垃圾清理:    /junk_clean [| dry_run=false]\n"
                "  系统信息:    /sys_info\n"
                "  Top进程:     /top_procs [| cpu|memory]\n\n"
                "[bold]安装追踪 (3步流程):[/bold]\n"
                "  1.安装前:  /track_start\n"
                "  2.安装后:  /track_stop\n"
                "  3.清理:    /track_clean\n\n"
                "[bold]媒体与存储:[/bold]\n"
                "  媒体扫描:  /media_scan\n"
                "  云盘列表:  /storage_hub list\n"
                "  云盘文件:  /cloud_list <云盘ID> [| 路径]\n"
                "  云盘搜索:  /cloud_search <关键词>\n"
                "  跨盘传输:  /cloud_transfer <源> | <目标> | <文件名>\n"
                "  传输状态:  /cloud_status <任务ID>\n"
                "  查找重复:  /cloud_duplicates\n\n"
                "[bold]剪贴板服务:[/bold]\n"
                "  启动:    /clip_magic\n"
                "  停止:    /skill_stop clip_magic\n"
                "  状态:    /skill_status clip_magic\n"
                "  历史:    /clip_history\n\n"
                "[bold]安全测试:[/bold]\n"
                "  端口扫描:  /sec_scan <目标IP>\n"
                "  Web 测试:  /web_sec_test <URL> [| full]\n\n"
                "[bold]服务控制:[/bold]\n"
                "  停止技能:  /skill_stop <名称>\n"
                "  技能状态:  /skill_status [名称]\n"
            )
        return ""

    def _mount_tool_buttons(self, content, tab_id: str):
        """为当前工具分类挂载快捷执行按钮."""
        from textual.widgets import Button
        from textual.containers import Horizontal

        if tab_id == "tools-network":
            # URL crawl
            content.mount(Label("  快速操作:"))
            row1 = Horizontal()
            btn_crawl = Button("🌐 爬取网页", id="tool-crawl-url", variant="primary")
            btn_email = Button("📧 发邮件", id="tool-email-send", variant="success")
            btn_weather = Button("☀️ 天气", id="tool-weather", variant="warning")
            row1.mount(btn_crawl)
            row1.mount(btn_email)
            row1.mount(btn_weather)
            content.mount(row1)

            row2 = Horizontal()
            btn_translate = Button("🌐 翻译", id="tool-translate", variant="primary")
            btn_img = Button("🖼️ 搜图", id="tool-img-search", variant="success")
            row2.mount(btn_translate)
            row2.mount(btn_img)
            content.mount(row2)

        elif tab_id == "tools-security":
            row = Horizontal()
            btn_enc = Button("🔐 加密文件", id="tool-encrypt", variant="primary")
            btn_dec = Button("🔓 解密文件", id="tool-decrypt", variant="warning")
            btn_audit = Button("🛡️ 安全审计", id="tool-audit-security", variant="error")
            row.mount(btn_enc)
            row.mount(btn_dec)
            row.mount(btn_audit)
            content.mount(row)

        elif tab_id == "tools-doc":
            row = Horizontal()
            btn_conv = Button("🔄 格式转换", id="tool-convert", variant="primary")
            btn_file = Button("📁 文件管理", id="tool-file-mgr", variant="success")
            row.mount(btn_conv)
            row.mount(btn_file)
            content.mount(row)

        elif tab_id == "tools-system":
            row = Horizontal()
            btn_mon = Button("📊 系统监控", id="tool-monitor", variant="primary")
            btn_dep = Button("📦 依赖管理", id="tool-dependency", variant="success")
            btn_doc = Button("🔍 系统诊断", id="tool-doctor", variant="warning")
            btn_skills = Button("🛠️ 技能列表", id="tool-skills-list", variant="default")
            row.mount(btn_mon)
            row.mount(btn_dep)
            row.mount(btn_doc)
            row.mount(btn_skills)
            content.mount(row)

        elif tab_id == "tools-skills":
            content.mount(Label("  快速操作:"))

            # 文档处理行
            row1 = Horizontal()
            row1.mount(Button("📄 转 Markdown", id="skill-btn-markitdown", variant="primary"))
            row1.mount(Button("📝 读 Word", id="skill-btn-docx-read", variant="success"))
            row1.mount(Button("✍️ 建 Word", id="skill-btn-docx-create", variant="success"))
            content.mount(row1)

            row2 = Horizontal()
            row2.mount(Button("📑 提取 PDF", id="skill-btn-pdf-extract", variant="primary"))
            row2.mount(Button("🔗 合并 PDF", id="skill-btn-pdf-merge", variant="primary"))
            row2.mount(Button("✂️ 拆分 PDF", id="skill-btn-pdf-split", variant="primary"))
            content.mount(row2)

            row3 = Horizontal()
            row3.mount(Button("🔄 格式转换", id="skill-btn-format-convert", variant="success"))
            content.mount(row3)

            # 压缩归档行
            content.mount(Label("  压缩归档:"))
            row4 = Horizontal()
            row4.mount(Button("📦 压缩", id="skill-btn-archive-compress", variant="primary"))
            row4.mount(Button("📤 解压", id="skill-btn-archive-extract", variant="success"))
            row4.mount(Button("📋 列出内容", id="skill-btn-archive-list", variant="default"))
            content.mount(row4)

            # 系统管理行
            content.mount(Label("  系统管理:"))
            row5 = Horizontal()
            row5.mount(Button("📜 软件列表", id="skill-btn-uninstaller", variant="warning"))
            row5.mount(Button("🔍 残留扫描", id="skill-btn-uninstall-scan", variant="warning"))
            row5.mount(Button("🗑️ 深度卸载", id="skill-btn-uninstall-do", variant="error"))
            content.mount(row5)

            row5b = Horizontal()
            row5b.mount(Button("🧹 垃圾扫描", id="skill-btn-junk-scan", variant="warning"))
            row5b.mount(Button("🧽 垃圾清理", id="skill-btn-junk-clean", variant="error"))
            row5b.mount(Button("📊 系统信息", id="skill-btn-sys-info", variant="primary"))
            content.mount(row5b)

            row5c = Horizontal()
            row5c.mount(Button("📈 Top进程", id="skill-btn-top-procs", variant="primary"))
            row5c.mount(Button("🎵 媒体扫描", id="skill-btn-media-scan", variant="success"))
            content.mount(row5c)

            # 安装追踪行
            content.mount(Label("  安装追踪 (3步):"))
            row_track = Horizontal()
            row_track.mount(Button("1️⃣ 安装前快照", id="skill-btn-track-start", variant="default"))
            row_track.mount(Button("2️⃣ 安装后差异", id="skill-btn-track-stop", variant="default"))
            row_track.mount(Button("3️⃣ 执行清理", id="skill-btn-track-clean", variant="error"))
            content.mount(row_track)

            # 云盘操作行
            content.mount(Label("  云盘操作:"))
            row6 = Horizontal()
            row6.mount(Button("☁️ 云盘列表", id="skill-btn-storage-hub", variant="primary"))
            row6.mount(Button("📁 列出文件", id="skill-btn-cloud-list", variant="primary"))
            row6.mount(Button("🔍 搜索文件", id="skill-btn-cloud-search", variant="success"))
            content.mount(row6)

            row6b = Horizontal()
            row6b.mount(Button("📋 传输状态", id="skill-btn-cloud-status", variant="default"))
            row6b.mount(Button("🔁 查找重复", id="skill-btn-cloud-dup", variant="default"))
            content.mount(row6b)

            # 剪贴板服务行
            content.mount(Label("  剪贴板服务:"))
            row7 = Horizontal()
            row7.mount(Button("▶️ 启动", id="skill-btn-clip-magic", variant="success"))
            row7.mount(Button("⏹️ 停止", id="skill-btn-clip-stop", variant="error"))
            row7.mount(Button("📊 状态", id="skill-btn-clip-status", variant="primary"))
            row7.mount(Button("📋 历史", id="skill-btn-clip-history", variant="default"))
            content.mount(row7)

            # 安全测试行
            content.mount(Label("  安全测试:"))
            row8 = Horizontal()
            row8.mount(Button("🔍 端口扫描", id="skill-btn-sec-scan", variant="error"))
            row8.mount(Button("🛡️ Web 测试", id="skill-btn-web-sec", variant="error"))
            content.mount(row8)

            # 全局控制行
            content.mount(Label("  服务控制:"))
            row9 = Horizontal()
            row9.mount(Button("📊 全部状态", id="skill-btn-all-status", variant="primary"))
            content.mount(row9)

    @on(Tabs.TabActivated, "#view-tools Tabs")
    def _on_tools_tab_changed(self, event):
        if event.tab:
            self._update_tools_content(event.tab.id)

    # Tool button handlers
    @on(Button.Pressed, "#tool-crawl-url")
    def _on_tool_crawl(self, _event):
        self._append_chat("🌐 爬取工具: 请输入 URL", "system")
        # Prompt user in chat
        self._prompt_and_execute("crawl_url", "请输入要爬取的 URL:")

    @on(Button.Pressed, "#tool-email-send")
    def _on_tool_email(self, _event):
        self._prompt_and_execute("email", "请输入收件人、主题和正文 (格式: to | subject | body):")

    @on(Button.Pressed, "#tool-weather")
    def _on_tool_weather_btn(self, _event):
        self._prompt_and_execute("weather", "请输入城市名称:")

    @on(Button.Pressed, "#tool-translate")
    def _on_tool_translate_btn(self, _event):
        self._prompt_and_execute("translate", "请输入要翻译的文本:")

    @on(Button.Pressed, "#tool-img-search")
    def _on_tool_img_btn(self, _event):
        self._prompt_and_execute("img_search", "请输入图片搜索关键词:")

    @on(Button.Pressed, "#tool-encrypt")
    def _on_tool_encrypt_btn(self, _event):
        self._prompt_and_execute("encrypt", "请输入要加密的文件路径:")

    @on(Button.Pressed, "#tool-decrypt")
    def _on_tool_decrypt_btn(self, _event):
        self._prompt_and_execute("decrypt", "请输入要解密的文件路径:")

    @on(Button.Pressed, "#tool-audit-security")
    def _on_tool_audit_btn(self, _event):
        self._execute_tool("audit_security", {})

    @on(Button.Pressed, "#tool-convert")
    def _on_tool_convert_btn(self, _event):
        self._prompt_and_execute("convert", "请输入 输入文件路径 和 输出文件路径 (格式: input -> output):")

    @on(Button.Pressed, "#tool-file-mgr")
    def _on_tool_file_btn(self, _event):
        self._prompt_and_execute("file", "文件操作 (create/read/delete/list)，输入: operation | path [| content]:")

    @on(Button.Pressed, "#tool-monitor")
    def _on_tool_monitor_btn(self, _event):
        self._execute_tool("monitor", {})

    @on(Button.Pressed, "#tool-dependency")
    def _on_tool_dep_btn(self, _event):
        self._prompt_and_execute("dependency", "依赖管理 (install/all/setup)，输入: operation [| package]:")

    @on(Button.Pressed, "#tool-doctor")
    def _on_tool_doctor_btn(self, _event):
        self._execute_tool("doctor", {})

    @on(Button.Pressed, "#tool-skills-list")
    def _on_tool_skills_btn(self, _event):
        self._execute_tool("skills_list", {})

    # ── 技能按钮处理器 (无 AI 可用) ──
    @on(Button.Pressed, "#skill-btn-markitdown")
    def _on_skill_markitdown(self, _event):
        self._prompt_and_execute("skill_markitdown", "请输入要转换的文件路径:")

    @on(Button.Pressed, "#skill-btn-docx-read")
    def _on_skill_docx_read(self, _event):
        self._prompt_and_execute("skill_docx", "请输入 Word 文档路径:")
        self._pending_tool = "skill_docx"
        self._pending_tool_params = {"action": "read"}

    @on(Button.Pressed, "#skill-btn-docx-create")
    def _on_skill_docx_create(self, _event):
        self._append_chat("创建 Word 文档，请输入: 输出路径 | 标题 | 内容", "system")
        self._pending_tool = "skill_docx_create"

    @on(Button.Pressed, "#skill-btn-pdf-extract")
    def _on_skill_pdf_extract(self, _event):
        self._prompt_and_execute("skill_pdf", "请输入 PDF 文件路径:")
        self._pending_tool = "skill_pdf"
        self._pending_tool_params = {"action": "extract_text"}

    @on(Button.Pressed, "#skill-btn-pdf-merge")
    def _on_skill_pdf_merge(self, _event):
        self._append_chat("合并 PDF，请输入: 文件1,文件2,... | 输出路径", "system")
        self._pending_tool = "skill_pdf_merge"

    @on(Button.Pressed, "#skill-btn-pdf-split")
    def _on_skill_pdf_split(self, _event):
        self._prompt_and_execute("skill_pdf", "请输入要拆分的 PDF 文件路径:")
        self._pending_tool = "skill_pdf"
        self._pending_tool_params = {"action": "split"}

    @on(Button.Pressed, "#skill-btn-format-convert")
    def _on_skill_format_convert(self, _event):
        self._append_chat("格式转换，请输入: 输入文件 | 输出格式 (docx/epub/png/html)", "system")
        self._pending_tool = "skill_format_convert"

    @on(Button.Pressed, "#skill-btn-archive-compress")
    def _on_skill_archive_compress(self, _event):
        self._append_chat("压缩文件，请输入: 输出路径 | 目标路径 [| 密码]", "system")
        self._pending_tool = "skill_archive_compress"

    @on(Button.Pressed, "#skill-btn-archive-extract")
    def _on_skill_archive_extract(self, _event):
        self._append_chat("解压文件，请输入: 压缩包路径 [| 输出目录] [| 密码]", "system")
        self._pending_tool = "skill_archive_extract"

    @on(Button.Pressed, "#skill-btn-archive-list")
    def _on_skill_archive_list(self, _event):
        self._prompt_and_execute("skill_archive", "请输入压缩包路径:")
        self._pending_tool = "skill_archive"
        self._pending_tool_params = {"action": "list_contents"}

    @on(Button.Pressed, "#skill-btn-uninstaller")
    def _on_skill_uninstaller(self, _event):
        self._execute_tool("skill_uninstaller", {"action": "list"})

    @on(Button.Pressed, "#skill-btn-sys-clean")
    def _on_skill_sys_clean(self, _event):
        self._execute_tool("skill_sys_clean", {"action": "clean"})

    @on(Button.Pressed, "#skill-btn-media-scan")
    def _on_skill_media_scan(self, _event):
        self._execute_tool("skill_media_scan", {})

    @on(Button.Pressed, "#skill-btn-storage-hub")
    def _on_skill_storage_hub(self, _event):
        self._execute_tool("skill_storage_hub", {"action": "list"})

    @on(Button.Pressed, "#skill-btn-clip-magic")
    def _on_skill_clip_magic(self, _event):
        self._execute_tool("skill_clip_magic", {})

    @on(Button.Pressed, "#skill-btn-sec-scan")
    def _on_skill_sec_scan(self, _event):
        self._prompt_and_execute("skill_sec_scan", "请输入目标 IP 地址:")

    @on(Button.Pressed, "#skill-btn-web-sec")
    def _on_skill_web_sec(self, _event):
        self._prompt_and_execute("skill_web_sec_test", "请输入目标 URL:")
        self._pending_tool = "skill_web_sec_test"
        self._pending_tool_params = {"mode": "full"}

    # ── 子操作按钮 ──
    @on(Button.Pressed, "#skill-btn-uninstall-scan")
    def _on_skill_uninstall_scan(self, _event):
        self._prompt_and_execute("skill_uninstall_scan", "请输入要扫描残留的软件名:")

    @on(Button.Pressed, "#skill-btn-uninstall-do")
    def _on_skill_uninstall_do(self, _event):
        self._append_chat("深度卸载，请输入: 软件名 | dry_run (true/false, 默认true)", "system")
        self._pending_tool = "skill_uninstall_do"

    @on(Button.Pressed, "#skill-btn-junk-scan")
    def _on_skill_junk_scan(self, _event):
        self._execute_tool("skill_junk_scan", {})

    @on(Button.Pressed, "#skill-btn-junk-clean")
    def _on_skill_junk_clean(self, _event):
        self._append_chat("清理垃圾，请输入: dry_run (true/false, 默认true)", "system")
        self._pending_tool = "skill_junk_clean"

    @on(Button.Pressed, "#skill-btn-sys-info")
    def _on_skill_sys_info(self, _event):
        self._execute_tool("skill_sys_info", {})

    @on(Button.Pressed, "#skill-btn-top-procs")
    def _on_skill_top_procs(self, _event):
        self._append_chat("查看 Top 进程，请输入排序方式: cpu 或 memory (默认cpu)", "system")
        self._pending_tool = "skill_top_procs"

    @on(Button.Pressed, "#skill-btn-track-start")
    def _on_skill_track_start(self, _event):
        self._execute_tool("skill_track_start", {})

    @on(Button.Pressed, "#skill-btn-track-stop")
    def _on_skill_track_stop(self, _event):
        self._execute_tool("skill_track_stop", {})

    @on(Button.Pressed, "#skill-btn-track-clean")
    def _on_skill_track_clean(self, _event):
        self._execute_tool("skill_track_clean", {})

    @on(Button.Pressed, "#skill-btn-cloud-list")
    def _on_skill_cloud_list(self, _event):
        self._append_chat("列出云盘文件，请输入: 云盘ID | 路径 (默认/)", "system")
        self._pending_tool = "skill_cloud_list"

    @on(Button.Pressed, "#skill-btn-cloud-search")
    def _on_skill_cloud_search(self, _event):
        self._prompt_and_execute("skill_cloud_search", "请输入搜索关键词:")

    @on(Button.Pressed, "#skill-btn-cloud-status")
    def _on_skill_cloud_status(self, _event):
        self._prompt_and_execute("skill_cloud_status", "请输入传输任务ID:")

    @on(Button.Pressed, "#skill-btn-cloud-dup")
    def _on_skill_cloud_dup(self, _event):
        self._execute_tool("skill_cloud_duplicates", {})

    @on(Button.Pressed, "#skill-btn-clip-stop")
    def _on_skill_clip_stop(self, _event):
        self._execute_tool("skill_stop", {"skill": "clip_magic"})

    @on(Button.Pressed, "#skill-btn-clip-status")
    def _on_skill_clip_status(self, _event):
        self._execute_tool("skill_status", {"skill": "clip_magic"})

    @on(Button.Pressed, "#skill-btn-clip-history")
    def _on_skill_clip_history(self, _event):
        self._execute_tool("skill_clip_history", {})

    @on(Button.Pressed, "#skill-btn-all-status")
    def _on_skill_all_status(self, _event):
        self._execute_tool("skill_status", {"skill": ""})

    def _prompt_and_execute(self, tool_name: str, prompt: str):
        """在聊天区提示用户输入参数并执行工具."""
        self._append_chat(prompt, "system")
        self._pending_tool = tool_name
        self._update_status(f"等待输入: {prompt[:30]}...")

    def _execute_tool(self, tool_name: str, params: dict):
        """执行指定工具."""
        try:
            if tool_name == "crawl_url":
                from package.network.crawler import run as crawl_run
                url = params.get("url", "")
                self._append_chat(f"🌐 正在爬取: {url}", "system")
                crawl_run(url=url)
                self._append_chat(f"✅ 爬取完成", "ok")

            elif tool_name == "crawl_query":
                from package.network.crawler import run as crawl_run
                query = params.get("query", "")
                crawl_run(search_query=query)
                self._append_chat("✅ 搜索爬取完成", "ok")

            elif tool_name == "email":
                from package.network.e_mail import EmailAssistant
                assistant = EmailAssistant()
                action = params.get("action", "receive")
                if action == "send":
                    to = params.get("to", "")
                    subject = params.get("subject", "")
                    body = params.get("body", "")
                    if not to or not subject:
                        self._append_chat("❌ 发送邮件需要收件人和主题", "error")
                    else:
                        assistant.send_email(subject, body, to)
                        self._append_chat("✅ 邮件已发送", "ok")
                else:
                    emails = assistant.fetch_unread_emails()
                    assistant.display_emails(emails)
                    self._append_chat(f"📧 收到 {len(emails)} 封邮件", "ok")

            elif tool_name == "img_search":
                from package.network.image_search_tool import run as img_run
                query = params.get("query", "")
                img_run(query=query)
                self._append_chat("✅ 图片搜索完成", "ok")

            elif tool_name == "weather":
                self._tool_weather(params.get("city", ""))

            elif tool_name == "translate":
                self._tool_translate(params.get("text", ""))

            elif tool_name == "encrypt":
                self._tool_encrypt(params.get("path", ""))

            elif tool_name == "decrypt":
                self._tool_decrypt(params.get("path", ""))

            elif tool_name == "audit_security":
                from butler.core.sec_utils.audit import run_security_audit
                result = run_security_audit()
                self._append_chat(str(result), "ai")

            elif tool_name == "audit_dir":
                from package.core_utils.system_executor_tool import run as audit_run
                path = params.get("path", "")
                audit_run(dir=path)
                self._append_chat("✅ 目录审计完成", "ok")

            elif tool_name == "convert":
                from package.document.file_converter import run as conv_run
                inp = params.get("input", "")
                out = params.get("output", "")
                conv_run(input_file=inp, output_file=out)
                self._append_chat("✅ 文件转换完成", "ok")

            elif tool_name == "file":
                from package.file_system.file_manager import FileManager
                fm = FileManager()
                op = params.get("op", "list")
                path = params.get("path", "")
                content = params.get("content", "")
                if op == "create":
                    success, msg = fm.create_file(path, content)
                    self._append_chat(msg, "ok" if success else "error")
                elif op == "read":
                    success, c = fm.read_file(path)
                    self._append_chat(c if success else f"❌ {c}", "ai" if success else "error")
                elif op == "delete":
                    success, msg = fm.delete_file(path)
                    self._append_chat(msg, "ok" if success else "error")
                elif op == "list":
                    success, items = fm.list_directory(path)
                    if success:
                        self._append_chat(f"📂 {path}:\n" + "\n".join(f"  - {i}" for i in items), "ai")
                    else:
                        self._append_chat(f"❌ {items}", "error")

            elif tool_name == "monitor":
                from package.core_utils.health_monitor import run as monitor_run
                monitor_run()
                self._append_chat("✅ 系统监控完成", "ok")

            elif tool_name == "dependency":
                from package.core_utils.dependency_manager import run as dep_run
                op = params.get("op", "install")
                pkg = params.get("package", "")
                result = dep_run(command=op, package=pkg)
                self._append_chat(str(result), "ai")

            elif tool_name == "doctor":
                self._tool_doctor()

            elif tool_name == "skills_list":
                from butler_cli import main as skills_main
                # 列出技能
                try:
                    from butler.core.skill_manager import SkillManager
                    sm = SkillManager()
                    sm.load_skills()
                    text = "🛠️ 已加载技能:\n"
                    for sid, manifest in sm.manifests.items():
                        text += f"  - {sid}: {manifest.get('description', 'N/A')}\n"
                    self._append_chat(text, "ai")
                except Exception as e:
                    self._append_chat(f"❌ 技能列表加载失败: {e}", "error")

            # ── 技能执行 (无 AI 可用) ──
            elif tool_name == "skill_markitdown":
                from skills.markitdown.markitdown_app import convert
                path = params.get("path", "")
                if not path:
                    self._append_chat("用法: /markitdown <文件路径>", "system")
                    return
                self._append_chat(f"📄 转换文件为 Markdown: {path}", "system")
                result = convert(path)
                self._append_chat(result[:5000] if len(result) > 5000 else result, "ai")

            elif tool_name == "skill_docx":
                from skills.docx.main import handle_request
                action = params.get("action", "read")
                result = handle_request(action, **params)
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_pdf":
                from skills.pdf.main import handle_request
                action = params.get("action", "extract_text")
                result = handle_request(action, **params)
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_archive":
                from skills.archive_manager import handle_request
                action = params.get("action", "list_contents")
                result = handle_request(action, **params)
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_uninstaller":
                from skills.geek_uninstaller.main import handle_request
                action = params.get("action", "list")
                result = handle_request(action, **params)
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_sys_clean":
                from skills.sys_cleaner.main import start_track, stop_track
                action = params.get("action", "help")
                if action == "track":
                    result = start_track(params)
                    self._append_chat(f"🔍 开始追踪安装变更: {result}", "system")
                elif action == "clean":
                    result = stop_track(params)
                    self._append_chat(f"🧹 清理结果: {result}", "ai")
                else:
                    self._append_chat("用法: /sys_clean [track | clean]", "system")

            elif tool_name == "skill_media_scan":
                from skills.media_manager.media_manager import MediaManagerSkill
                mm = MediaManagerSkill()
                library = mm.get_media_library()
                if library:
                    audio_files = [f for f in library if f.get("type") == "audio"]
                    image_files = [f for f in library if f.get("type") == "image"]
                    self._append_chat(
                        f"🎵 扫描完成: {len(audio_files)} 个音频, {len(image_files)} 张图片\n"
                        f"前 10 个文件:\n" + "\n".join(f"  - {f.get('name', '?')}" for f in library[:10]),
                        "ai"
                    )
                else:
                    self._append_chat("未找到媒体文件", "system")

            elif tool_name == "skill_storage_hub":
                from skills.storage_hub.hub_manager import HubManager
                hub = HubManager()
                action = params.get("action", "list")
                if action == "list":
                    drives = hub.config.get("drives", [])
                    if drives:
                        lines = ["☁️ 已配置云盘:"]
                        for d in drives:
                            lines.append(f"  - {d.get('name', '?')} ({d.get('type', '?')})")
                        self._append_chat("\n".join(lines), "ai")
                    else:
                        self._append_chat("未配置云盘适配器", "system")
                else:
                    self._append_chat(f"云盘操作: {action} (详细操作请使用 CLI)", "system")

            elif tool_name == "skill_clip_magic":
                from skills.skill_clip_magic.clip_analyzer import handle_request
                result = handle_request("run")
                self._append_chat(f"📋 {result}", "ok")

            elif tool_name == "skill_sec_scan":
                from skills.skill_sec_radar.sec_manager import handle_request
                target = params.get("target", "127.0.0.1")
                self._append_chat(f"🔍 SYN 扫描目标: {target}", "system")
                result = handle_request("scan", target=target)
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_web_sec_test":
                from skills.security.web_security_tester.main import handle_request
                target = params.get("target", "")
                mode = params.get("mode", "full")
                if not target:
                    self._append_chat("用法: /web_sec_test <目标URL>", "system")
                    return
                self._append_chat(f"🛡️ Web 安全测试: {target} (模式: {mode})", "system")
                result = handle_request("test", target=target, mode=mode)
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_format_convert":
                from skills.format_convert.format_convert import handle_request
                inp = params.get("input", "")
                to_fmt = params.get("to_fmt", "docx")
                if not inp:
                    self._append_chat("用法: /format_convert <输入文件> | <输出格式>", "system")
                    return
                self._append_chat(f"🔄 格式转换: {inp} → {to_fmt}", "system")
                result = handle_request("run", input=inp, to=to_fmt)
                self._append_chat(str(result), "ai")

            # ── 技能控制 (停止/状态) ──
            elif tool_name == "skill_stop":
                skill_name = params.get("skill", "").strip()
                if not skill_name:
                    self._append_chat("用法: /skill_stop <技能名>\n支持: clip_magic, focus, pixel_pet", "system")
                    return
                self._append_chat(f"⏹️ 停止技能: {skill_name}", "system")
                try:
                    if skill_name in ("clip_magic", "clipmagic"):
                        from skills.skill_clip_magic.clip_analyzer import handle_request as clip_handler
                        result = clip_handler("stop")
                    elif skill_name in ("focus", "focus_mode"):
                        if self.command_callback:
                            self.command_callback("text", "/focus-stop")
                        result = "专注模式已停止"
                    elif skill_name in ("pixel_pet", "pixelpet"):
                        result = "Pixel Pet 可通过关闭窗口停止"
                    else:
                        result = f"未知技能: {skill_name}"
                    self._append_chat(str(result), "ok")
                except Exception as e:
                    self._append_chat(f"❌ 停止失败: {e}", "error")

            elif tool_name == "skill_status":
                skill_name = params.get("skill", "").strip()
                if not skill_name:
                    # 列出所有后台技能状态
                    lines = ["📊 后台技能状态:"]
                    try:
                        from skills.skill_clip_magic.clip_analyzer import handle_request as clip_handler
                        lines.append(f"  ClipMagic: {clip_handler('status')}")
                    except Exception:
                        lines.append("  ClipMagic: (无法查询)")
                    lines.append("  Focus: (需完整运行时)")
                    lines.append("  PixelPet: (需查看进程)")
                    self._append_chat("\n".join(lines), "ai")
                else:
                    try:
                        if skill_name in ("clip_magic", "clipmagic"):
                            from skills.skill_clip_magic.clip_analyzer import handle_request as clip_handler
                            result = clip_handler("status")
                        else:
                            result = f"未知技能: {skill_name}"
                        self._append_chat(str(result), "ai")
                    except Exception as e:
                        self._append_chat(f"❌ 查询失败: {e}", "error")

            elif tool_name == "skill_clip_history":
                from skills.skill_clip_magic.clip_analyzer import handle_request as clip_handler
                result = clip_handler("history")
                self._append_chat(str(result), "ai")

            # ── 卸载子操作 ──
            elif tool_name == "skill_uninstall_scan":
                from skills.geek_uninstaller.main import handle_request as un_handler
                name = params.get("name", "").strip()
                if not name:
                    self._append_chat("用法: /uninstall_scan <软件名>", "system")
                    return
                self._append_chat(f"🔍 扫描 {name} 的残留文件...", "system")
                result = un_handler("scan_leftovers", name=name)
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_uninstall_do":
                from skills.geek_uninstaller.main import handle_request as un_handler
                name = params.get("name", "").strip()
                if not name:
                    self._append_chat("用法: /uninstall_do <软件名> [| dry_run]", "system")
                    return
                dry_run = params.get("dry_run", "true")
                dry_run = dry_run != "false"
                self._append_chat(f"🗑️ 深度卸载 {name} (dry_run={dry_run})...", "system")
                result = un_handler("uninstall", name=name, dry_run=dry_run)
                self._append_chat(str(result), "ai")

            # ── 垃圾清理子操作 ──
            elif tool_name == "skill_junk_scan":
                from skills.geek_uninstaller.main import handle_request as un_handler
                self._append_chat("🧹 扫描系统垃圾文件...", "system")
                result = un_handler("scan_junk")
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_junk_clean":
                from skills.geek_uninstaller.main import handle_request as un_handler
                dry_run = params.get("dry_run", "true")
                dry_run = dry_run != "false"
                self._append_chat(f"🧹 清理垃圾文件 (dry_run={dry_run})...", "system")
                result = un_handler("clean_junk", dry_run=dry_run)
                self._append_chat(str(result), "ai")

            # ── 系统信息子操作 ──
            elif tool_name == "skill_sys_info":
                from skills.geek_uninstaller.main import handle_request as un_handler
                self._append_chat("📊 获取系统信息...", "system")
                result = un_handler("system_info")
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_top_procs":
                from skills.geek_uninstaller.main import handle_request as un_handler
                sort_by = params.get("sort_by", "cpu") or "cpu"
                self._append_chat(f"📈 Top 进程 (按 {sort_by} 排序)...", "system")
                result = un_handler("top_processes", sort_by=sort_by)
                self._append_chat(str(result), "ai")

            # ── 云盘子操作 ──
            elif tool_name == "skill_cloud_list":
                from skills.storage_hub.hub_manager import handle_request as cloud_handler
                drive = params.get("drive", "")
                path = params.get("path", "/")
                if not drive:
                    self._append_chat("用法: /cloud_list <云盘ID> [| 路径]", "system")
                    return
                result = cloud_handler("list_files", drive=drive, path=path)
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_cloud_search":
                from skills.storage_hub.hub_manager import handle_request as cloud_handler
                query = params.get("query", "")
                if not query:
                    self._append_chat("用法: /cloud_search <关键词>", "system")
                    return
                self._append_chat(f"🔍 搜索云盘文件: {query}", "system")
                result = cloud_handler("search_all", query=query)
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_cloud_transfer":
                from skills.storage_hub.hub_manager import handle_request as cloud_handler
                src = params.get("src_drive", "")
                dst = params.get("dst_drive", "")
                fname = params.get("file_name", "")
                if not src or not dst or not fname:
                    self._append_chat("用法: /cloud_transfer <源盘> | <目标盘> | <文件名>", "system")
                    return
                self._append_chat(f"☁️ 传输 {fname}: {src} → {dst}", "system")
                result = cloud_handler("transfer", src_drive=src, dst_drive=dst,
                                       file_name=fname, source_path=params.get("source_path", "/"),
                                       dst_path=params.get("dst_path", "/"))
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_cloud_status":
                from skills.storage_hub.hub_manager import handle_request as cloud_handler
                task_id = params.get("task_id", "")
                if not task_id:
                    self._append_chat("用法: /cloud_status <任务ID>", "system")
                    return
                result = cloud_handler("check_transfer_status", task_id=task_id)
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_cloud_duplicates":
                from skills.storage_hub.hub_manager import handle_request as cloud_handler
                self._append_chat("🔍 查找重复文件...", "system")
                result = cloud_handler("find_duplicates")
                self._append_chat(str(result), "ai")

            # ── 安装追踪子操作 ──
            elif tool_name == "skill_track_start":
                from skills.sys_cleaner.main import handle_request as track_handler
                self._append_chat("📸 捕获安装前快照...", "system")
                result = track_handler("start_track")
                self._append_chat(str(result), "system")

            elif tool_name == "skill_track_stop":
                from skills.sys_cleaner.main import handle_request as track_handler
                self._append_chat("📸 捕获安装后快照并生成差异...", "system")
                result = track_handler("stop_track")
                self._append_chat(str(result), "ai")

            elif tool_name == "skill_track_clean":
                from skills.sys_cleaner.main import handle_request as track_handler
                self._append_chat("🧹 执行残留清理...", "system")
                result = track_handler("execute_clean")
                self._append_chat(str(result), "ai")

            else:
                self._append_chat(f"未知工具: {tool_name}", "error")

        except Exception as e:
            self._append_chat(f"❌ 工具执行异常: {e}", "error")

    @property
    def _pending_tool(self):
        if not hasattr(self, "_pending_tool_value"):
            self._pending_tool_value = None
        return self._pending_tool_value

    @_pending_tool.setter
    def _pending_tool(self, value):
        self._pending_tool_value = value

    @property
    def _pending_tool_params(self):
        if not hasattr(self, "_pending_tool_params_value"):
            self._pending_tool_params_value = {}
        return self._pending_tool_params_value

    @_pending_tool_params.setter
    def _pending_tool_params(self, value):
        self._pending_tool_params_value = value

    # ------------------------ Dashboard ------------------------ #

    def _init_dashboard(self):
        self._update_dashboard()

    def _update_dashboard(self):
        sys_info = self._get_system_info()
        mem_info = self._get_memory_info()

        sys_static = self.query_existing("#dash-system", Static)
        if sys_static:
            sys_static.update(sys_info)

        mem_static = self.query_existing("#dash-memory", Static)
        if mem_static:
            mem_static.update(mem_info)

        tasks_table = self.query_existing("#dash-tasks-table", DataTable)
        if tasks_table:
            tasks_table.clear(columns=True)
            tasks_table.add_columns("ID", "任务", "状态", "负责人")
            tasks = self._get_sample_tasks()
            for t in tasks[:5]:
                status_icon = {"pending": "⏳", "in_progress": "▶️", "completed": "✅"}.get(t["status"], "❓")
                tasks_table.add_row(str(t["id"]), t["subject"], f"{status_icon} {t['status']}", t.get("owner", "-"))

    def _get_system_info(self) -> str:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return (
                f"[bold]系统资源[/bold]\n"
                f"  CPU: {cpu}%\n"
                f"  内存: {mem.percent}% ({mem.used//1024//1024}MB / {mem.total//1024//1024}MB)\n"
                f"  磁盘: {disk.percent}% ({disk.free//1024//1024//1024}GB 可用)\n"
            )
        except Exception:
            return "[bold]系统资源[/bold]\n  （需要 psutil 包）"

    def _get_memory_info(self) -> str:
        return (
            f"[bold]Butler 记忆[/bold]\n"
            f"  后端: SQLite (本地)\n"
            f"  状态: 已连接\n"
            f"  长期记忆: 已激活\n"
            f"  做梦引擎: 就绪\n"
        )

    def _get_sample_tasks(self):
        try:
            from butler.core.task_manager import task_manager
            return task_manager.list_business_tasks()
        except Exception:
            return [
                {"id": 1, "subject": "示例任务: 配置 API 密钥", "status": "pending", "owner": "user"},
                {"id": 2, "subject": "示例任务: 检查系统健康", "status": "in_progress", "owner": "system"},
            ]

    # ------------------------ Memory View ------------------------ #

    def _init_memory_view(self):
        tabs = self.query_existing("#view-memory", Vertical)
        if not tabs:
            return

        # Load default content for each tab
        self._update_memory_content("memos")

    def _update_memory_content(self, tab_id: str):
        content = self.query_existing("#memory-content", VerticalScroll)
        if not content:
            return
        for child in list(content.children):
            child.remove()

        if tab_id == "memos":
            text = self._get_memos()
        elif tab_id == "long-mem":
            text = self._get_long_memory()
        elif tab_id == "recent":
            text = self._get_recent_history()
        else:
            text = "选择要查看的记忆类型"

        content.mount(Label(text))

    def _get_memos(self) -> str:
        try:
            from butler.core.memory.memory_engine import UnifiedMemoryEngine
            return "📝 Butler 备忘录\n\n（记忆引擎就绪后显示实际内容）"
        except Exception:
            return "📝 Butler 备忘录\n\n（记忆模块加载中...）"

    def _get_long_memory(self) -> str:
        return "📚 长期记忆库\n\n（显示已存储的事实与知识条目）"

    def _get_recent_history(self) -> str:
        return "💭 最近对话历史\n\n（显示最近的交互记录）"

    @on(Tabs.TabActivated, "#view-memory Tabs")
    def _on_memory_tab_changed(self, event):
        tab_id = event.tab.id if event.tab else None
        if tab_id:
            self._update_memory_content(tab_id)

    # ------------------------ Tasks View ------------------------ #

    def _init_tasks_view(self):
        table = self.query_existing("#tasks-table", DataTable)
        if table:
            table.add_columns("ID", "任务", "状态", "负责人", "操作")
            self._refresh_tasks()

    def _refresh_tasks(self):
        table = self.query_existing("#tasks-table", DataTable)
        if not table:
            return
        table.clear()
        tasks = self._get_sample_tasks()
        for t in tasks:
            status_icon = {"pending": "⏳", "in_progress": "▶️", "completed": "✅"}.get(t["status"], "❓")
            table.add_row(
                str(t["id"]),
                t["subject"],
                f"{status_icon} {t['status']}",
                t.get("owner", "-"),
                "详情"
            )

    @on(Button.Pressed, "#btn-new-task")
    def _on_new_task(self, _event):
        self._append_chat("新建任务功能 (需要完整运行时)", "system")

    @on(Button.Pressed, "#btn-refresh-tasks")
    def _on_refresh_tasks(self, _event):
        self._refresh_tasks()

    # ------------------------ Skills View ------------------------ #

    def _init_skills_view(self):
        self._refresh_skills()

    def _refresh_skills(self):
        tree = self.query_existing("#skills-tree", Tree)
        if not tree:
            return
        tree.reset("技能列表")
        tree.root.expand()

        try:
            from butler.core.skill_manager import SkillManager
            sm = SkillManager()
            sm.load_skills()
            for skill_id, manifest in sm.manifests.items():
                node = tree.root.add(
                    f"{skill_id} v{manifest.get('version', '?')}",
                    expand=False,
                )
                node.add(f"描述: {manifest.get('description', 'N/A')}")
                node.add(f"入口: {manifest.get('entry', 'N/A')}")
        except Exception as e:
            tree.root.add(f"(技能加载失败: {e})")

    @on(Button.Pressed, "#btn-refresh-skills")
    def _on_refresh_skills(self, _event):
        self._refresh_skills()

    # ------------------------ Packages View ------------------------ #

    def _init_packages_view(self):
        table = self.query_existing("#pkgs-table", DataTable)
        if table:
            table.add_columns("名称", "版本", "状态", "类型")
        self._refresh_packages()

    def _refresh_packages(self):
        table = self.query_existing("#pkgs-table", DataTable)
        if not table:
            return
        table.clear()

        try:
            from butler.package_runtime.loader import PackageLoader
            loader = PackageLoader()
            packages = loader.registry.list_packages()
            for p in packages:
                manifest = loader.get_manifest(p['name'])
                ptype = manifest.type if manifest else "unknown"
                table.add_row(p['name'], p['version'], p['status'], ptype)
        except Exception:
            table.add_row("(包列表加载中...)", "", "", "")

    @on(Button.Pressed, "#btn-list-pkgs")
    def _on_list_pkgs(self, _event):
        self._refresh_packages()

    @on(Button.Pressed, "#btn-install-pkg")
    def _on_install_pkg(self, _event):
        path_input = self.query_existing("#pkg-path", Input)
        if not path_input or not path_input.value.strip():
            self._append_chat("请先输入包路径", "error")
            return
        path = path_input.value.strip()
        self._append_chat(f"正在安装包: {path}", "system")
        try:
            from butler.package_runtime.loader import PackageLoader
            loader = PackageLoader()
            if loader.install(path):
                self._append_chat(f"✅ 包安装成功: {path}", "ok")
                self._refresh_packages()
            else:
                self._append_chat(f"❌ 包安装失败: {path}", "error")
        except Exception as e:
            self._append_chat(f"❌ 安装异常: {e}", "error")

    # ------------------------ Agents View ------------------------ #

    def _init_agents_view(self):
        self._refresh_agents()

    def _refresh_agents(self):
        tree = self.query_existing("#agents-tree", Tree)
        if not tree:
            return
        tree.root.add("🔄 正在加载员工列表...", expand=False)

        try:
            from butler.package_runtime.loader import PackageLoader
            loader = PackageLoader()
            packages = loader.registry.list_packages()
            for p in packages:
                manifest = loader.get_manifest(p['name'])
                if manifest and manifest.type == "agent":
                    tree.root.add(
                        f"🤖 {p['name']} v{p['version']}",
                        expand=False,
                    )
        except Exception:
            pass

        if not list(tree.root.children):
            tree.root.add("(暂无数字员工角色，请先安装 agent 类型的包)")

    @on(Button.Pressed, "#btn-refresh-agents")
    def _on_refresh_agents(self, _event):
        self._refresh_agents()

    @on(Button.Pressed, "#btn-run-agent")
    def _on_run_agent(self, _event):
        role_input = self.query_existing("#agent-role", Input)
        task_input = self.query_existing("#agent-task", Input)
        if not role_input or not role_input.value.strip():
            self._append_chat("请输入员工角色名称", "error")
            return
        if not task_input or not task_input.value.strip():
            self._append_chat("请输入任务描述", "error")
            return

        role = role_input.value.strip()
        task = task_input.value.strip()
        self._append_chat(f"🤖 指派任务给 [{role}]: {task}", "system")

        try:
            from butler.agent.agent import Agent
            agent = Agent(role=role)
            self._append_chat(f"⏳ 员工 [{role}] 正在执行任务...", "system")
            result = agent.run_task(task)
            self._append_chat(f"✅ 任务完成: {result.get('status', 'unknown')}", "ok")
            if result.get('report'):
                self._append_chat(f"📋 汇报:\n{result['report']}", "ai")
        except Exception as e:
            self._append_chat(f"❌ 执行失败: {e}", "error")

    # ------------------------ TimeMachine ------------------------ #

    def _init_timemachine_view(self):
        self._refresh_timemachine()

    def _refresh_timemachine(self):
        table = self.query_existing("#tm-table", DataTable)
        if not table:
            return
        table.clear(columns=True)
        table.add_columns("时间", "类别", "详情")

        try:
            from butler.core.time_machine import time_machine
            now = time.time()
            snapshots = time_machine.get_range(now - 3600, now)
            for s in snapshots[-20:]:
                ts = s.get("timestamp", 0)
                import datetime
                dt = datetime.datetime.fromtimestamp(ts)
                cat = s.get("category", "unknown")
                payload = s.get("payload", {})
                if isinstance(payload, dict):
                    detail = str(payload)[:100]
                else:
                    detail = str(payload)[:100]
                table.add_row(dt.strftime("%H:%M:%S"), cat, detail)
        except Exception:
            table.add_row("(时光机数据加载中...)", "", "")

    @on(Button.Pressed, "#btn-refresh-tm")
    def _on_refresh_tm(self, _event):
        self._refresh_timemachine()

    # ------------------------ Settings View ------------------------ #

    def _init_settings_view(self):
        content = self.query_existing("#settings-content", VerticalScroll)
        if not content:
            return
        settings_html = self._build_settings_html()
        content.mount(Label(settings_html))

    def _build_settings_html(self) -> str:
        # 动态读取当前 AI 提供商配置
        try:
            from butler.core.config_model import PROVIDER_DEFAULTS, PROVIDER_KEY_PATHS
            import os as _os
            _provider = _os.getenv("AI_PROVIDER", "deepseek") or "deepseek"
            _defaults = PROVIDER_DEFAULTS.get(_provider, PROVIDER_DEFAULTS["deepseek"])
            _label = _os.getenv("CUSTOM_PROVIDER_NAME", "") or ""
            _key_env = _defaults["key_env"]
            _kv = _os.getenv(_key_env, "") or ""
            if _kv and "YOUR_" not in _kv:
                _key_status = f"{_kv[:4]}***（已配置）"
            else:
                _key_status = "未配置"
            _name = _defaults["display_name"] + (f"（{_label}）" if _label else "")
            _api_lines = [
                "[bold]🔑 API 配置[/bold]",
                f"  当前提供商: {_provider} ({_name})",
                f"  密钥状态: {_key_env} = {_key_status}",
                "  配置文件: config/config.yaml",
                "  环境变量: .env",
                "  [提示] 在终端运行 [bold]butler config[/bold] 可交互式切换服务商/填写密钥",
                "         运行 [bold]butler config show[/bold] 查看当前配置\n",
            ]
        except Exception:
            _api_lines = [
                "[bold]🔑 API 配置[/bold]",
                "  配置文件: config/config.yaml",
                "  环境变量: .env",
                "  [提示] 在终端运行 [bold]butler config[/bold] 配置 AI 服务商\n",
            ]

        lines = [
            "[bold]⚙️ Butler 设置[/bold]\n",
            "[bold]🎨 主题[/bold]",
            "  当前: 默认深色",
            "  可选: dark, light, google, apple\n",
        ]
        lines.extend(_api_lines)
        lines.extend([
            "[bold]🔊 语音[/bold]",
            "  模式: offline",
            "  可选: offline, local, online\n",
            "[bold]💾 存储[/bold]",
            "  记忆后端: SQLite",
            "  数据目录: data/butler_memory/\n",
        ])
        return "\n".join(lines)

    @on(Tabs.TabActivated, "#view-settings Tabs")
    def _on_settings_tab_changed(self, event):
        self._update_status(f"设置分类: {event.tab.id if event.tab else ''}")

    # ------------------------ Tools (CLI commands) ------------------------ #

    def _tool_weather(self, city: str):
        self._append_chat(f"🌤️ 查询天气: {city}", "system")
        try:
            from package.network.weather import get_weather_from_web
            res = get_weather_from_web(city)
            if res:
                msg = f"☀️ {city} 天气:\n"
                for k, v in res.items():
                    msg += f"  {k}: {v}\n"
                self._append_chat(msg, "ai")
            else:
                self._append_chat("❌ 无法获取天气信息", "error")
        except Exception as e:
            self._append_chat(f"❌ 天气查询失败: {e}", "error")

    def _tool_encrypt(self, path: str):
        self._append_chat(f"🔐 加密文件: {path}", "system")
        try:
            from package.security.encrypt import DualLayerEncryptor
            import getpass
            core_code = getpass.getpass("请输入 6 位核心码: ")
            result = DualLayerEncryptor().encrypt_file(path, core_code)
            self._append_chat(f"✅ 加密成功: {result}", "ok")
        except Exception as e:
            self._append_chat(f"❌ 加密失败: {e}", "error")

    def _tool_decrypt(self, path: str):
        self._append_chat(f"🔓 解密文件: {path}", "system")
        try:
            from package.security.encrypt import DualLayerEncryptor
            import getpass
            core_code = getpass.getpass("请输入 6 位核心码: ")
            result = DualLayerEncryptor().decrypt_file(path, core_code)
            self._append_chat(f"✅ 解密成功: {result}", "ok")
        except Exception as e:
            self._append_chat(f"❌ 解密失败: {e}", "error")

    def _tool_translate(self, text: str):
        self._append_chat(f"🌐 翻译: {text}", "system")
        try:
            from package.document.translators import translate_text
            result = translate_text(text)
            self._append_chat(f"翻译结果: {result}", "ai")
        except Exception as e:
            self._append_chat(f"❌ 翻译失败: {e}", "error")

    def _tool_doctor(self):
        self._append_chat("🔍 运行系统诊断...", "system")
        try:
            from butler.cli.doctor_cmd import run_doctor
            from io import StringIO
            import sys
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            run_doctor()
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
            self._append_chat(output, "ai")
        except Exception as e:
            self._append_chat(f"❌ 诊断失败: {e}", "error")

    # ------------------------ Status / Queue ------------------------ #

    def _update_status(self, msg: str):
        self.status_message = msg
        st = self.query_existing("#status-text", Static)
        if st:
            st.update(f"● {msg}")

    def _drain_queue(self):
        with self._queue_lock:
            while self._msg_queue:
                try:
                    msg_type, payload = self._msg_queue.pop(0)
                    if msg_type == "chat":
                        self._append_chat(str(payload.get("text", "")), payload.get("tag", "normal"))
                    elif msg_type == "status":
                        self._update_status(str(payload))
                except Exception:
                    pass

    def enqueue_message(self, msg_type: str, payload: dict):
        with self._queue_lock:
            self._msg_queue.append((msg_type, payload))

    # ------------------------ Public API ------------------------ #

    def set_jarvis(self, jarvis):
        self.jarvis = jarvis

    def set_command_callback(self, callback):
        self.command_callback = callback

    def on_app_shutdown(self):
        self._stop_event.set()


def run_tui():
    """启动 Butler TUI."""
    run_preflight_check()

    app = ButlerTUI()

    # Try to initialize Jarvis in headless mode
    try:
        from butler.butler_app import Jarvis, USBScreen
        usb_screen = USBScreen(40, 8)
        jarvis = Jarvis(root=None, usb_screen=usb_screen, headless=True)
        app.set_jarvis(jarvis)
        app.set_command_callback(jarvis.panel_command_handler)

        # Subscribe to event bus for UI updates
        def ui_output_handler(message, tag, response_id):
            app.enqueue_message("chat", {"text": message, "tag": tag})

        event_bus.subscribe("ui_output", ui_output_handler)

        # Start Jarvis background
        jarvis.main()
    except Exception as e:
        logger.warning(f"Jarvis 初始化失败 (TUI 将以演示模式运行): {e}")
        app._update_status("演示模式 - Jarvis 未连接")

    try:
        app.run()
    except Exception as e:
        logger.error(f"TUI 运行异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        app.on_app_shutdown()
        if app.jarvis:
            try:
                app.jarvis._handle_exit()
            except Exception:
                pass


if __name__ == "__main__":
    run_tui()
