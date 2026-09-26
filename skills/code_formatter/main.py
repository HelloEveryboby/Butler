"""Butler Code Formatter Skill - JSON/YAML/XML format, minify, validate, convert."""
import json
import re
from typing import Any, Dict, Optional

# 尝试导入 PyYAML
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

# 尝试导入 xml
import xml.dom.minidom
import xml.etree.ElementTree as ET


def _detect_format(text: str) -> str:
    """自动检测数据格式。"""
    stripped = text.strip()
    if not stripped:
        return "unknown"

    # JSON 检测
    if stripped[0] in "{[":
        try:
            json.loads(stripped)
            return "json"
        except json.JSONDecodeError:
            pass

    # XML 检测
    if stripped.startswith("<?xml") or stripped.startswith("<"):
        try:
            ET.fromstring(stripped)
            return "xml"
        except ET.ParseError:
            pass

    # YAML 检测（宽松）
    if _HAS_YAML:
        try:
            result = yaml.safe_load(stripped)
            if result is not None and not isinstance(result, (str, int, float)):
                return "yaml"
        except yaml.YAMLError:
            pass

    # 回退：尝试 JSON
    try:
        json.loads(stripped)
        return "json"
    except json.JSONDecodeError:
        pass

    return "unknown"


def format_json(text: str, indent: int = 2) -> str:
    """美化 JSON。"""
    data = json.loads(text)
    return json.dumps(data, indent=indent, ensure_ascii=False)


def minify_json(text: str) -> str:
    """压缩 JSON。"""
    data = json.loads(text)
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def validate_json(text: str) -> Dict:
    """校验 JSON。"""
    try:
        json.loads(text)
        return {"valid": True, "message": "JSON 格式合法。"}
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "message": f"JSON 解析错误：{e.msg}",
            "line": e.lineno,
            "column": e.colno,
        }


def format_xml(text: str, indent: int = 2) -> str:
    """美化 XML。"""
    dom = xml.dom.minidom.parseString(text)
    pretty = dom.toprettyxml(indent=" " * indent)
    # 去除多余空行
    lines = [line for line in pretty.split("\n") if line.strip()]
    return "\n".join(lines)


def minify_xml(text: str) -> str:
    """压缩 XML。"""
    dom = xml.dom.minidom.parseString(text)
    # 去除所有文本节点中的空白
    return re.sub(r">\s+<", "><", dom.toxml())


def validate_xml(text: str) -> Dict:
    """校验 XML。"""
    try:
        ET.fromstring(text)
        return {"valid": True, "message": "XML 格式合法。"}
    except ET.ParseError as e:
        return {
            "valid": False,
            "message": f"XML 解析错误：{e}",
        }


def format_yaml(text: str, indent: int = 2) -> str:
    """美化 YAML。"""
    if not _HAS_YAML:
        return "错误：PyYAML 未安装，无法处理 YAML。"
    data = yaml.safe_load(text)
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, indent=indent)


def minify_yaml(text: str) -> str:
    """压缩 YAML（转为 flow style）。"""
    if not _HAS_YAML:
        return "错误：PyYAML 未安装，无法处理 YAML。"
    data = yaml.safe_load(text)
    return yaml.dump(data, default_flow_style=True, allow_unicode=True)


def validate_yaml(text: str) -> Dict:
    """校验 YAML。"""
    if not _HAS_YAML:
        return {"valid": False, "message": "PyYAML 未安装。"}
    try:
        yaml.safe_load(text)
        return {"valid": True, "message": "YAML 格式合法。"}
    except yaml.YAMLError as e:
        return {"valid": False, "message": f"YAML 解析错误：{e}"}


def json_to_yaml(text: str) -> str:
    """JSON 转 YAML。"""
    if not _HAS_YAML:
        return "错误：PyYAML 未安装。"
    data = json.loads(text)
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


def yaml_to_json(text: str, indent: int = 2) -> str:
    """YAML 转 JSON。"""
    if not _HAS_YAML:
        return "错误：PyYAML 未安装。"
    data = yaml.safe_load(text)
    return json.dumps(data, indent=indent, ensure_ascii=False)


def handle_request(action: str, **kwargs) -> Any:
    """Butler 技能入口。"""
    text = kwargs.get("text") or kwargs.get("input") or kwargs.get("content", "")
    fmt = (kwargs.get("format") or kwargs.get("type") or "").lower()
    indent = int(kwargs.get("indent", 2))

    if not text:
        return "错误：请提供 text 参数。"

    if not fmt:
        fmt = _detect_format(text)
        if fmt == "unknown":
            return "错误：无法自动识别格式，请指定 format 参数 (json/yaml/xml)。"

    if action in ("format", "beautify", "run"):
        if fmt == "json":
            return format_json(text, indent)
        if fmt == "xml":
            return format_xml(text, indent)
        if fmt == "yaml":
            return format_yaml(text, indent)
        return f"错误：不支持的格式 '{fmt}'。"

    if action == "minify":
        if fmt == "json":
            return minify_json(text)
        if fmt == "xml":
            return minify_xml(text)
        if fmt == "yaml":
            return minify_yaml(text)
        return f"错误：不支持的格式 '{fmt}'。"

    if action in ("validate", "check"):
        if fmt == "json":
            return validate_json(text)
        if fmt == "xml":
            return validate_xml(text)
        if fmt == "yaml":
            return validate_yaml(text)
        return f"错误：不支持的格式 '{fmt}'。"

    if action == "convert":
        target = (kwargs.get("to") or kwargs.get("target", "")).lower()
        if fmt == "json" and target == "yaml":
            return json_to_yaml(text)
        if fmt == "yaml" and target == "json":
            return yaml_to_json(text, indent)
        return f"错误：不支持的转换 {fmt} -> {target}。"

    if action == "help" or not action:
        return (
            "### 🛠️ Butler 代码格式化器\n\n"
            "**美化** (action: `format`): text, format (json/yaml/xml, 自动检测), indent\n"
            "**压缩** (action: `minify`): text, format\n"
            "**校验** (action: `validate`): text, format\n"
            "**转换** (action: `convert`): text, format, to (目标格式)\n\n"
            "支持格式：JSON、YAML(需 PyYAML)、XML"
        )

    return f"未知动作: {action}"
