"""本地 OCR 能力（可选组件）。

优先级：
  1. PaddleOCR（中文识别效果最好）
  2. pytesseract + 系统 tesseract 二进制
  3. 都没有 → 抛出 OCRUnavailable，由上层给用户明确提示

设计为【可选依赖】：不安装任何 OCR 也能用文本/PDF 翻译，
只有 translate.image / 截图翻译需要它。
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("butler.translate.ocr")


class OCRUnavailable(RuntimeError):
    """没有可用的 OCR 引擎。"""


@dataclass
class OCRWord:
    text: str
    bbox: dict = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class OCRResult:
    text: str
    confidence: float = 0.0
    words: List[OCRWord] = field(default_factory=list)


class OcrEngine:
    """惰性初始化的 OCR 引擎。"""

    def __init__(self) -> None:
        self._engine = None
        self._kind: Optional[str] = None

    @property
    def available(self) -> bool:
        try:
            self._ensure()
            return True
        except OCRUnavailable:
            return False

    @property
    def kind(self) -> Optional[str]:
        self._ensure()
        return self._kind

    def _ensure(self) -> None:
        if self._engine is not None:
            return

        # 1) PaddleOCR
        try:
            from paddleocr import PaddleOCR  # type: ignore

            self._engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            self._kind = "paddleocr"
            logger.info("OCR engine: PaddleOCR")
            return
        except Exception as exc:  # noqa: BLE001
            logger.debug("PaddleOCR 不可用: %s", exc)

        # 2) pytesseract
        try:
            import pytesseract  # type: ignore  # noqa: F401

            self._engine = "pytesseract"
            self._kind = "pytesseract"
            logger.info("OCR engine: pytesseract")
            return
        except Exception as exc:  # noqa: BLE001
            logger.debug("pytesseract 不可用: %s", exc)

        raise OCRUnavailable(
            "未安装 OCR 引擎。请安装其一后重试：\n"
            "  pip install paddleocr paddlepaddle     # 推荐，中文识别最佳\n"
            "  pip install pytesseract                # 需要系统安装 tesseract\n"
            "也可以在浏览器扩展端使用本地 tesseract.js（无需后端）。"
        )

    # ---------- 对外接口 ----------

    def recognize(self, image_bytes: bytes) -> OCRResult:
        """识别图片字节中的文字。"""
        self._ensure()

        if self._kind == "paddleocr":
            return self._run_paddle(image_bytes)
        return self._run_pytesseract(image_bytes)

    def recognize_base64(self, data: str) -> OCRResult:
        """识别 base64（可带 data: 前缀）中的文字。"""
        if "," in data and data.strip().startswith("data:"):
            data = data.split(",", 1)[1]
        return self.recognize(base64.b64decode(data))

    # ---------- 实现 ----------

    def _run_paddle(self, image_bytes: bytes) -> OCRResult:
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        result = self._engine.ocr(np.array(img), cls=True)

        words: List[OCRWord] = []
        lines: List[str] = []
        confs: List[float] = []

        for page in result or []:
            for item in page or []:
                # item = [box, (text, conf)]
                try:
                    box, (text, conf) = item[0], item[1]
                except (IndexError, TypeError, ValueError):
                    continue
                text = (text or "").strip()
                if not text:
                    continue
                lines.append(text)
                confs.append(float(conf or 0.0))
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                words.append(
                    OCRWord(
                        text=text,
                        bbox={"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys)},
                        confidence=float(conf or 0.0),
                    )
                )

        return OCRResult(
            text="\n".join(lines),
            confidence=(sum(confs) / len(confs)) if confs else 0.0,
            words=words,
        )

    def _run_pytesseract(self, image_bytes: bytes) -> OCRResult:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        img = Image.open(io.BytesIO(image_bytes))
        data = pytesseract.image_to_data(img, lang="chi_sim+eng", output_type=pytesseract.Output.DICT)

        words: List[OCRWord] = []
        lines: List[str] = []
        confs: List[float] = []

        for i, text in enumerate(data.get("text", [])):
            text = (text or "").strip()
            if not text:
                continue
            try:
                conf = float(data["conf"][i])
            except (KeyError, TypeError, ValueError):
                conf = -1.0
            lines.append(text)
            confs.append(max(conf, 0.0))
            words.append(
                OCRWord(
                    text=text,
                    bbox={
                        "x0": data["left"][i],
                        "y0": data["top"][i],
                        "x1": data["left"][i] + data["width"][i],
                        "y1": data["top"][i] + data["height"][i],
                    },
                    confidence=max(conf, 0.0),
                )
            )

        return OCRResult(
            text=" ".join(lines),
            confidence=(sum(confs) / len(confs)) if confs else 0.0,
            words=words,
        )


# 模块级单例
ocr_engine = OcrEngine()
