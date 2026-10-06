/* ============================================================
   文本工具 — 术语候选提取（纯函数）
   ------------------------------------------------------------
   从页面全文中提取「术语候选」，供 AI 上下文摘要使用：
   - 英文：2-3 词的专有名词/词组（首字母大写 或 含技术词）
   - 中文：2-6 字的高频词（简单 n-gram 频次）
   只做候选，不做决策 —— 最终术语由 LLM 结合上下文给出。
   ============================================================ */

/**
 * 提取术语候选。
 * @param text 页面全文（或前 N 字）
 * @param limit 最多返回条数
 * @returns 术语候选列表（source 为原文）
 */
export function extractTermCandidates(text: string, limit = 30): string[] {
  if (!text || !text.trim()) return [];
  const counts = new Map<string, number>();

  // 英文词组（2-3 词）：每个词首字母大写，或整体是已知缩写形态
  const phrases = text.match(/\b[A-Za-z][A-Za-z0-9+.#-]*(?:\s+[A-Za-z][A-Za-z0-9+.#-]*){1,2}\b/g) || [];
  for (const p of phrases) {
    const words = p.split(/\s+/);
    const isProper = words.some(w => /^[A-Z][a-z]+$/.test(w) || /^[A-Z]{2,}$/.test(w));
    if (!isProper) continue;
    // 过滤纯句子开头（the/This/The 等后接普通词）
    if (/^(The|This|That|These|Those|It|He|She|We|They|A|An)\s/.test(p)) continue;
    bump(counts, p, 3);
  }

  // 英文技术缩写（2+ 全大写字母，含数字/点）
  const acronyms = text.match(/\b[A-Z][A-Z0-9]{1,7}(?:[.+#-][A-Z0-9]+)*\b/g) || [];
  for (const a of acronyms) {
    if (a.length >= 2 && a.length <= 10) bump(counts, a, 2);
  }

  // 中文 2-4 字高频片段（排除常见虚词组合，简单频次过滤）
  const hanRuns = text.match(/[\u4e00-\u9fff]{2,4}/g) || [];
  for (const h of hanRuns) {
    bump(counts, h, 1);
  }

  return Array.from(counts.entries())
    .filter(([term, c]) => {
      if (c < 2 && /[\u4e00-\u9fff]/.test(term)) return false; // 中文至少出现 2 次
      return term.length >= 2;
    })
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([term]) => term);
}

function bump(map: Map<string, number>, key: string, weight: number): void {
  map.set(key, (map.get(key) || 0) + weight);
}
