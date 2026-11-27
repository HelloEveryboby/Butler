/* ============================================================
   译文可信度门禁（对齐 Python translate_system/engine.py:is_trustworthy）
   ------------------------------------------------------------
   真实事故：一个 mock 翻译上游把原文加上「[译文]」前缀原样回显，
   结果被当成正式产出写进缓存和翻译记忆库，之后所有下游导出都在
   “成功”地输出假译文。这里在入库前做一次真伪门禁。
   ============================================================ */

const TARGET_SCRIPT_RE: Record<string, RegExp> = {
  zh: /[\u4e00-\u9fff]/,
  ja: /[\u3040-\u30ff\u4e00-\u9fff]/,
  ko: /[\uac00-\ud7af]/,
  ru: /[\u0400-\u04ff]/,
  ar: /[\u0600-\u06ff]/,
  th: /[\u0e00-\u0e7f]/,
  el: /[\u0370-\u03ff]/,
  he: /[\u0590-\u05ff]/,
};

/** 抠掉原文后残留里的“纯噪音”字符（标点 / 括号 / 空白） */
const LABEL_NOISE_RE = /[\s\[\]（）()<>《》：:，,。.!！?？、/\\\-—_"'“”‘’…+*#&@]+/g;

function normLang(code?: string): string {
  return (code || '').replace(/_/g, '-').trim().toLowerCase();
}

function targetScriptRe(targetLang: string): RegExp | null {
  const key = normLang(targetLang).split('-')[0];
  return TARGET_SCRIPT_RE[key] ?? null;
}

/**
 * 判断译文能否入库。
 *
 * 同语种（或任一侧为空）不做要求；跨语种时：
 *   1. 译文与原文完全相同 → 不可信；
 *   2. 原文整串出现在译文里，且抠掉原文后剩余部分很短（≤ 12 个非标点字符）
 *      → 不可信（「[译文]Hello world」「Translation: Hello world」都是假翻译）；
 *   3. 目标语言有已知字符集，译文里却一个对应字符都没有 → 不可信。
 *
 * 刻意偏保守：宁可让某条真译文重译一次，也不让一条假译文进缓存。
 */
export function isTrustworthy(
  original: string,
  translated: string,
  fromLang: string,
  toLang: string
): boolean {
  const src = (original || '').trim();
  const dst = (translated || '').trim();
  if (!src || !dst) return false;
  if (normLang(fromLang) === normLang(toLang)) return true;
  if (dst === src) return false;

  if (src.length >= 4 && dst.includes(src)) {
    const residual = dst.split(src).join('').replace(LABEL_NOISE_RE, '');
    if (residual.length <= 12) return false;
  }

  const re = targetScriptRe(toLang);
  if (re && src.length >= 4 && !re.test(dst)) return false;

  return true;
}
