/* ============================================================
   术语表（Glossary）— 纯函数实现，便于单测
   ------------------------------------------------------------
   规则：
   1. 长词优先，避免短词先把长词吃掉（US vs USB）
   2. 拉丁/数字开头的词加词边界保护，避免 US → focus 变成 fo美国
   3. CJK 词不加边界（中文没有空格分词）
   4. 大小写不敏感，但替换值保持术语表里写死的大小写
   ============================================================ */

export interface GlossaryTerm {
  source: string;
  target: string;
}

/** 把一段正则元字符转义 */
function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** 是否是"词边界敏感"的词（拉丁字母 / 数字开头） */
function isWordBoundarySensitive(source: string): boolean {
  return /[A-Za-z0-9]/.test(source[0]);
}

/**
 * 应用术语表。
 *
 * 采用【单次正则替换】而不是逐条替换，从而保证：
 *  - 替换结果不会被后续术语二次替换（A→B 且 B→C 时，A 只变成 B）
 *  - 长词优先，短词不会误吃长词（US 不会命中 USB）
 *  - 词边界保护，US 不会命中 focus
 *
 * @param text   原文
 * @param glossary 术语表
 * @returns 替换后的文本
 */
export function applyGlossary(text: string, glossary: GlossaryTerm[]): string {
  if (!text || !glossary || glossary.length === 0) return text;

  // 去重 + 长词优先（决定 alternation 的匹配顺序）
  const seen = new Set<string>();
  const sorted = glossary
    .filter(g => g && g.source && g.target)
    .filter(g => {
      const key = g.source.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice()
    .sort((a, b) => b.source.length - a.source.length);

  if (sorted.length === 0) return text;

  // 小写 key → 译文（匹配时不区分大小写）
  const lookup = new Map<string, string>();
  for (const { source, target } of sorted) {
    lookup.set(source.toLowerCase(), target);
  }

  // 每个候选自带词边界（仅拉丁/数字词需要），合成一个正则，单次替换
  const alternatives = sorted.map(({ source }) => {
    const escaped = escapeRegExp(source);
    return isWordBoundarySensitive(source)
      ? `(?<![A-Za-z0-9])${escaped}(?![A-Za-z0-9])`
      : escaped;
  });
  const re = new RegExp(alternatives.join('|'), 'gi');

  return text.replace(re, (matched) => lookup.get(matched.toLowerCase()) ?? matched);
}
