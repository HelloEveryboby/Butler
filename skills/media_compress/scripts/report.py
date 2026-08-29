"""
压缩报告生成
"""

import json
from typing import List, Dict, Any


def print_single_report(result: Dict[str, Any]) -> str:
    """单文件压缩报告"""
    if not result.get("success"):
        return f"❌ {result.get('input', '?')}: {result.get('error', '未知错误')}"

    lines = [
        f"✅ {result.get('input', '?')}",
        f"   {result.get('input_size_human', '?')} → {result.get('output_size_human', '?')}  "
        f"节省 {result.get('saved_bytes_human', '?')} ({result.get('saved_percent', 0)}%)",
        f"   模式: {result.get('mode', '?')}  工具: {result.get('tool', result.get('codec', '?'))}",
    ]

    w = result.get("new_width") or result.get("width")
    h = result.get("new_height") or result.get("height")
    if w and h:
        lines.append(f"   分辨率: {w}×{h}")

    lines.append(f"   输出: {result.get('output', '?')}")
    return "\n".join(lines)


def print_batch_report(results: List[Dict[str, Any]]) -> str:
    """批量压缩报告"""
    if not results:
        return "没有文件被处理"

    total_input = 0
    total_output = 0
    success = 0
    failed = 0

    lines = []
    lines.append("=" * 50)
    lines.append("📊 批量压缩报告")
    lines.append("=" * 50)

    for r in results:
        lines.append("")
        lines.append(print_single_report(r))

        if r.get("success"):
            success += 1
            total_input += r.get("input_size", 0)
            total_output += r.get("output_size", 0)
        else:
            failed += 1

    lines.append("")
    lines.append("=" * 50)
    lines.append(f"📁 共 {len(results)} 个文件: ✅ {success} 成功, ❌ {failed} 失败")

    if total_input > 0:
        saved = total_input - total_output
        percent = (saved / total_input) * 100
        lines.append(f"📦 原始总大小: {_human_size(total_input)}")
        lines.append(f"📦 压缩后总大小: {_human_size(total_output)}")
        lines.append(f"💰 总共节省: {_human_size(saved)} ({percent:.1f}%)")

    lines.append("=" * 50)
    return "\n".join(lines)


def print_analyze_report(info: Dict[str, Any]) -> str:
    """分析报告"""
    if info.get("error"):
        return f"❌ 分析失败: {info['error']}"

    lines = []
    lines.append(f"📄 {info.get('filename', '?')}")
    lines.append(f"   格式: {info.get('format', '?')}  模式: {info.get('mode', '?')}")
    lines.append(f"   分辨率: {info.get('width', '?')}×{info.get('height', '?')}  "
                 f"位深: {info.get('bit_depth', '?')}bit")

    has_exif = info.get("has_exif", False)
    has_alpha = info.get("has_alpha", False)
    lines.append(f"   EXIF: {'有' if has_exif else '无'}  "
                 f"Alpha通道: {'有' if has_alpha else '无'}")

    lines.append(f"   文件大小: {info.get('file_size_human', '?')}")
    lines.append(f"   ─────────────────────────────")

    est = info.get("estimate", {})
    for mode_name, label in [("lossless", "无损"), ("visual_lossless", "视觉无损"), ("high", "高压缩")]:
        e = est.get(mode_name, {})
        lines.append(f"   {label}: → {e.get('human', '?')} (节省 {e.get('saved_percent', 0)}%)")

    return "\n".join(lines)


def _human_size(size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
