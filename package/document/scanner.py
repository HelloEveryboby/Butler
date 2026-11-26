"""文档扫描 — 拍照/图片 → 电子版。

流水线：透视矫正 → 去阴影 → 增强（彩色/灰度/黑白/铅笔/碳笔）→ 保留彩色笔迹
→ 多页 PDF。可选 OCR 生成可搜索文字层。
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger("Scanner")

MODES = ("color", "gray", "bw", "pencil", "charcoal")


def _cv2():
    import cv2

    return cv2


def _np():
    import numpy as np

    return np


def _load_bgr(path: str | Path):
    img = _cv2().imread(str(path), _cv2().IMREAD_COLOR)
    if img is None:
        raise ValueError(f"无法读取图片: {path}")
    return img


def detect_document_quad(img) -> list[tuple[int, int]] | None:
    """检测纸张四角；失败返回 None（由调用方决定是否不矫正）。"""
    cv2 = _cv2()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    edges = cv2.dilate(edges, _np().ones((3, 3), _np().uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    min_area = img.shape[0] * img.shape[1] * 0.1
    for contour in contours:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(approx) > min_area:
            return [(int(p[0][0]), int(p[0][1])) for p in approx]
    return None


def _order_points(quad: Iterable[tuple[int, int]]):
    np = _np()
    points = np.array(list(quad), dtype="float32")
    ordered = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    ordered[0] = points[np.argmin(sums)]
    ordered[2] = points[np.argmax(sums)]
    diffs = np.diff(points, axis=1).ravel()
    ordered[1] = points[np.argmin(diffs)]
    ordered[3] = points[np.argmax(diffs)]
    return ordered


def warp_perspective(img, quad):
    """按四角做透视矫正。"""
    cv2 = _cv2()
    np = _np()
    rect = _order_points(quad)
    tl, tr, br, bl = rect
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if width < 10 or height < 10:
        return img
    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img, matrix, (width, height))


def remove_shadow(img):
    """背景估计除法去阴影。"""
    cv2 = _cv2()
    np = _np()
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    planes = list(cv2.split(rgb))
    for i, plane in enumerate(planes):
        background = cv2.dilate(plane, np.ones((7, 7), np.uint8))
        background = cv2.medianBlur(background, 21)
        diff = 255 - cv2.absdiff(plane, background)
        planes[i] = cv2.normalize(diff, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    return cv2.cvtColor(cv2.merge(planes), cv2.COLOR_RGB2BGR)


def enhance(img, mode: str = "color"):
    """按模式增强；返回 BGR 或灰度图。"""
    cv2 = _cv2()
    if mode not in MODES:
        raise ValueError(f"未知扫描模式: {mode}（可选 {', '.join(MODES)}）")

    if mode == "color":
        base = remove_shadow(img)
        lab = cv2.cvtColor(base, cv2.COLOR_BGR2LAB)
        l_chan, a_chan, b_chan = cv2.split(lab)
        l_chan = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l_chan)
        return cv2.cvtColor(cv2.merge([l_chan, a_chan, b_chan]), cv2.COLOR_LAB2BGR)

    gray = cv2.cvtColor(remove_shadow(img), cv2.COLOR_BGR2GRAY)
    if mode == "gray":
        return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    if mode == "bw":
        return cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12
        )
    if mode == "pencil":
        block = max(15, (min(gray.shape) // 40) | 1)
        return cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 8
        )
    # charcoal：保留炭笔浓淡层次
    stretched = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    gamma = 0.8
    table = _np().array(
        [((i / 255.0) ** gamma) * 255 for i in _np().arange(256)], dtype="uint8"
    )
    return cv2.LUT(stretched, table)


def preserve_ink(original, enhanced):
    """把原图中的高饱和彩色笔迹贴回增强底图。"""
    cv2 = _cv2()
    np = _np()
    base = enhanced
    if base.ndim == 2:
        base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    hsv = cv2.cvtColor(original, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] > 60) & (hsv[:, :, 2] > 40)).astype(np.uint8)
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    if base.shape[:2] != original.shape[:2]:
        return base
    result = base.copy()
    result[mask > 0] = original[mask > 0]
    return result


def process_image(path: str | Path, mode: str = "color", keep_ink: bool = True,
                  correct: bool = True):
    """单张图片 → RGB numpy（可直接交给 PIL）。

    若 BHL 注册了 ``scan_process_image`` 原生方法，优先使用其输出文件。
    """
    from butler.core.hybrid_accel import try_native

    native = try_native(
        "scan_process_image",
        {"path": str(path), "mode": mode, "keep_ink": keep_ink, "correct": correct},
    )
    if isinstance(native, dict) and native.get("output"):
        from PIL import Image

        with Image.open(native["output"]) as image:
            return _np().asarray(image.convert("RGB"))

    cv2 = _cv2()
    img = _load_bgr(path)
    if correct:
        quad = detect_document_quad(img)
        if quad:
            img = warp_perspective(img, quad)
    base = enhance(img, mode)
    if keep_ink and mode in ("color", "gray", "bw"):
        base = preserve_ink(img, base)
    if base.ndim == 2:
        base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    return cv2.cvtColor(base, cv2.COLOR_BGR2RGB)


def scan_images(
    paths: Iterable[str | Path],
    out_pdf: str | Path,
    mode: str = "color",
    keep_ink: bool = True,
    dpi: int = 200,
    correct: bool = True,
) -> dict:
    """把多张图片合并为一份 PDF；单页即普通 PDF。"""
    from PIL import Image

    image_paths = [Path(p) for p in paths]
    if not image_paths:
        raise ValueError("没有输入图片")

    pages = [
        Image.fromarray(process_image(p, mode=mode, keep_ink=keep_ink, correct=correct))
        for p in image_paths
    ]
    output = Path(out_pdf).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    first, rest = pages[0], pages[1:]
    first.save(output, "PDF", resolution=dpi, save_all=True, append_images=rest)
    return {"pages": len(pages), "output": str(output), "size": output.stat().st_size}


def scan_from_camera(
    out_pdf: str | Path,
    index: int = 0,
    mode: str = "color",
    keep_ink: bool = True,
    dpi: int = 200,
) -> dict:
    """调用摄像头拍一张并生成 PDF。"""
    cv2 = _cv2()
    capture = cv2.VideoCapture(index)
    if not capture.isOpened():
        raise RuntimeError(
            "无法打开摄像头（无设备或权限不足），请改用本地图片: butler scan <图片路径>"
        )
    try:
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok or frame is None:
        raise RuntimeError("摄像头未返回画面，请重试或改用本地图片")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as fh:
        temp_path = Path(fh.name)
    try:
        cv2.imwrite(str(temp_path), frame)
        return scan_images([temp_path], out_pdf, mode=mode, keep_ink=keep_ink, dpi=dpi)
    finally:
        temp_path.unlink(missing_ok=True)


def ocr_text(paths: Iterable[str | Path]) -> str:
    """对图片或 PDF 做 OCR，返回拼接文本。"""
    from package.document.translate_system.ocr import OcrEngine

    engine = OcrEngine()
    chunks: list[str] = []
    for item in paths:
        path = Path(item)
        if path.suffix.lower() == ".pdf":
            chunks.append(_pdf_text(path))
            continue
        chunks.append(engine.recognize(path.read_bytes()).text)
    return "\n".join(chunk for chunk in chunks if chunk)


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        logger.warning("PDF 文本提取失败: %s", exc)
        return ""
