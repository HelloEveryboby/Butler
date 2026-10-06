"""翻译系统引擎：统一编排 Provider + 缓存 + 术语表 + 历史 + 翻译记忆 + AI 上下文。"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from .cache import TranslationCache
from .config import ProviderConfig, TranslateSystemConfig
from .context import (
    ContextBuildError,
    ContextCache,
    build_context,
    render_context_block,
)
from .glossary import Glossary
from .history import TranslationHistory
from .languages import detect_language, lang_name
from .presets import Preset, PresetStore, compose_system_prompt
from .providers import (
    FallbackProvider,
    TranslationProvider,
    create_provider,
)
from .tm import TranslationMemory

logger = logging.getLogger("butler.translate.engine")


# ---------- 译文可信度校验 ----------
# 真实事故：一个 mock 翻译上游把原文加上「[译文]」前缀原样回显，
# 结果被当成正式产出写进缓存和翻译记忆库，之后所有下游导出
# 都在“成功”地输出假译文。这里做一次入库前的真伪门禁。

_TARGET_SCRIPT_RE = {
    "zh": re.compile(r"[\u4e00-\u9fff]"),
    "ja": re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]"),
    "ko": re.compile(r"[\uac00-\ud7af]"),
    "ru": re.compile(r"[\u0400-\u04ff]"),
    "ar": re.compile(r"[\u0600-\u06ff]"),
    "th": re.compile(r"[\u0e00-\u0e7f]"),
    "el": re.compile(r"[\u0370-\u03ff]"),
    "he": re.compile(r"[\u0590-\u05ff]"),
}

# 抠掉原文后残留里的“纯噪音”字符（标点 / 括号 / 空白），用于判断剩余部分是否只是个标签
_LABEL_NOISE_RE = re.compile(
    r"[\s\[\]（）()<>《》：:，,。.!！?？、/\\\-—_\"'“”‘’…+*#&@]+"
)


def _norm_lang(code: Optional[str]) -> str:
    return (code or "").replace("_", "-").strip().lower()


def _target_script_re(target_lang: str) -> Optional[re.Pattern]:
    key = _norm_lang(target_lang).split("-", 1)[0]
    return _TARGET_SCRIPT_RE.get(key)


def is_trustworthy(original: str, translated: str, from_lang: str, to_lang: str) -> bool:
    """判断译文能否入库。

    同语种（或任一侧为空）不做要求；跨语种时：
      1. 译文与原文完全相同 → 不可信；
      2. 原文整串出现在译文里，且把原文抠掉后剩下的部分很短（≤ 12 个非标点字符）
         → 不可信。这正是事故特征：「[译文]Hello world」「Translation: Hello world」
         都只是给原文戴了顶帽子，并没有真翻译。

    刻意偏保守：宁可让某条真译文重译一次，也不让一条假译文进翻译记忆库。
    """
    src = (original or "").strip()
    dst = (translated or "").strip()
    if not src or not dst:
        return False
    if _norm_lang(from_lang) == _norm_lang(to_lang):
        return True
    if dst == src:
        return False

    if src in dst and len(src) >= 4:
        residual = _LABEL_NOISE_RE.sub("", dst.replace(src, ""))
        if len(residual) <= 12:
            return False

    # 3. 目标语言有已知字符集，译文里却一个对应字符都没有 → 不可信。
    #    （例：翻成中文却全是拉丁字母）
    pat = _target_script_re(to_lang)
    if pat is not None and len(src) >= 4 and not pat.search(dst):
        return False

    return True


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

        # 翻译记忆库（TM）：语义复用 + few-shot，降级链 Redis → Zvec → SQLite
        self.tm = TranslationMemory(str(data_dir / "tm.db"))

        # AI 上下文缓存（文档摘要 + 术语表，24h 有效）
        self.context_cache = ContextCache(str(data_dir / "context_cache.json"))
        self._doc_context: Optional[dict] = None

        # 最近一次调用中的可信度告警（供 CLI / 导出层向用户明示，
        # 避免“导出成功”却拿到假译文）
        self.last_warnings: List[str] = []

        # AI 专家 / 行业身份预设
        self.preset_store = PresetStore(str(data_dir / "presets"))
        self._preset_id = "general"

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
        # 离线模式：只允许本地源（local-llm），禁用所有远程 provider
        if self.config.offline_mode:
            enabled = [p for p in enabled if p.type == "local-llm"]
            if not enabled:
                raise RuntimeError(
                    "offline_mode is enabled but no local provider (type=local-llm) is available"
                )
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

    def _current_preset(self) -> Optional[Preset]:
        return self.preset_store.get(self._preset_id) or self.preset_store.get("general")

    def set_preset(self, preset_id: str) -> None:
        """切换 AI 专家 / 行业身份预设。"""
        self._preset_id = preset_id

    @property
    def preset_id(self) -> str:
        return self._preset_id

    def list_presets(self):
        return self.preset_store.load()

    def begin_document(self, full_text: str, to: Optional[str] = None) -> dict:
        """开始一篇文档的翻译：一次 LLM 调用构建上下文（摘要 + 术语表）。

        结果缓存 24h；术语写入 Glossary，后续 translate(use_context=True) 自动注入。
        """
        target = to or self.config.target_lang
        try:
            ctx = build_context(
                full_text, target,
                llm_fn=self._llm_chat,
                cache=self.context_cache,
            )
        except ContextBuildError:
            self._doc_context = None
            raise
        self._doc_context = ctx
        # 术语表同时写进 Glossary（双保险的另一条腿）
        terms = {t["source"]: t["target"] for t in ctx.get("terms", [])}
        if terms:
            self.glossary.add_many(terms)
        return ctx

    def _llm_chat(self, system_prompt: str, user_prompt: str) -> str:
        """供上下文构建使用的 LLM 对话调用。"""
        return self._provider.chat(system_prompt, user_prompt)

    def _prepare_prompt_extras(self, target: str, source_text: str = "",
                               use_context: bool = False) -> None:
        """组合「预设 + 文档上下文 + 术语约束」并注入 provider。

        成本控制：每篇文档只在 begin_document 多一次 LLM 调用；
        use_context=True 但没有 begin_document 时，对当前文本构建上下文（有缓存）。
        """
        context_block = ""
        if use_context:
            ctx = self._doc_context
            if ctx is None and source_text.strip():
                try:
                    ctx = build_context(
                        source_text, target,
                        llm_fn=self._llm_chat,
                        cache=self.context_cache,
                    )
                    self._doc_context = ctx
                    # 与 begin_document 一致：术语写进 Glossary
                    terms = {t["source"]: t["target"] for t in ctx.get("terms", [])}
                    if terms:
                        self.glossary.add_many(terms)
                except ContextBuildError:
                    ctx = None
            if ctx:
                context_block = render_context_block(ctx)

        extras = compose_system_prompt(
            preset=self._current_preset(),
            glossary_rules=self.glossary.render_prompt_rules(),
            context_block=context_block,
            target_lang_name=lang_name(target),
        )
        self._provider.set_prompt_extras(extras)

    def translate(
        self,
        text: str,
        to: Optional[str] = None,
        from_lang: str = "auto",
        use_cache: bool = True,
        record_history: bool = True,
        use_context: bool = False,
    ) -> str:
        """翻译单段文本。

        链路：缓存 → TM（语义复用 / few-shot）→ LLM → 术语兑底 → 回写 TM。
        """
        if not text or not text.strip():
            return text
        target = to or self.config.target_lang
        if from_lang == "auto":
            from_lang = detect_language(text)

        if use_cache and self.config.cache_enabled:
            cached = self.cache.get(text, target)
            if cached is not None:
                return cached

        # 翻译记忆：语义命中直接复用；相似命中作为 few-shot
        tm_result = self.tm.lookup(text, target, from_lang)
        if tm_result.reusable and tm_result.entry is not None:
            return tm_result.entry.target
        self._provider.set_fewshot(tm_result.fewshot)

        self._prepare_prompt_extras(target, source_text=text, use_context=use_context)
        try:
            translated = self._provider.translate(text, from_lang, target)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Translation failed: {e}") from e
        finally:
            self._provider.set_fewshot([])

        # 事后兑底：术语强制替换（单次正则，防连环替换）
        translated = self.glossary.apply(translated)

        # 真伪门禁：不可信的译文直接返回（不阻断链路），
        # 但绝不写缓存 / 历史 / 翻译记忆，避免一次性事故永久污染 TM。
        if not is_trustworthy(text, translated, from_lang, target):
            logger.warning(
                "译文未通过可信度校验，已跳过缓存与翻译记忆入库："
                "源语言=%s 目标语言=%s 原文=%r 译文=%r",
                from_lang, target, text[:80], translated[:80],
            )
            self.last_warnings.append("有译文未通过可信度校验（疑似未真正翻译），已跳过缓存/翻译记忆入库")
            return translated

        if self.config.cache_enabled:
            self.cache.set(text, target, translated, self._provider.name)
            self.cache.persist()

        if record_history:
            self.history.record(text, translated, from_lang, target, self._provider.name)

        # 回写翻译记忆库
        self.tm.record(text, translated, from_lang, target, self._provider.name)

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
            self._prepare_prompt_extras(target, source_text=miss_texts[0])
            try:
                translated = self._provider.translate_batch(miss_texts, det_from, target)
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"Batch translation failed: {e}") from e

            for i, (idx, original) in enumerate(zip(miss_indices, miss_texts)):
                value = translated[i] if i < len(translated) else original
                # 事后兑底：术语强制替换
                value = self.glossary.apply(value)
                results[idx] = value
                # 真伪门禁：不可信译文不入库（见 is_trustworthy）
                if not is_trustworthy(original, value, det_from, target):
                    logger.warning(
                        "批量译文未通过可信度校验，已跳过缓存与翻译记忆入库：%r -> %r",
                        original[:80], value[:80],
                    )
                    self.last_warnings.append(
                        "有译文未通过可信度校验（疑似未真正翻译），已跳过缓存/翻译记忆入库"
                    )
                    continue
                if self.config.cache_enabled:
                    self.cache.set(original, target, value, self._provider.name)
                self.tm.record(original, value, det_from, target, self._provider.name)
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
        # 按段落切分，保留每段原始内容（不 strip），仅过滤空段
        segments = re.split(r"\n\s*\n", text)
        segments = [s for s in segments if s.strip()]
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
