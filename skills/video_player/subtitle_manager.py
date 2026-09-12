"""
字幕管理器 — 负责字幕文件的发现、加载和格式转换。
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SubtitleManager:
    """字幕管理器"""

    # 支持的字幕扩展名（按优先级排序）
    SUBTITLE_EXTENSIONS = [
        '.ass',     # Advanced SubStation Alpha（高质量特效字幕）
        '.ssa',     # SubStation Alpha
        '.srt',     # SubRip（最常见）
        '.vtt',     # WebVTT
        '.sub',     # MicroDVD
        '.idx',     # VobSub 索引
        '.sup',     # PGS 字幕
        '.lrc',     # 歌词
    ]

    # 语言代码映射
    LANG_MAP = {
        # 中文
        "chi": "中文", "zh": "中文", "chs": "简中", "cht": "繁中",
        "zhs": "简中", "zht": "繁中", "简中": "简中", "繁中": "繁中",
        "中文": "中文", "chinese": "中文", "mandarin": "中文",
        "简体": "简中", "繁体": "繁中", "sc": "简中", "tc": "繁中",
        # 英文
        "eng": "英语", "en": "英语", "english": "英语",
        # 日语
        "jpn": "日语", "ja": "日语", "japanese": "日语", "日语": "日语", "日文": "日语",
        # 韩语
        "kor": "韩语", "ko": "韩语", "korean": "韩语", "韩语": "韩语",
        # 法语
        "fre": "法语", "fr": "法语", "french": "法语",
        # 德语
        "ger": "德语", "de": "德语", "german": "德语",
        # 西班牙语
        "spa": "西语", "es": "西语", "spanish": "西语",
    }

    def find_subtitles(self, video_path: str) -> list[dict]:
        """
        查找视频的所有可用字幕。
        搜索范围：
        1. 同目录同名外挂字幕
        2. 同目录 subtitles/ 子目录
        3. 同目录 subs/ 子目录
        """
        results = []
        video_path = Path(video_path)
        video_dir = video_path.parent
        video_stem = video_path.stem

        # 1. 同目录同名字幕
        for ext in self.SUBTITLE_EXTENSIONS:
            # 匹配模式：
            #   video.srt          → 直接匹配
            #   video.chi.srt      → 带语言标签
            #   video.eng.srt      → 带语言标签
            #   video.chs.srt      → 简中
            #   video.zh.srt       → 中文
            #   video.简中.srt     → 中文标签
            candidates = list(video_dir.glob(f"{video_stem}*{ext}"))
            for f in candidates:
                if f == video_path:
                    continue
                # 提取语言标签
                remaining = f.stem.replace(video_stem, "").strip(".")
                lang = self._detect_language(remaining)
                results.append({
                    "path": str(f),
                    "filename": f.name,
                    "language": lang,
                    "language_code": remaining or "und",
                    "codec": ext.lstrip('.').lower(),
                    "is_external": True,
                    "source": "same_dir",
                })

        # 2. subtitles/ 和 subs/ 子目录
        for sub_dir_name in ["subtitles", "subs", "Subs", "Subtitles"]:
            sub_dir = video_dir / sub_dir_name
            if sub_dir.is_dir():
                for f in sub_dir.iterdir():
                    if f.suffix.lower() in self.SUBTITLE_EXTENSIONS and video_stem in f.stem:
                        remaining = f.stem.replace(video_stem, "").strip(".")
                        lang = self._detect_language(remaining)
                        results.append({
                            "path": str(f),
                            "filename": f.name,
                            "language": lang,
                            "language_code": remaining or "und",
                            "codec": f.suffix.lstrip('.').lower(),
                            "is_external": True,
                            "source": sub_dir_name,
                        })

        # 按语言偏好排序
        results.sort(key=lambda x: self._sort_key(x["language"]))
        return results

    def _detect_language(self, label: str) -> str:
        """从文件名标签检测语言"""
        if not label:
            return "未知"
        label_lower = label.lower().strip()
        # 直接映射
        if label_lower in self.LANG_MAP:
            return self.LANG_MAP[label_lower]
        # 部分匹配
        for key, name in self.LANG_MAP.items():
            if key in label_lower or label_lower in key:
                return name
        return label or "未知"

    def _sort_key(self, lang: str) -> int:
        """语言排序优先级（中文 > 英语 > 其他）"""
        priority = {"简中": 0, "繁中": 1, "中文": 2, "英语": 3, "日语": 4, "韩语": 5}
        return priority.get(lang, 99)

    def get_preferred_subtitle(self, video_path: str,
                                preferred_lang: str = "chi") -> Optional[str]:
        """
        获取首选字幕文件路径。
        :param video_path: 视频文件路径
        :param preferred_lang: 偏好语言代码
        :return: 字幕文件路径或 None
        """
        subtitles = self.find_subtitles(video_path)
        if not subtitles:
            return None

        # 优先匹配偏好语言
        preferred_names = self._get_lang_names(preferred_lang)
        for sub in subtitles:
            if sub["language"] in preferred_names:
                return sub["path"]

        # 降级：返回第一个字幕
        return subtitles[0]["path"]

    def _get_lang_names(self, lang_code: str) -> list[str]:
        """获取语言代码对应的显示名称列表"""
        names = []
        for key, name in self.LANG_MAP.items():
            if key.startswith(lang_code) or lang_code.startswith(key):
                if name not in names:
                    names.append(name)
        return names or ["中文", "简中"]

    def has_subtitle(self, video_path: str) -> bool:
        """检查视频是否有可用字幕"""
        return len(self.find_subtitles(video_path)) > 0
