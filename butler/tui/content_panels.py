"""TUI 内容面板 — 通用朗读与文档扫描。

朗读面板订阅（轮询）ReadingService 状态，用反色高亮当前朗读句，
实现"读到哪里标到哪里"；扫描面板提供图片→PDF/OCR 的图形入口。
"""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static


class ReaderPanel(Vertical):
    """通用朗读面板：文件/URL/剪贴板 → 多音色朗读 + 高亮。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service = None
        self._segments = []
        self._last_index = -1

    def compose(self):
        yield Label("📖 通用朗读（文件 / 网页 / 剪贴板）", classes="tool-section-title")
        with Horizontal():
            yield Input(placeholder="文件路径或网页 URL（留空读取剪贴板）", id="reader-source")
            yield Button("加载", id="reader-load", variant="primary")
            yield Button("播放", id="reader-play", variant="success")
            yield Button("暂停", id="reader-pause")
            yield Button("停止", id="reader-stop", variant="error")
        with VerticalScroll(id="reader-scroll"):
            yield Static("尚未加载文本", id="reader-body")

    def on_mount(self) -> None:
        self.set_interval(0.6, self._tick)

    def _set_body(self, text: str) -> None:
        self.query_one("#reader-body", Static).update(text)

    @on(Button.Pressed, "#reader-load")
    def _load(self) -> None:
        source = self.query_one("#reader-source", Input).value.strip()
        try:
            from butler.core.reading import ReadingService

            if self._service is None:
                self._service = ReadingService()
            if source:
                self._service.open(source)
            else:
                from butler.core.reading.sources import read_clipboard

                self._service.open_text(read_clipboard(), name="剪贴板")
        except Exception as exc:
            self._set_body(f"❌ 加载失败: {exc}")
            return
        self._segments = self._service.book["segments"]
        self._last_index = -1
        self._render()

    @on(Button.Pressed, "#reader-play")
    def _play(self) -> None:
        if not self._service:
            self._set_body("请先加载文本")
            return
        try:
            self._service.start_background(resume=True)
        except Exception as exc:
            self._set_body(f"❌ {exc}")

    @on(Button.Pressed, "#reader-pause")
    def _toggle_pause(self) -> None:
        if not self._service:
            return
        status = self._service.status()
        if status.get("paused"):
            self._service.resume()
        else:
            self._service.pause()

    @on(Button.Pressed, "#reader-stop")
    def _stop(self) -> None:
        if self._service:
            self._service.stop()

    def _tick(self) -> None:
        if not self._service:
            return
        status = self._service.status()
        if not status.get("open"):
            return
        index = int(status.get("index", -1))
        if index != self._last_index:
            self._last_index = index
            self._render()

    def _render(self) -> None:
        from rich.text import Text

        if not self._segments:
            return
        text = Text()
        for segment in self._segments:
            if segment.index == self._last_index:
                style = "reverse"
            elif segment.kind == "dialogue":
                style = "bold cyan"
            else:
                style = ""
            speaker = f"{segment.speaker}: " if segment.kind == "dialogue" else ""
            text.append(f"{speaker}{segment.text}\n", style=style)
        self.query_one("#reader-body", Static).update(text)


class ScanPanel(Vertical):
    """文档扫描面板：图片 → PDF，保留彩色勾画，可 OCR。"""

    def compose(self):
        yield Label("🖨 文档扫描（图片 / 拍照 → PDF）", classes="tool-section-title")
        with Horizontal():
            yield Input(placeholder="图片路径，多个用逗号分隔", id="scan-paths")
            yield Select(
                [("彩色", "color"), ("灰度", "gray"), ("黑白", "bw"),
                 ("铅笔", "pencil"), ("碳笔", "charcoal")],
                value="color",
                id="scan-mode",
            )
        with Horizontal():
            yield Input(placeholder="输出 PDF 路径（默认 scan_output.pdf）", id="scan-out")
            yield Button("扫描", id="scan-run", variant="primary")
            yield Button("拍照", id="scan-camera")
        yield Static("等待扫描", id="scan-result")

    def _result(self, text: str) -> None:
        self.query_one("#scan-result", Static).update(text)

    def _options(self) -> dict:
        mode = self.query_one("#scan-mode", Select).value
        return {"mode": str(mode or "color"), "keep_ink": True}

    @on(Button.Pressed, "#scan-run")
    def _scan(self) -> None:
        raw = self.query_one("#scan-paths", Input).value.strip()
        paths = [item.strip() for item in raw.split(",") if item.strip()]
        if not paths:
            self._result("请填写图片路径")
            return
        out = self.query_one("#scan-out", Input).value.strip() or "scan_output.pdf"
        try:
            from package.document.scanner import scan_images

            result = scan_images(paths, out, **self._options())
        except Exception as exc:
            self._result(f"❌ 扫描失败: {exc}")
            return
        self._result(
            f"✅ 已生成 {Path(result['output']).name}（{result['pages']} 页，"
            f"{result['size']} 字节）"
        )

    @on(Button.Pressed, "#scan-camera")
    def _camera(self) -> None:
        out = self.query_one("#scan-out", Input).value.strip() or "scan_camera.pdf"
        try:
            from package.document.scanner import scan_from_camera

            result = scan_from_camera(out, **self._options())
        except Exception as exc:
            self._result(f"❌ 拍照失败: {exc}")
            return
        self._result(f"✅ 已生成 {Path(result['output']).name}")
