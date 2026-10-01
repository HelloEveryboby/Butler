"""翻译系统引擎：统一编排 Provider + 缓存 + 术语表 + 历史。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from .cache import TranslationCache
from .config import ProviderConfig, TranslateSystemConfig
from .glossary import Glossary
from .history import TranslationHistory
from .languages import detect_language
from .providers import (
    FallbackProvider,
    TranslationProvider,
    create_provider,
)


class TranslationSystem:
    """统一翻译系统。"""

    def __init__(self, config: Optional[TranslateSystemConfig] = None):
        self.config = config or TranslateSystemConfig()
        data_dir = Path(self.config.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        self.cache = TranslationCache(
            str(data_dir / "cache.json"),
            max_size=self.config.cache_max_size,
        )
        self.glossary = Glossary(str(data_dir / "glossary.json"))
        self.history = TranslationHistory(str(data_dir / "history.json"))

        self._provider = self._build_provider()

    # ---------- Provider 管理 ----------

    def _build_provider(self) -> TranslationProvider:
        chain = [
            self.config.providers[i] if isinstance(i, int) else self.config.get_provider(i)
            for i in self.config.fallback_chain
        ]
        enabled = [p for p in chain if p and p.enabled]
        if not enabled:
            # 回退到任意可用 provider
            enabled = [p for p in self.config.providers if p.enabled]
        if not enabled:
            raise RuntimeError("No enabled translation providers")
        providers = [create_provider(p) for p in enabled]
        return FallbackProvider(providers) if len(providers) > 1 else providers[0]

    def reload_providers(self) -> None:
        self._provider = self._build_provider()

    def set_active_provider(self, provider_id: str) -> None:
        """将指定 provider 移到降级链首位。"""
        chain = [provider_id] + [p for p in self.config.fallback_chain if p != provider_id]
        self.config.fallback_chain = chain
        self.reload_providers()

    def add_provider(self, provider: ProviderConfig) -> None:
        self.config.providers.append(provider)
        if provider.id not in self.config.fallback_chain:
            self.config.fallback_chain.append(provider.id)
        self.reload_providers()

    def remove_provider(self, provider_id: str) -> None:
        self.config.providers = [p for p in self.config.providers if p.id != provider_id]
        self.config.fallback_chain = [p for p in self.config.fallback_chain if p != provider_id]
        self.reload_providers()

    # ---------- 核心翻译 ----------

    def translate(
        self,
        text: str,
        to: Optional[str] = None,
        from_lang: str = "auto",
        use_cache: bool = True,
        record_history: bool = True,
    ) -> str:
        """翻译单段文本。"""
        if not text or not text.strip():
            return text
        target = to or self.config.target_lang
        if from_lang == "auto":
            from_lang = detect_language(text)

        if use_cache and self.config.cache_enabled:
            cached = self.cache.get(text, target)
            if cached is not None:
                return cached

        # 术语表：对原文做术语替换（对所有 provider 通用）
        processed = self.glossary.replace_in_text(text)

        try:
            translated = self._provider.translate(processed, from_lang, target)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Translation failed: {e}") from e

        if self.config.cache_enabled:
            self.cache.set(text, target, translated, self._provider.name)
            self.cache.persist()

        if record_history:
            self.history.record(text, translated, from_lang, target, self._provider.name)

        return translated

    def translate_batch(
        self,
        texts: List[str],
        to: Optional[str] = None,
        from_lang: str = "auto",
    ) -> List[str]:
        """批量翻译。"""
        if not texts:
            return []
        target = to or self.config.target_lang

        results: List[str] = [""] * len(texts)
        miss_indices: List[int] = []
        miss_texts: List[str] = []

        for idx, text in enumerate(texts):
            if not text.strip():
                results[idx] = text
                continue
            if self.config.cache_enabled:
                cached = self.cache.get(text, target)
                if cached is not None:
                    results[idx] = cached
                    continue
            miss_indices.append(idx)
            miss_texts.append(text)

        if miss_texts:
            det_from = detect_language(miss_texts[0]) if from_lang == "auto" else from_lang
            processed = [self.glossary.replace_in_text(t) for t in miss_texts]
            try:
                translated = self._provider.translate_batch(processed, det_from, target)
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"Batch translation failed: {e}") from e

            for i, (idx, original) in enumerate(zip(miss_indices, miss_texts)):
                value = translated[i] if i < len(translated) else original
                results[idx] = value
                if self.config.cache_enabled:
                    self.cache.set(original, target, value, self._provider.name)
            if self.config.cache_enabled:
                self.cache.persist()

        return results

    def translate_bilingual(
        self,
        text: str,
        to: Optional[str] = None,
        context: Optional[str] = None,
    ) -> List[dict]:
        """双语翻译，返回 [{source, target}, ...]。"""
        target = to or self.config.target_lang
        # 按段落切分
        segments = re.split(r"\n\s*\n", text.strip())
        segments = [s.strip() for s in segments if s.strip()]
        if not segments:
            return []

        translations = self.translate_batch(segments, to=target)
        result = []
        for src, tgt in zip(segments, translations):
            entry = {"source": src, "target": tgt}
            if context:
                entry["context"] = context
            result.append(entry)
        return result

    # ---------- 文件 / 网页 ----------

    def translate_file(self, input_file: str, output_file: Optional[str] = None,
                       to: Optional[str] = None) -> str:
        """翻译整个文件，返回输出路径。"""
        with open(input_file, "r", encoding="utf-8") as f:
            text = f.read()

        paragraphs = re.split(r"(\n\s*\n)", text)
        chunks: List[str] = []
        for part in paragraphs:
            if part.strip():
                chunks.append(part)

        translated = self.translate_batch(chunks, to=to)

        out_text = ""
        ti = 0
        for part in paragraphs:
            if part.strip():
                out_text += translated[ti] if ti < len(translated) else part
                ti += 1
            else:
                out_text += part

        if output_file is None:
            p = Path(input_file)
            output_file = str(p.with_suffix(".translated" + p.suffix))
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(out_text)
        return output_file

    def translate_website(self, url: str, to: Optional[str] = None) -> dict:
        """抓取网页并双语翻译。"""
        target = to or self.config.target_lang
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.extract()

            title = soup.title.string.strip() if soup.title and soup.title.string else url
            paragraphs = soup.find_all(["p", "h1", "h2", "h3", "li"])
            content = "\n\n".join(
                p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20
            )
            if len(content) > 4000:
                content = content[:4000] + "..."

            translated_title = self.translate(title, to=target)
            segments = self.translate_bilingual(content, to=target, context=f"URL: {url}")

            return {
                "title_source": title,
                "title_target": translated_title,
                "url": url,
                "segments": segments,
            }
        except Exception as e:  # noqa: BLE001
            return {
                "title_source": "Error",
                "title_target": f"无法访问或解析网页: {e}",
                "url": url,
                "segments": [],
            }

    # ---------- 术语表 / 历史 快捷方法 ----------

    def add_term(self, source: str, target: str) -> None:
        self.glossary.add(source, target)

    def remove_term(self, source: str) -> bool:
        return self.glossary.remove(source)

    def get_history(self, limit: Optional[int] = None):
        return self.history.all(limit)

    def clear_cache(self) -> None:
        self.cache.clear()
