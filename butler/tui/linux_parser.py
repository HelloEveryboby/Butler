# -*- coding: utf-8 -*-
"""Linux 风格命令行解析器.

支持:
  - 短选项: -f value, -fvalue
  - 长选项: --flag value, --flag=value
  - 位置参数: cmd arg1 arg2
  - 引号: -t "title with spaces"
  - 管道: cmd1 | cmd2
  - 重定向: cmd > file.txt
  - 帮助: cmd --help, cmd -h
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FlagDef:
    """单个选项的定义."""
    short: str           # 如 "-i"
    long: str            # 如 "--input"
    dest: str            # 参数名, 如 "input"
    help: str            # 说明
    required: bool = False
    is_bool: bool = False  # 布尔开关 (如 --dry-run, 不需要值)


@dataclass
class ParsedCommand:
    """解析后的单条命令."""
    name: str                              # 命令名 (不含 /)
    flags: dict = field(default_factory=dict)  # 选项值 {dest: value}
    positionals: list = field(default_factory=list)  # 位置参数
    raw: str = ""                          # 原始文本


@dataclass
class Pipeline:
    """完整的管道命令行."""
    stages: list[ParsedCommand]            # 各阶段命令
    redirect_to: Optional[str] = None      # 重定向目标文件


def tokenize(line: str) -> list[str]:
    """用 shlex 分词, 支持引号."""
    try:
        return shlex.split(line)
    except ValueError:
        # 引号不匹配时退化为空格分词
        return line.split()


def parse_pipeline(line: str) -> Pipeline:
    """解析完整命令行, 支持 | 管道和 > 重定向.

    示例:
      "pdf_extract paper.pdf > out.txt"
      "pdf_extract paper.pdf | grep keyword"
      "archive_compress -o backup.7z -t /docs -p secret"
    """
    # 按管道和重定向分割 (保留分隔符用于判断)
    tokens = tokenize(line)

    stages: list[ParsedCommand] = []
    current_tokens: list[str] = []
    redirect_to = None
    in_redirect = False

    for tok in tokens:
        if tok == "|" and not in_redirect:
            if current_tokens:
                stages.append(_parse_stage(current_tokens))
                current_tokens = []
        elif tok == ">" and not in_redirect:
            if current_tokens:
                stages.append(_parse_stage(current_tokens))
                current_tokens = []
            in_redirect = True
        elif in_redirect:
            redirect_to = tok
            in_redirect = False
        else:
            current_tokens.append(tok)

    if current_tokens:
        stages.append(_parse_stage(current_tokens))

    return Pipeline(stages=stages, redirect_to=redirect_to)


def _parse_stage(tokens: list[str]) -> ParsedCommand:
    """解析单个命令阶段为 name + flags + positionals."""
    if not tokens:
        return ParsedCommand(name="")

    name = tokens[0].lstrip("/")  # 兼容旧的 / 前缀
    raw = " ".join(tokens)
    flags = {}
    positionals = []

    i = 1
    while i < len(tokens):
        tok = tokens[i]

        # --help / -h
        if tok in ("--help", "-h"):
            flags["__help__"] = True
            i += 1
            continue

        # --flag=value
        if tok.startswith("--") and "=" in tok:
            key, val = tok.split("=", 1)
            dest = key.lstrip("-")
            flags[dest] = val
            i += 1
            continue

        # --flag value  或  -f value
        if tok.startswith("-") and len(tok) > 1 and tok != "-":
            # 判断是否是布尔开关 (下一个 token 以 - 开头或不存在)
            if tok.startswith("--"):
                dest = tok.lstrip("-")
            else:
                dest = tok.lstrip("-")

            # 检查下一个 token 是否是值
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                flags[dest] = tokens[i + 1]
                i += 2
            elif i + 1 < len(tokens) and tokens[i + 1] == "-":
                # 值为 "-" (stdin)
                flags[dest] = "-"
                i += 2
            else:
                # 布尔开关
                flags[dest] = True
                i += 1
            continue

        # -fvalue (短选项带值, 如 -ooutput.pdf)
        if tok.startswith("-") and len(tok) > 2 and not tok.startswith("--"):
            dest = tok[1]
            val = tok[2:]
            flags[dest] = val
            i += 1
            continue

        # 位置参数
        positionals.append(tok)
        i += 1

    return ParsedCommand(name=name, flags=flags, positionals=positionals, raw=raw)


def merge_flags_with_defs(parsed: ParsedCommand, flag_defs: list[FlagDef]) -> dict:
    """将解析结果与选项定义合并, 支持短/长选项映射到 dest.

    返回 dict, key 为 dest 名.
    """
    result = {}

    # 建立 短/长 → dest 的映射
    short_map = {}  # {"i": "input", "o": "output"}
    long_map = {}   # {"input": "input", "output": "output"}
    for fd in flag_defs:
        if fd.short:
            short_map[fd.short.lstrip("-")] = fd.dest
        if fd.long:
            long_map[fd.long.lstrip("-")] = fd.dest

    # 映射 flags
    for key, val in parsed.flags.items():
        if key == "__help__":
            result["__help__"] = True
            continue
        if key in long_map:
            result[long_map[key]] = val
        elif key in short_map:
            result[short_map[key]] = val
        else:
            # 未知选项, 保留原始 key
            result[key] = val

    # 位置参数映射到第一个未填充的 required dest
    pos_idx = 0
    for fd in flag_defs:
        if fd.dest not in result and pos_idx < len(parsed.positionals):
            result[fd.dest] = parsed.positionals[pos_idx]
            pos_idx += 1

    # 剩余位置参数
    if pos_idx < len(parsed.positionals):
        result["__positionals__"] = parsed.positionals[pos_idx:]

    return result


def format_help(name: str, description: str, detail: str,
                flag_defs: list[FlagDef], example: str = "") -> str:
    """生成 --help 输出文本."""
    lines = [
        f"用法: {name} [选项] [参数]",
        f"",
        f"  {description}",
        f"",
    ]

    if flag_defs:
        lines.append("选项:")
        for fd in flag_defs:
            req = " (必填)" if fd.required else ""
            if fd.is_bool:
                lines.append(f"  {fd.short}, {fd.long:<16} {fd.help}{req}")
            else:
                short = fd.short or "  "
                lines.append(f"  {short}, {fd.long:<16} {fd.help}{req}")
        lines.append("")

    if detail:
        lines.append(f"说明:")
        for ln in detail.split("\n"):
            lines.append(f"  {ln}")
        lines.append("")

    if example:
        lines.append(f"示例:")
        lines.append(f"  {example}")
        lines.append("")

    lines.append(f"  -h, --help     显示此帮助信息")

    return "\n".join(lines)
