"""AI 专家 / 行业身份预设。

内置 7 套可编辑的 prompt 模板：通用 / 技术文档 / 法律合同 / 金融研报 /
医学文献 / 文学小说 / 游戏本地化。每套含：身份设定、语气、术语倾向、
数字/单位/代码处理规则。

支持：
- 自定义预设（保存到 data_dir/presets/*.json）
- 从 JSON 导入 / 导出
- 与术语约束（Glossary.render_prompt_rules）组合进最终 system prompt
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Preset:
    """一个翻译身份预设。"""

    id: str
    name: str
    identity: str          # 身份设定
    tone: str              # 语气 / 文风
    terminology: str       # 术语倾向
    rules: List[str] = field(default_factory=list)  # 数字/单位/代码等处理规则
    builtin: bool = False  # 内置预设不可删除

    def render(self, target_lang_name: str = "目标语言") -> str:
        """渲染为 system prompt 片段。"""
        lines = [
            f"你是一名{self.identity}，正在将文本翻译为{target_lang_name}。",
            f"语气与文风：{self.tone}",
            f"术语倾向：{self.terminology}",
        ]
        if self.rules:
            lines.append("处理规则：")
            for rule in self.rules:
                lines.append(f"- {rule}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "identity": self.identity,
            "tone": self.tone,
            "terminology": self.terminology,
            "rules": list(self.rules),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Preset":
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            identity=str(data.get("identity", "专业译员")),
            tone=str(data.get("tone", "准确、自然、流畅")),
            terminology=str(data.get("terminology", "优先使用通用译法")),
            rules=[str(r) for r in data.get("rules", [])],
        )


# ---------- 内置预设 ----------

_BUILTIN_PRESETS: List[Preset] = [
    Preset(
        id="general",
        name="通用",
        identity="经验丰富的专业译员",
        tone="准确、自然、流畅，避免翻译腔",
        terminology="优先使用目标语言中最通用、最常见的译法；无通用译法的专有名词保留原文",
        rules=[
            "数字、百分比、货币金额保持原样，不改变格式",
            "单位（kg、km、px 等）保留原文",
            "代码、变量名、命令、URL、文件路径一律不翻译",
            "原文中的换行、缩进、空白结构必须严格保留",
        ],
        builtin=True,
    ),
    Preset(
        id="tech",
        name="技术文档",
        identity="资深技术文档工程师，精通软件与硬件工程术语",
        tone="严谨、简洁、术语统一，符合技术文档写作规范",
        terminology=(
            "技术术语优先采用业界通行译法（如 Kubernetes→Kubernetes、middleware→中间件）；"
            "API 名称、命令、配置项保留原文并保持大小写"
        ),
        rules=[
            "代码块、命令行、配置片段一律不翻译",
            "变量名、函数名、文件路径、URL 保留原文",
            "数字与单位之间保留空格，单位不翻译",
            "被动语态可按目标语言技术文档习惯调整为主动语态",
            "中英文混排时，中文与英文/数字之间加半角空格",
        ],
        builtin=True,
    ),
    Preset(
        id="legal",
        name="法律合同",
        identity="持证法律翻译专家，熟悉大陆法系与普通法系合同文本",
        tone="正式、严谨、句式完整，符合法律文书规范",
        terminology=(
            "法律术语严格对齐目标语言法律体系的标准表述"
            "（如 indemnification→赔偿/补偿、jurisdiction→管辖权）；"
            "条款编号、定义术语（首字母大写词）保持原文写法"
        ),
        rules=[
            "shall/must/will 等情态动词按法律语境准确区分义务与权利",
            "条款编号（1.1、Article 3 等）原样保留",
            "机构名、法域名保留原文或使用官方译名",
            "数字金额同时保留原文写法，不擅自换算币种",
            "不简化、不意译，宁可直译也要保证法律效力等价",
        ],
        builtin=True,
    ),
    Preset(
        id="finance",
        name="金融研报",
        identity="资深金融行业分析师与财经翻译，熟悉资本市场术语",
        tone="专业、客观、数据驱动，符合财经媒体文风",
        terminology=(
            "金融术语使用目标语言市场通行说法"
            "（如 EPS→每股收益、bullish→看涨、liquidity→流动性）；"
            "公司名、股票代码、指数名称使用官方译名或保留原文"
        ),
        rules=[
            "所有数字、百分比、倍数、货币符号必须与原文完全一致，绝不出错",
            "财务单位（bn/mn、bps、YoY/QoQ）按目标语言财经惯例翻译或保留",
            "表格与数据对齐关系保持不变",
            "年份、季度、财年写法遵循目标语言惯例",
        ],
        builtin=True,
    ),
    Preset(
        id="medical",
        name="医学文献",
        identity="医学文献翻译专家，具备临床医学与药学背景",
        tone="客观、精确、符合医学论文写作规范",
        terminology=(
            "医学名词优先使用目标语言官方审定名词（如 WHO/全国科技名词委）；"
            "药名使用通用名（INN），不使用商品名；疾病、解剖名词保持全称规范译法"
        ),
        rules=[
            "药品剂量、浓度、给药途径必须逐字核对，绝不出错",
            "缩写词（如 RCT、CI、HR）首次出现可保留原文并附译名",
            "统计学符号（p、n、SD、OR）保留原文格式",
            "拉丁学名保持斜体原文，不翻译",
        ],
        builtin=True,
    ),
    Preset(
        id="literary",
        name="文学小说",
        identity="资深文学翻译家，擅长小说叙事文本的再创作",
        tone="文笔优美，贴合原文叙事风格与人物语气，可读性优先",
        terminology=(
            "人名、地名按目标语言文学翻译惯例处理（约定俗成的译名优先）；"
            "双关、隐喻在保证意思的前提下优先保留文学效果"
        ),
        rules=[
            "对话要贴合人物身份与口语习惯，避免翻译腔",
            "保留原文的段落节奏与句式张力",
            "诗歌、歌词等特殊文体按目标语言文学体裁处理",
            "文化专有项可在译文自然融入，不加脚注",
        ],
        builtin=True,
    ),
    Preset(
        id="game",
        name="游戏本地化",
        identity="游戏本地化专家，熟悉 RPG / FPS / 手游文本与玩家社区文化",
        tone="口语化、有代入感，符合游戏 UI 与剧情语境",
        terminology=(
            "技能名、装备名、NPC 称谓全篇统一；"
            "采用目标语言玩家社区的通用叫法（如 buff→增益、cooldown→冷却）"
        ),
        rules=[
            "UI 文本注意长度限制，尽量简短",
            "道具名保持名词短语风格，技能名可中二但要一致",
            "按键提示（如 Press [E]）中的按键、变量占位符（%s、{0}）原样保留",
            "粗口、俚语按目标语言游戏审查习惯适度本地化",
        ],
        builtin=True,
    ),
]


def builtin_presets() -> Dict[str, Preset]:
    return {p.id: p for p in _BUILTIN_PRESETS}


# ---------- 预设仓库（内置 + 用户自定义） ----------

class PresetStore:
    """预设仓库：内置预设 + data_dir/presets/ 下的用户自定义预设。"""

    def __init__(self, presets_dir: Optional[str] = None):
        self.presets_dir = Path(presets_dir) if presets_dir else None

    def _user_preset_files(self) -> List[Path]:
        if not self.presets_dir or not self.presets_dir.is_dir():
            return []
        return sorted(self.presets_dir.glob("*.json"))

    def load(self) -> Dict[str, Preset]:
        """加载全部预设（内置 + 自定义，自定义同 id 覆盖内置）。"""
        presets = builtin_presets()
        for path in self._user_preset_files():
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    p = Preset.from_dict(item)
                    p.builtin = False
                    presets[p.id] = p
            except (OSError, json.JSONDecodeError, KeyError):
                continue
        return presets

    def get(self, preset_id: str) -> Optional[Preset]:
        return self.load().get(preset_id)

    def save(self, preset: Preset) -> Path:
        """保存（或覆盖）一个自定义预设到 JSON 文件。"""
        if not self.presets_dir:
            raise ValueError("PresetsDir is not configured")
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        path = self.presets_dir / f"{_safe_filename(preset.id)}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(preset.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def delete(self, preset_id: str) -> bool:
        """删除自定义预设（内置预设不允许删除）。"""
        builtin = builtin_presets()
        if preset_id in builtin:
            return False
        path = self.presets_dir / f"{_safe_filename(preset_id)}.json" if self.presets_dir else None
        if path and path.exists():
            path.unlink()
            return True
        return False

    def export_json(self, preset_id: Optional[str] = None) -> str:
        """导出为 JSON 字符串；不指定 id 则导出全部。"""
        presets = self.load()
        if preset_id is not None:
            if preset_id not in presets:
                raise KeyError(preset_id)
            data = presets[preset_id].to_dict()
        else:
            data = [p.to_dict() for p in presets.values()]
        return json.dumps(data, ensure_ascii=False, indent=2)

    def import_json(self, text: str, save: bool = True) -> List[Preset]:
        """从 JSON 字符串导入一个或多个预设。"""
        data = json.loads(text)
        items = data if isinstance(data, list) else [data]
        imported: List[Preset] = []
        for item in items:
            p = Preset.from_dict(item)
            p.builtin = False
            imported.append(p)
            if save:
                self.save(p)
        return imported


def _safe_filename(preset_id: str) -> str:
    return re.sub(r"[^\w\-]", "_", preset_id)


# ---------- system prompt 组合 ----------

def compose_system_prompt(
    preset: Optional[Preset],
    glossary_rules: str = "",
    context_block: str = "",
    base_prompt: str = "",
    target_lang_name: str = "目标语言",
) -> str:
    """把「预设身份 + 术语约束 + 文档上下文」组合进最终 system prompt。"""
    parts: List[str] = []
    if preset is not None:
        parts.append(preset.render(target_lang_name))
    if context_block:
        parts.append(context_block)
    if glossary_rules:
        parts.append(glossary_rules)
    if base_prompt:
        parts.append(base_prompt)
    return "\n\n".join(parts)
