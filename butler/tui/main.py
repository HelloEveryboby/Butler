# -*- coding: utf-8 -*-
"""Butler TUI 主入口 - 启动完整的终端用户界面."""

import sys
import os
import json
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
            ("🔧 辅助工具", "tools2"),
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
                    yield Tabs(
                        Tab("🐍 可调用技能", id="skills-tab-user"),
                        Tab("🤖 Agent 技能", id="skills-tab-agent"),
                    )
                    yield Tree("可调用技能", id="skills-tree-user")
                    yield Tree("Agent 技能", id="skills-tree-agent", visible=False)
                    with Horizontal(id="skill-action-bar"):
                        yield Button("▶ 运行", id="btn-skill-run", variant="success")
                        yield Button("📖 查看指令", id="btn-skill-view", variant="primary")
                        yield Button("📋 详情", id="btn-skill-info", variant="default")
                        yield Label("", id="skill-selected-label")

                # Tools view (辅助工具)
                with Vertical(id="view-tools2", visible=False):
                    yield Label("🔧 辅助工具", classes="tool-section-title")
                    with Horizontal():
                        yield Button("🔄 刷新工具", id="btn-refresh-tool-list")
                        yield Select([], id="tool-filter", allow_blank=True, placeholder="筛选权限...")
                    yield DataTable(id="tools-table")
                    with Horizontal(id="tool-action-bar"):
                        yield Button("▶ 执行", id="btn-tool-run", variant="success")
                        yield Button("📋 详情", id="btn-tool-info", variant="default")
                        yield Label("", id="tool-selected-label")

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
        self._init_tools2_view()
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
            "view-tools2", "view-packages", "view-agents",
            "view-timemachine", "view-settings"
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
            preset = getattr(self, "_pending_tool_params", None) or {}
            # 用 Linux 解析器处理带选项的输入, 退化为简单位置参数
            params = self._parse_pending_input(pending, text, preset)
            self._pending_tool_params = {}
            self._execute_tool(pending, params)
            return

        # 尝试 Linux 风格命令 (无 / 前缀, 支持 -f --flag | >)
        if self._try_linux_command(text):
            return

        # 兼容旧 / 前缀命令
        if text.startswith("/"):
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

    # ── 命令名 → tool_name 映射 ──
    _CMD_TO_TOOL = {
        # 技能命令
        "markitdown": ("skill_markitdown", {}),
        "docx_read": ("skill_docx", {"action": "read"}),
        "docx_create": ("skill_docx", {"action": "create"}),
        "pdf_extract": ("skill_pdf", {"action": "extract_text"}),
        "pdf_merge": ("skill_pdf", {"action": "merge"}),
        "pdf_split": ("skill_pdf", {"action": "split"}),
        "archive_compress": ("skill_archive", {"action": "compress"}),
        "archive_extract": ("skill_archive", {"action": "extract"}),
        "archive_list": ("skill_archive", {"action": "list_contents"}),
        "uninstaller": ("skill_uninstaller", {}),
        "uninstall_scan": ("skill_uninstall_scan", {}),
        "uninstall_do": ("skill_uninstall_do", {}),
        "junk_scan": ("skill_junk_scan", {}),
        "junk_clean": ("skill_junk_clean", {}),
        "sys_info": ("skill_sys_info", {}),
        "top_procs": ("skill_top_procs", {}),
        "media_scan": ("skill_media_scan", {}),
        "storage_hub": ("skill_storage_hub", {}),
        "cloud_list": ("skill_cloud_list", {}),
        "cloud_search": ("skill_cloud_search", {}),
        "cloud_transfer": ("skill_cloud_transfer", {}),
        "cloud_status": ("skill_cloud_status", {}),
        "cloud_duplicates": ("skill_cloud_duplicates", {}),
        "clip_magic": ("skill_clip_magic", {}),
        "clip_history": ("skill_clip_history", {}),
        "skill_stop": ("skill_stop", {}),
        "skill_status": ("skill_status", {}),
        "sec_scan": ("skill_sec_scan", {}),
        "web_sec_test": ("skill_web_sec_test", {}),
        "format_convert": ("skill_format_convert", {}),
        "track_start": ("skill_track_start", {}),
        "track_stop": ("skill_track_stop", {}),
        "track_clean": ("skill_track_clean", {}),
        # 网络命令
        "weather": ("weather", {}),
        "crawl_url": ("crawl_url", {}),
        "crawl_query": ("crawl_query", {}),
        "email_send": ("email_send", {}),
        "email_recv": ("email_recv", {}),
        "img_search": ("img_search", {}),
        "translate": ("translate", {}),
        "translate_file": ("translate_file", {}),
        "translate_url": ("translate_url", {}),
        # 安全命令
        "encrypt": ("encrypt", {}),
        "decrypt": ("decrypt", {}),
        "audit_security": ("audit_security", {}),
        "audit_dir": ("audit_dir", {}),
        # 文档命令
        "convert": ("convert", {}),
        "file_create": ("file_create", {}),
        "file_read": ("file_read", {}),
        "file_delete": ("file_delete", {}),
        "file_list": ("file_list", {}),
        # 系统命令
        "monitor": ("monitor", {}),
        "dep_install": ("dep_install", {}),
        "dep_all": ("dep_all", {}),
        "doctor": ("doctor", {}),
        "skills_list": ("skills_list", {}),
        # 对话/管理命令
        "help": ("help", {}),
        "commands": ("commands", {}),
        "howto": ("howto", {}),
        "status": ("status", {}),
        "kairos": ("kairos", {}),
        "performance": ("performance", {}),
        "dream": ("dream", {}),
        "focus": ("focus", {}),
        "focus-stop": ("focus-stop", {}),
        "clear": ("clear", {}),
        "tasks": ("tasks", {}),
        "team": ("team", {}),
        "memory": ("memory", {}),
        "profile": ("profile", {}),
        "exit": ("exit", {}),
        # 底层执行命令
        "py": ("py", {}),
        "sh": ("sh", {}),
        "py_eval": ("py_eval", {}),
    }

    def _parse_pending_input(self, pending: str, text: str, preset: dict) -> dict:
        """解析 pending tool 的用户输入, 支持 Linux 选项和简单位置参数."""
        from butler.tui.linux_parser import parse_pipeline, merge_flags_with_defs
        from butler.tui.command_catalog import FLAG_REGISTRY

        # 反向查找命令名
        cmd_name = pending.replace("skill_", "").replace("skill_", "")
        # 找到对应的 FLAG_REGISTRY 条目
        flag_defs = None
        for cname, defs in FLAG_REGISTRY.items():
            tool_entry = self._CMD_TO_TOOL.get(cname)
            if tool_entry and tool_entry[0] == pending:
                flag_defs = defs
                cmd_name = cname
                break

        # 如果输入包含选项 (- 或 --), 用 Linux 解析器
        if flag_defs is not None and text.strip().startswith("-"):
            pipeline = parse_pipeline(f"{cmd_name} {text}")
            if pipeline.stages:
                params = merge_flags_with_defs(pipeline.stages[0], flag_defs)
                params.update(preset)
                return params

        # 退化为简单位置参数映射
        params = {}
        if flag_defs:
            positionals = text.split()
            pos_idx = 0
            for fd in flag_defs:
                if fd.required and pos_idx < len(positionals):
                    params[fd.dest] = positionals[pos_idx]
                    pos_idx += 1
            if pos_idx < len(positionals):
                params["__positionals__"] = positionals[pos_idx:]
        else:
            # 无 flag_defs, 整行作为单个参数
            params = {"arg": text.strip()}

        params.update(preset)
        return params

    def _try_linux_command(self, text: str) -> bool:
        """尝试解析并执行 Linux 风格命令 (无 / 前缀)."""
        from butler.tui.command_catalog import _BY_NAME, _BY_ALIAS, FLAG_REGISTRY
        from butler.tui.linux_parser import parse_pipeline, merge_flags_with_defs, format_help
        from butler.tui.os_command_adapter import is_os_command, execute_os_command, list_os_commands

        pipeline = parse_pipeline(text)
        if not pipeline.stages:
            return False

        first = pipeline.stages[0]
        cmd_name = first.name.lower()

        # ── 命令解释器 / 翻译器 / 对比器 ──
        if cmd_name in ("cmd_explain", "explain"):
            from butler.tui.os_command_adapter import explain_command
            flag_defs = FLAG_REGISTRY.get(cmd_name, [])
            params = merge_flags_with_defs(first, flag_defs)
            target_cmd = params.get("cmd_name", "")
            args_raw = params.get("args", "")
            args_list = args_raw.split() if args_raw else None
            if not target_cmd:
                self._append_chat(
                    "用法:\n"
                    "  cmd_explain -c <命令名>       # 解释命令 + 三平台翻译\n"
                    "  cmd_explain -c ls -a '-la /tmp'  # 附参数说明\n"
                    "  别名: explain\n",
                    "system"
                )
                return True
            self._append_chat(explain_command(target_cmd, args_list), "ai")
            return True

        if cmd_name == "cmd_translate":
            from butler.tui.os_command_adapter import translate_command_line
            flag_defs = FLAG_REGISTRY.get(cmd_name, [])
            params = merge_flags_with_defs(first, flag_defs)
            cmd_line = params.get("command_line", "")
            target_os = params.get("target_os", "")
            if not cmd_line:
                self._append_chat(
                    "用法:\n"
                    "  cmd_translate -c 'ls -la /home'          # 翻译到三平台\n"
                    "  cmd_translate -c 'dir /s' -t linux       # 翻译到指定平台\n"
                    "  cmd_translate -c 'grep error log' -t windows\n",
                    "system"
                )
                return True
            if target_os and target_os.lower() in ("linux", "windows", "macos"):
                result = translate_command_line(cmd_line, target_os.lower())
                self._append_chat(
                    f"🔄 翻译到 {target_os.upper()}:\n"
                    f"  输入: {cmd_line}\n"
                    f"  输出: {result}",
                    "ai"
                )
            else:
                lines = [f"🔄 跨平台翻译: {cmd_line}\n"]
                for os_name in ("linux", "windows", "macos"):
                    translated = translate_command_line(cmd_line, os_name)
                    lines.append(f"  {os_name.upper():<9} 👉  {translated}")
                self._append_chat("\n".join(lines), "ai")
            return True

        if cmd_name in ("cmd_compare", "compare"):
            from butler.tui.os_command_adapter import compare_commands
            flag_defs = FLAG_REGISTRY.get(cmd_name, [])
            params = merge_flags_with_defs(first, flag_defs)
            commands_str = params.get("commands", "")
            # 优先用 --list, 退化为位置参数
            if commands_str:
                if "," in commands_str:
                    cmd_list = [s.strip() for s in commands_str.split(",")]
                else:
                    cmd_list = commands_str.split()
            else:
                cmd_list = list(first.positionals)
            if not cmd_list:
                self._append_chat(
                    "用法:\n"
                    "  cmd_compare 'ls -la' 'grep pattern file'\n"
                    "  cmd_compare ls, grep, ping, find\n"
                    "  compare -l 'ls -la,dir,find'\n"
                    "别名: compare\n",
                    "system"
                )
                return True
            self._append_chat(compare_commands(cmd_list), "ai")
            return True

        # ── 优先检查 OS 原生命令 (ls, cat, grep, ping, ps...) ──
        if is_os_command(cmd_name):
            # 特殊处理: os_help 命令
            if cmd_name in ("os_help", "oslist", "oscommands"):
                self._append_chat(list_os_commands(), "ai")
                return True

            # 收集位置参数和选项, 组合为 args
            args = list(first.positionals)
            for key, val in first.flags.items():
                if key == "__help__":
                    # OS 命令的 --help: 显示 man 风格信息
                    resolved = __import__("butler.tui.os_command_adapter", fromlist=["resolve_command"]).resolve_command(cmd_name)
                    resolved_str = " ".join(resolved) if resolved else "N/A"
                    self._append_chat(
                        f"命令: {cmd_name}\n"
                        f"平台映射: {resolved_str}\n"
                        f"用法: {cmd_name} [选项] [参数]\n"
                        f"支持管道 | 和重定向 >",
                        "system"
                    )
                    return True
                if val is True:
                    args.append(f"--{key}")
                else:
                    args.append(f"--{key}" if len(key) > 1 else f"-{key}")
                    args.append(str(val))

            # 处理管道: 先执行 OS 命令, 再用管道处理结果
            if len(pipeline.stages) > 1 or pipeline.redirect_to:
                result = execute_os_command(cmd_name, args)
                result_str = result.output if result.success else result.output

                # 重定向
                if pipeline.redirect_to and not pipeline.stages[1:]:
                    try:
                        with open(pipeline.redirect_to, "w", encoding="utf-8") as f:
                            f.write(result_str)
                        self._append_chat(f"✅ 输出已保存到 {pipeline.redirect_to}", "ok")
                    except Exception as e:
                        self._append_chat(f"❌ 写入失败: {e}", "error")
                    return True

                # 管道处理
                for stage in pipeline.stages[1:]:
                    pipe_cmd = stage.name.lower()
                    if is_os_command(pipe_cmd):
                        # 管道中也是 OS 命令 (如 grep), 将前一结果作为输入
                        pipe_args = list(stage.positionals)
                        # 用 echo 管道方式或直接用内置处理
                        if pipe_cmd in ("grep", "findstr"):
                            keyword = " ".join(pipe_args) if pipe_args else ""
                            ignore_case = stage.flags.get("i") or stage.flags.get("ignore-case")
                            if ignore_case:
                                filtered = [ln for ln in result_str.split("\n")
                                            if keyword.lower() in ln.lower()]
                            else:
                                filtered = [ln for ln in result_str.split("\n")
                                            if keyword in ln]
                            result_str = "\n".join(filtered) if filtered else "(无匹配)"
                        elif pipe_cmd in ("head",):
                            n = int(pipe_args[0]) if pipe_args else 10
                            result_str = "\n".join(result_str.split("\n")[:n])
                        elif pipe_cmd in ("tail",):
                            n = int(pipe_args[0]) if pipe_args else 10
                            result_str = "\n".join(result_str.split("\n")[-n:])
                        elif pipe_cmd in ("wc",):
                            lines = result_str.strip().split("\n") if result_str.strip() else []
                            result_str = f"{len(lines)} 行"
                        elif pipe_cmd in ("sort",):
                            result_str = "\n".join(sorted(result_str.split("\n")))
                        elif pipe_cmd in ("uniq",):
                            seen = set()
                            uniq_lines = []
                            for ln in result_str.split("\n"):
                                if ln not in seen:
                                    seen.add(ln)
                                    uniq_lines.append(ln)
                            result_str = "\n".join(uniq_lines)
                        else:
                            # 通用: 直接执行 OS 命令, 通过 stdin 传数据
                            import subprocess
                            try:
                                r = subprocess.run(
                                    __import__("butler.tui.os_command_adapter", fromlist=["resolve_command"]).resolve_command(pipe_cmd) + pipe_args,
                                    input=result_str, capture_output=True, text=True, timeout=30
                                )
                                result_str = r.stdout if r.stdout else "(无输出)"
                            except Exception:
                                self._append_chat(f"  | {pipe_cmd} (管道命令失败, 已跳过)", "system")
                    else:
                        self._append_chat(f"  | {pipe_cmd} (不支持的管道命令, 已跳过)", "system")

                # 重定向在管道之后
                if pipeline.redirect_to:
                    try:
                        with open(pipeline.redirect_to, "w", encoding="utf-8") as f:
                            f.write(result_str)
                        self._append_chat(f"✅ 输出已保存到 {pipeline.redirect_to}", "ok")
                    except Exception as e:
                        self._append_chat(f"❌ 写入失败: {e}", "error")
                else:
                    tag = "ok" if result.success else "error"
                    prefix = "" if result.success else f"❌ "
                    self._append_chat(f"{prefix}{result_str}", tag)
                return True

            # 无管道: 直接执行
            result = execute_os_command(cmd_name, args)
            tag = "ok" if result.success else "error"
            if result.success:
                self._append_chat(result.output, tag)
            else:
                self._append_chat(f"❌ {result.output}", tag)
            return True

        # 检查是否是 Butler 内置命令
        entry = _BY_NAME.get(cmd_name) or _BY_ALIAS.get(cmd_name)
        if not entry and cmd_name not in FLAG_REGISTRY:
            return False

        # 处理 --help / -h
        if first.flags.get("__help__"):
            flag_defs = FLAG_REGISTRY.get(cmd_name, [])
            help_text = format_help(
                cmd_name,
                entry.description if entry else "",
                entry.detail if entry else "",
                flag_defs,
                entry.example if entry else "",
            )
            self._append_chat(help_text, "system")
            return True

        # 查找 tool 映射
        tool_mapping = self._CMD_TO_TOOL.get(cmd_name)
        if not tool_mapping:
            return False

        tool_name, extra_params = tool_mapping
        flag_defs = FLAG_REGISTRY.get(cmd_name, [])
        params = merge_flags_with_defs(first, flag_defs)
        params.update(extra_params)

        # 处理 --no-dry-run 布尔开关
        if params.pop("no_dry_run", None):
            params["dry_run"] = False
        elif "dry_run" not in params:
            # 默认 dry_run=True (仅对需要它的命令)
            if tool_name in ("skill_uninstall_do", "skill_junk_clean"):
                params["dry_run"] = True

        # 处理 > 重定向
        if pipeline.redirect_to:
            result = self._execute_tool_capture(tool_name, params)
            if result is not None:
                try:
                    with open(pipeline.redirect_to, "w", encoding="utf-8") as f:
                        f.write(str(result))
                    self._append_chat(f"✅ 输出已保存到 {pipeline.redirect_to}", "ok")
                except Exception as e:
                    self._append_chat(f"❌ 写入文件失败: {e}", "error")
            return True

        # 处理 | 管道
        if len(pipeline.stages) > 1:
            result = self._execute_tool_capture(tool_name, params)
            if result is not None:
                result_str = str(result)
                # 将结果传递给后续管道命令
                for i, stage in enumerate(pipeline.stages[1:], 1):
                    pipe_cmd = stage.name.lower()
                    if pipe_cmd in ("grep", "find", "filter"):
                        # 简易 grep: 按关键词过滤结果行
                        keyword = stage.positionals[0] if stage.positionals else ""
                        if stage.flags.get("i") or stage.flags.get("ignore-case"):
                            filtered = [ln for ln in result_str.split("\n")
                                        if keyword.lower() in ln.lower()]
                        else:
                            filtered = [ln for ln in result_str.split("\n")
                                        if keyword in ln]
                        result_str = "\n".join(filtered) if filtered else "(无匹配)"
                    elif pipe_cmd in ("head", "first"):
                        n = int(stage.positionals[0]) if stage.positionals else 10
                        result_str = "\n".join(result_str.split("\n")[:n])
                    elif pipe_cmd in ("tail", "last"):
                        n = int(stage.positionals[0]) if stage.positionals else 10
                        result_str = "\n".join(result_str.split("\n")[-n:])
                    elif pipe_cmd in ("wc", "count"):
                        lines = result_str.strip().split("\n")
                        result_str = f"{len(lines)} 行"
                    elif pipe_cmd in ("sort",):
                        result_str = "\n".join(sorted(result_str.split("\n")))
                    else:
                        self._append_chat(f"  | {pipe_cmd} (不支持管道命令, 已跳过)", "system")
                self._append_chat(result_str, "ai")
            return True

        # 普通单命令执行
        self._execute_tool(tool_name, params)
        return True

    def _execute_tool_capture(self, tool_name: str, params: dict) -> str | None:
        """执行工具并捕获输出文本 (不直接显示到聊天区)."""
        import io, contextlib
        captured = io.StringIO()
        # 临时替换 _append_chat 以捕获输出
        original_append = self._append_chat
        captured_lines = []
        def capture_append(text, tag="ai"):
            captured_lines.append(text)
        self._append_chat = capture_append
        try:
            self._execute_tool(tool_name, params)
        except Exception as e:
            captured_lines.append(f"❌ 执行异常: {e}")
        finally:
            self._append_chat = original_append
        return "\n".join(captured_lines) if captured_lines else None

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
            # ── 辅助工具命令 ──
            "tool_list": ("tool_list", lambda a: {}),
            "tool_run": ("tool_run", lambda a: self._parse_tool_run_input(a)),
            "tool_info": ("tool_info", lambda a: {"tool_name": a}),
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

    def _parse_tool_run_input(self, text: str) -> dict:
        """解析工具执行输入 (格式: <tool_name> --key value ...)."""
        if not text:
            return {"tool_name": ""}
        parts = text.strip().split()
        if not parts:
            return {"tool_name": ""}
        tool_name = parts[0]
        args = {}
        i = 1
        while i < len(parts):
            arg = parts[i]
            if arg.startswith('--'):
                key = arg[2:]
                if i + 1 < len(parts) and not parts[i + 1].startswith('--'):
                    args[key] = parts[i + 1]
                    i += 2
                else:
                    args[key] = True
                    i += 1
            elif arg.startswith('-'):
                key = arg[1:]
                if i + 1 < len(parts) and not parts[i + 1].startswith('-'):
                    args[key] = parts[i + 1]
                    i += 2
                else:
                    args[key] = True
                    i += 1
            else:
                i += 1
        return {"tool_name": tool_name, "arguments": args}

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

        # ── 命令解释/翻译/对比 (转发给 Linux 风格处理器) ──
        if name in ("cmd_explain", "explain", "cmd_translate", "cmd_compare", "compare",
                    "os_help", "oslist", "oscommands"):
            # 去掉 / 前缀, 用 Linux 解析器统一处理 (支持 -c / -t / -l 等选项)
            reconstructed = cmd[1:]
            if self._try_linux_command(reconstructed):
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
                "[bold cyan]🧰 技能工具箱 (Linux 风格, 无需 AI)[/bold cyan]\n\n"
                "[bold]文档处理:[/bold]\n"
                "  markitdown -i <文件> [-o <输出>]\n"
                "  docx_read -i <文件>\n"
                "  docx_create -o <路径> -t <标题> -c <内容>\n"
                "  pdf_extract -i <文件>\n"
                "  pdf_merge -i <文件1,文件2> -o <输出>\n"
                "  pdf_split -i <文件> [-o <目录>]\n"
                "  format_convert -i <输入> -f <docx|epub|png|html>\n\n"
                "[bold]压缩归档:[/bold]\n"
                "  archive_compress -o <输出> -t <目标> [-p <密码>]\n"
                "  archive_extract -i <压缩包> [-d <目录>] [-p <密码>]\n"
                "  archive_list -i <压缩包>\n\n"
                "[bold]系统管理:[/bold]\n"
                "  uninstaller [--action list|uninstall] [-n <软件名>]\n"
                "  uninstall_scan -n <软件名>\n"
                "  uninstall_do -n <软件名> [--no-dry-run]\n"
                "  junk_scan [--categories <类型>]\n"
                "  junk_clean [--no-dry-run]\n"
                "  sys_info\n"
                "  top_procs [-s cpu|memory] [-n <数量>]\n\n"
                "[bold]安装追踪 (3步流程):[/bold]\n"
                "  track_start    # 安装前快照\n"
                "  track_stop     # 安装后差异\n"
                "  track_clean    # 执行清理\n\n"
                "[bold]媒体与存储:[/bold]\n"
                "  media_scan\n"
                "  storage_hub [--action list]\n"
                "  cloud_list -d <云盘ID> [-p <路径>]\n"
                "  cloud_search -q <关键词>\n"
                "  cloud_transfer -s <源盘> -d <目标盘> -f <文件名>\n"
                "  cloud_status -t <任务ID>\n"
                "  cloud_duplicates\n\n"
                "[bold]剪贴板服务:[/bold]\n"
                "  clip_magic              # 启动\n"
                "  skill_stop -n clip_magic   # 停止\n"
                "  skill_status -n clip_magic # 状态\n"
                "  clip_history            # 历史\n\n"
                "[bold]安全测试:[/bold]\n"
                "  sec_scan -t <目标IP> [-p <端口>]\n"
                "  web_sec_test -t <URL> [-m recon|scan|full]\n\n"
                "[bold]管道与重定向:[/bold]\n"
                "  pdf_extract -i paper.pdf | grep keyword\n"
                "  sys_info > system_snapshot.txt\n"
                "  uninstaller | head 5\n\n"
                "[bold]帮助:[/bold]\n"
                "  任意命令 --help 或 -h 查看用法\n\n"
                "[bold cyan]🖥️ OS 原生命令 (跨平台)[/bold cyan]\n\n"
                "[bold]文件操作:[/bold]  ls cat cp mv rm mkdir touch pwd ln chmod\n"
                "[bold]搜索:[/bold]      find grep locate which whereis rg\n"
                "[bold]进程:[/bold]      ps top kill killall tasklist taskkill\n"
                "[bold]网络:[/bold]      ping ifconfig ipconfig netstat curl wget ssh nslookup\n"
                "[bold]系统:[/bold]      uname uptime free lscpu whoami env hostname date\n"
                "[bold]文本:[/bold]      echo sed awk sort uniq cut tr tee xargs jq wc diff\n"
                "[bold]包管理:[/bold]    apt brew pip winget\n"
                "[bold]压缩:[/bold]      tar zip unzip gzip\n"
                "[bold]macOS:[/bold]     open pbcopy pbpaste say defaults\n"
                "[bold]Windows:[/bold]   dir type copy move del systeminfo where findstr clip\n"
                "[bold]服务:[/bold]      systemctl crontab sudo nohup watch sleep\n\n"
                "[bold]OS 命令示例:[/bold]\n"
                "  ls -la /tmp\n"
                "  cat config.yaml | grep port\n"
                "  ping -c 4 8.8.8.8\n"
                "  ps aux | head 10\n"
                "  find / -name '*.py' 2>/dev/null | head 20\n"
                "  ls > files.txt\n"
                "  os_help                    # 列出所有支持的 OS 命令\n"
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
        self._append_chat("创建 Word 文档，请输入: -o <路径> -t <标题> -c <内容>", "system")
        self._pending_tool = "skill_docx_create"

    @on(Button.Pressed, "#skill-btn-pdf-extract")
    def _on_skill_pdf_extract(self, _event):
        self._prompt_and_execute("skill_pdf", "请输入 PDF 文件路径:")
        self._pending_tool = "skill_pdf"
        self._pending_tool_params = {"action": "extract_text"}

    @on(Button.Pressed, "#skill-btn-pdf-merge")
    def _on_skill_pdf_merge(self, _event):
        self._append_chat("合并 PDF，请输入: -i <文件1,文件2> -o <输出路径>", "system")
        self._pending_tool = "skill_pdf_merge"

    @on(Button.Pressed, "#skill-btn-pdf-split")
    def _on_skill_pdf_split(self, _event):
        self._prompt_and_execute("skill_pdf", "请输入要拆分的 PDF 文件路径:")
        self._pending_tool = "skill_pdf"
        self._pending_tool_params = {"action": "split"}

    @on(Button.Pressed, "#skill-btn-format-convert")
    def _on_skill_format_convert(self, _event):
        self._append_chat("格式转换，请输入: -i <输入文件> -f <docx|epub|png|html>", "system")
        self._pending_tool = "skill_format_convert"

    @on(Button.Pressed, "#skill-btn-archive-compress")
    def _on_skill_archive_compress(self, _event):
        self._append_chat("压缩文件，请输入: -o <输出路径> -t <目标> [-p <密码>]", "system")
        self._pending_tool = "skill_archive_compress"

    @on(Button.Pressed, "#skill-btn-archive-extract")
    def _on_skill_archive_extract(self, _event):
        self._append_chat("解压文件，请输入: -i <压缩包> [-d <目录>] [-p <密码>]", "system")
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
        self._append_chat("Web 安全测试，请输入: -t <URL> [-m recon|scan|full]", "system")
        self._pending_tool = "skill_web_sec_test"

    # ── 子操作按钮 ──
    @on(Button.Pressed, "#skill-btn-uninstall-scan")
    def _on_skill_uninstall_scan(self, _event):
        self._prompt_and_execute("skill_uninstall_scan", "请输入要扫描残留的软件名:")

    @on(Button.Pressed, "#skill-btn-uninstall-do")
    def _on_skill_uninstall_do(self, _event):
        self._append_chat("深度卸载，请输入: -n <软件名> [--no-dry-run]", "system")
        self._pending_tool = "skill_uninstall_do"

    @on(Button.Pressed, "#skill-btn-junk-scan")
    def _on_skill_junk_scan(self, _event):
        self._execute_tool("skill_junk_scan", {})

    @on(Button.Pressed, "#skill-btn-junk-clean")
    def _on_skill_junk_clean(self, _event):
        self._append_chat("清理垃圾，请输入: [--no-dry-run] (默认仅模拟)", "system")
        self._pending_tool = "skill_junk_clean"

    @on(Button.Pressed, "#skill-btn-sys-info")
    def _on_skill_sys_info(self, _event):
        self._execute_tool("skill_sys_info", {})

    @on(Button.Pressed, "#skill-btn-top-procs")
    def _on_skill_top_procs(self, _event):
        self._append_chat("Top 进程，请输入: [-s cpu|memory] [-n <数量>]", "system")
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
        self._append_chat("列出云盘文件，请输入: -d <云盘ID> [-p <路径>]", "system")
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
                from butler.core.skill_manager import SkillManager
                try:
                    sm = SkillManager()
                    sm.load_skills()
                    text = "🛠️ 已加载技能:\n"
                    for sid, manifest in sm.manifests.items():
                        text += f"  - {sid}: {manifest.get('description', 'N/A')}\n"
                    self._append_chat(text, "ai")
                except Exception as e:
                    self._append_chat(f"❌ 技能列表加载失败: {e}", "error")

            elif tool_name == "tool_list":
                try:
                    from butler.core.tool_bridge import list_tools
                    tools = list_tools()
                    text = "🔧 Butler 辅助工具:\n"
                    text += "═" * 40 + "\n"
                    always = [t for t in tools if t['permission_level'] == 'always_allow']
                    confirm = [t for t in tools if t['permission_level'] == 'require_confirm']
                    if always:
                        text += f"\n  🔓 自动执行 ({len(always)} 个):\n"
                        for t in always:
                            ro = "👁" if t.get('is_read_only') else "  "
                            ds = "💥" if t.get('is_destructive') else "  "
                            text += f"  {ro}{ds} {t['name']:<20} {t['description'][:50]}\n"
                    if confirm:
                        text += f"\n  🔐 需确认 ({len(confirm)} 个):\n"
                        for t in confirm:
                            ro = "👁" if t.get('is_read_only') else "  "
                            ds = "💥" if t.get('is_destructive') else "  "
                            text += f"  {ro}{ds} {t['name']:<20} {t['description'][:50]}\n"
                    text += f"\n  TOTAL {len(tools)} | 只读 {len([t for t in tools if t.get('is_read_only')])} | 破坏性 {len([t for t in tools if t.get('is_destructive')])}"
                    self._append_chat(text, "ai")
                except Exception as e:
                    self._append_chat(f"❌ 工具列表加载失败: {e}", "error")

            elif tool_name == "tool_run":
                tool_name = params.get("tool_name", "")
                tool_args = params.get("arguments", {})
                if not tool_name:
                    self._append_chat("用法: /tool_run <工具名> [--key value ...]", "system")
                    self._append_chat("示例: /tool_run read --path config.yaml", "system")
                    return
                try:
                    from butler.core.tool_bridge import ToolContext
                    ctx = ToolContext()
                    result = ctx.execute(tool_name, **tool_args)
                    if result.get('success'):
                        content = result.get('content', '')
                        self._append_chat(f"✅ {tool_name} 执行成功:\n{content[:3000]}", "ai")
                    else:
                        self._append_chat(f"❌ {tool_name} 执行失败: {result.get('error', 'Unknown')}", "error")
                except Exception as e:
                    self._append_chat(f"❌ 工具执行异常: {e}", "error")

            elif tool_name == "tool_info":
                tool_name = params.get("tool_name", "")
                if not tool_name:
                    self._append_chat("用法: /tool_info <工具名>", "system")
                    return
                try:
                    from butler.core.tool_bridge import ToolContext
                    ctx = ToolContext()
                    info = ctx.info(tool_name)
                    if info:
                        text = f"📋 工具详情: {tool_name}\n"
                        text += "─" * 40 + "\n"
                        text += f"  名称:       {info['name']}\n"
                        text += f"  描述:       {info['description']}\n"
                        text += f"  权限:       {info['permission_level']}\n"
                        text += f"  只读:       {'是' if info['is_read_only'] else '否'}\n"
                        text += f"  破坏性:     {'是' if info['is_destructive'] else '否'}\n"
                        text += f"  并发安全:   {'是' if info['is_concurrency_safe'] else '否'}\n"
                        schema = info.get('parameters_schema', {})
                        if schema and schema.get('properties'):
                            text += f"\n  参数定义:\n"
                            required = schema.get('required', [])
                            for pname, pdef in schema['properties'].items():
                                req = " (必填)" if pname in required else ""
                                ptype = pdef.get('type', 'string')
                                desc = pdef.get('description', '')
                                text += f"    - {pname} [{ptype}]{req}\n      {desc}\n"
                        self._append_chat(text, "ai")
                    else:
                        self._append_chat(f"❌ 工具 '{tool_name}' 未找到", "error")
                except Exception as e:
                    self._append_chat(f"❌ 获取工具信息失败: {e}", "error")

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
        self._skill_current_tab = "user"
        self._skill_selected_id = None

    @on(Tabs.TabActivated, "#skills-tab-user")
    def _on_skills_tab_user(self, event):
        self._skill_current_tab = "user"
        tree_user = self.query_existing("#skills-tree-user", Tree)
        tree_agent = self.query_existing("#skills-tree-agent", Tree)
        if tree_user:
            tree_user.display = True
        if tree_agent:
            tree_agent.display = False
        self._skill_selected_id = None
        self._update_skill_action_bar()

    @on(Tabs.TabActivated, "#skills-tab-agent")
    def _on_skills_tab_agent(self, event):
        self._skill_current_tab = "agent"
        tree_user = self.query_existing("#skills-tree-user", Tree)
        tree_agent = self.query_existing("#skills-tree-agent", Tree)
        if tree_user:
            tree_user.display = False
        if tree_agent:
            tree_agent.display = True
        self._skill_selected_id = None
        self._update_skill_action_bar()

    def _update_skill_action_bar(self):
        label = self.query_existing("#skill-selected-label", Label)
        btn_run = self.query_existing("#btn-skill-run", Button)
        btn_view = self.query_existing("#btn-skill-view", Button)

        if not self._skill_selected_id:
            if label:
                label.update("")
            if btn_run:
                btn_run.disabled = True
            if btn_view:
                btn_view.disabled = True
            return

        skill_id, access_level = self._skill_selected_id
        if label:
            tag = "🐍" if access_level == "user" else "📖"
            label.update(f"{tag} {skill_id}")
        if btn_run:
            btn_run.disabled = (access_level != "user")
        if btn_view:
            btn_view.disabled = False

    @on(Tree.NodeHighlighted, "#skills-tree-user")
    def _on_skill_tree_user_highlighted(self, event):
        node = event.node
        if node and hasattr(node, 'skill_id'):
            self._skill_selected_id = (node.skill_id, 'user')
            self._update_skill_action_bar()

    @on(Tree.NodeHighlighted, "#skills-tree-agent")
    def _on_skill_tree_agent_highlighted(self, event):
        node = event.node
        if node and hasattr(node, 'skill_id'):
            self._skill_selected_id = (node.skill_id, 'agent')
            self._update_skill_action_bar()

    @on(Button.Pressed, "#btn-skill-run")
    def _on_skill_run_clicked(self, _event):
        if not self._skill_selected_id:
            self._append_chat("请先从技能树中选择一个技能", "system")
            return
        skill_id, access_level = self._skill_selected_id
        if access_level != "user":
            self._append_chat(f"❌ {skill_id} 是 Agent 技能，只能通过 AI 对话调用", "error")
            return
        self._append_chat(f"▶ 正在运行技能: {skill_id}", "system")
        self._execute_tool(f"skill_{skill_id}", {"action": "run"})

    @on(Button.Pressed, "#btn-skill-view")
    def _on_skill_view_clicked(self, _event):
        if not self._skill_selected_id:
            self._append_chat("请先从技能树中选择一个技能", "system")
            return
        skill_id, access_level = self._skill_selected_id
        skills = self._discover_skills_local()
        if skill_id in skills:
            from butler.core.skill_registry import read_skill_contents
            path = skills[skill_id]
            contents = read_skill_contents(path)
            if contents:
                self._append_chat(f"📖 {skill_id} SKILL.md 指令:\n{'─' * 40}", "system")
                self._append_chat(contents[:2000], "ai")
            else:
                manifest_path = path / "manifest.json"
                if manifest_path.exists():
                    try:
                        data = json.loads(manifest_path.read_text(encoding='utf-8'))
                        self._append_chat(f"📖 {skill_id} manifest.json:\n{json.dumps(data, ensure_ascii=False, indent=2)}", "ai")
                    except Exception:
                        self._append_chat(f"❌ 读取 manifest.json 失败", "error")
                else:
                    self._append_chat(f"⚠️  {skill_id} 无 SKILL.md 或 manifest.json", "system")

    @on(Button.Pressed, "#btn-skill-info")
    def _on_skill_info_clicked(self, _event):
        if not self._skill_selected_id:
            self._append_chat("请先从技能树中选择一个技能", "system")
            return
        skill_id, access_level = self._skill_selected_id
        self._append_chat(f"📋 技能详情: {skill_id}", "system")
        meta = self._load_skill_meta_local(skill_id)
        if meta:
            access_info = "🐍 可调用技能" if access_level == "user" else "📖 Agent 技能 (AI-only)"
            self._append_chat(f"  类型: {access_info}", "ai")
            for key in ['name', 'version', 'description', 'author', 'format']:
                if meta.get(key):
                    self._append_chat(f"  {key}: {meta[key]}", "ai")
            if meta.get('actions'):
                self._append_chat(f"  动作: {', '.join(meta['actions'])}", "ai")
            if access_level == "agent":
                self._append_chat(f"  ⚠️  此技能无 Python 入口，仅能通过 AI 对话使用", "system")
                self._append_chat(f"     如需手动调用，需在目录中添加 main.py 或 __init__.py", "system")

    def _discover_skills_local(self) -> dict:
        from butler.core.skill_registry import discover_skills
        return discover_skills()

    def _load_skill_meta_local(self, skill_id: str) -> dict:
        from butler.core.skill_registry import get_skill
        result = get_skill(skill_id)
        if result is None:
            return {}
        path, meta = result
        return meta

    def _refresh_skills(self):
        tree_user = self.query_existing("#skills-tree-user", Tree)
        tree_agent = self.query_existing("#skills-tree-agent", Tree)
        if not tree_user or not tree_agent:
            return

        tree_user.reset("🐍 可调用技能 (用户可直接使用)")
        tree_agent.reset("📖 Agent 技能 (仅 AI 大模型可用)")
        tree_user.root.expand()
        tree_agent.root.expand()

        try:
            skills = self._discover_skills_local()
            user_count = 0
            agent_count = 0

            for skill_id in sorted(skills.keys()):
                path = skills[skill_id]
                meta = self._load_skill_meta_local(skill_id)
                has_py = meta.get('has_python', False)
                access_level = 'user' if has_py else 'agent'
                name = meta.get('name', skill_id)
                desc = meta.get('description', '无描述')
                version = meta.get('version', '?')

                if access_level == 'user':
                    node = tree_user.root.add(f"🐍 {skill_id} v{version}", expand=False)
                    node.skill_id = skill_id
                    node.add(f"名称: {name}")
                    node.add(f"描述: {desc}")
                    actions = meta.get('actions', [])
                    if actions:
                        node.add(f"动作: {', '.join(actions)}")
                    node.add(f"路径: {path}")
                    user_count += 1
                else:
                    node = tree_agent.root.add(f"📖 {skill_id} v{version}", expand=False)
                    node.skill_id = skill_id
                    node.add(f"名称: {name}")
                    node.add(f"描述: {desc}")
                    keywords = meta.get('keywords', [])
                    if keywords:
                        node.add(f"关键词: {', '.join(keywords)}")
                    node.add(f"⚠️ 纯指令集，无 Python 入口")
                    node.add(f"路径: {path}")
                    agent_count += 1

            tree_user.root.add(f"── 共 {user_count} 个可调用技能 ──")
            tree_agent.root.add(f"── 共 {agent_count} 个 Agent 技能 ──")

        except Exception as e:
            tree_user.root.add(f"(技能加载失败: {e})")
            tree_agent.root.add(f"(技能加载失败: {e})")

    @on(Button.Pressed, "#btn-refresh-skills")
    def _on_refresh_skills(self, _event):
        self._refresh_skills()

    # ------------------------ Tools View (辅助工具) ------------------------ #

    def _init_tools2_view(self):
        self._refresh_tools()
        self._tool_selected = None
        filter_select = self.query_existing("#tool-filter", Select)
        if filter_select:
            filter_select.set_options([
                ("全部", ""),
                ("自动执行", "always_allow"),
                ("需确认", "require_confirm"),
            ])

    def _refresh_tools(self):
        table = self.query_existing("#tools-table", DataTable)
        if not table:
            return
        table.clear(columns=True)
        table.add_columns("工具名", "描述", "权限", "只读", "破坏性")

        try:
            from butler.core.tool_bridge import list_tools
            tools = list_tools()
            for t in tools:
                perm_icon = "🔓" if t['permission_level'] == 'always_allow' else "🔐"
                ro = "👁" if t.get('is_read_only') else "✏️"
                ds = "💥" if t.get('is_destructive') else ""
                table.add_row(
                    t['name'],
                    t['description'][:45],
                    f"{perm_icon} {t['permission_level']}",
                    ro,
                    ds,
                )
        except Exception as e:
            table.add_row("(工具加载失败)", str(e), "", "", "")

    @on(Button.Pressed, "#btn-refresh-tool-list")
    def _on_refresh_tools(self, _event):
        self._refresh_tools()

    @on(DataTable.CellSelected, "#tools-table")
    def _on_tool_selected(self, event):
        table = self.query_existing("#tools-table", DataTable)
        if not table:
            return
        row = event.row
        if row < len(table.get_column(0)):
            name = table.get_column(0)[row]
            self._tool_selected = name
            label = self.query_existing("#tool-selected-label", Label)
            if label:
                label.update(f"已选择: {name}")

    @on(Button.Pressed, "#btn-tool-info")
    def _on_tool_info(self, _event):
        if not self._tool_selected:
            self._append_chat("请先从列表中选择一个工具", "system")
            return
        name = self._tool_selected
        self._append_chat(f"🔧 工具详情: {name}", "system")
        try:
            from butler.core.tool_bridge import ToolContext
            ctx = ToolContext()
            info = ctx.info(name)
            if info:
                self._append_chat(f"  描述: {info['description']}", "ai")
                self._append_chat(f"  权限: {info['permission_level']}", "ai")
                self._append_chat(f"  只读: {'是' if info['is_read_only'] else '否'}", "ai")
                self._append_chat(f"  破坏性: {'是' if info['is_destructive'] else '否'}", "ai")
                schema = info.get('parameters_schema', {})
                if schema.get('properties'):
                    self._append_chat(f"  参数:", "ai")
                    required = schema.get('required', [])
                    for pname, pdef in schema['properties'].items():
                        req = " (必填)" if pname in required else ""
                        self._append_chat(f"    - {pname} [{pdef.get('type', 'string')}]{req}: {pdef.get('description', '')}", "ai")
        except Exception as e:
            self._append_chat(f"❌ 获取工具信息失败: {e}", "error")

    @on(Button.Pressed, "#btn-tool-run")
    def _on_tool_run(self, _event):
        if not self._tool_selected:
            self._append_chat("请先从列表中选择一个工具", "system")
            return
        name = self._tool_selected
        self._append_chat(f"▶ 执行工具: {name}", "system")
        try:
            from butler.core.tool_bridge import ToolContext
            ctx = ToolContext()
            result = ctx.execute(name)
            if result.get('success'):
                content = result.get('content', '')
                self._append_chat(f"✅ 执行成功\n{content[:2000]}", "ai")
            else:
                self._append_chat(f"❌ 执行失败: {result.get('error', 'Unknown')}", "error")
        except Exception as e:
            self._append_chat(f"❌ 执行异常: {e}", "error")

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
