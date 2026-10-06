/* ============================================================
   System Prompt 构造 — 纯函数，便于单测
   ------------------------------------------------------------
   「术语进 prompt + 事后 applyGlossary 兜底」双保险的前半部分：
   1. 术语强制约束：每条术语输出 `- "X" 必须译为 "Y"`
   2. 页面上下文（摘要 + 术语候选）拼进 system prompt
   3. 行业身份预设（身份/语气/术语倾向/数字单位代码规则）
   ============================================================ */

import { GlossaryEntry, PageContext, PresetTemplate, TranslateOptions } from '../utils/types';
import { buildPresetPrompt } from '../utils/presets';

/**
 * 术语强制约束片段。
 * 输出示例：
 *   术语强制约束（必须严格遵守）：
 *   - "API Gateway" 必须译为 "API 网关"
 */
export function buildGlossaryConstraint(glossary: GlossaryEntry[]): string {
  const valid = (glossary || []).filter(g => g && g.source && g.target);
  if (valid.length === 0) return '';
  const lines = valid.map(g => `- "${g.source}" 必须译为 "${g.target}"`);
  return `术语强制约束（必须严格遵守）：\n${lines.join('\n')}`;
}

/**
 * 合并术语表与页面术语候选：
 * - 术语表（用户词典）优先，同 source（忽略大小写）时覆盖候选
 * - 去重、长词优先（prompt 里顺序也长词优先，利于模型理解）
 */
export function mergeTerms(
  glossary: GlossaryEntry[],
  ctxTerms: GlossaryEntry[]
): GlossaryEntry[] {
  const map = new Map<string, GlossaryEntry>();
  for (const t of ctxTerms || []) {
    if (t && t.source && t.target) map.set(t.source.toLowerCase(), t);
  }
  for (const g of glossary || []) {
    if (g && g.source && g.target) map.set(g.source.toLowerCase(), g);
  }
  return Array.from(map.values()).sort((a, b) => b.source.length - a.source.length);
}

/**
 * 构造完整 system prompt。
 * @param basePrompt 基础翻译指令（含 {from} / {to} 占位符）
 */
export function buildSystemPrompt(
  basePrompt: string,
  fromName: string,
  toName: string,
  opts?: TranslateOptions
): string {
  const base = basePrompt.replace(/\{from\}/g, fromName).replace(/\{to\}/g, toName);
  const parts: string[] = [base];

  // 行业身份预设
  if (opts?.preset) {
    parts.push(buildPresetPrompt(opts.preset));
  }

  // 页面上下文
  const ctx = opts?.context;
  if (ctx?.summary) {
    parts.push(`页面上下文摘要（用于理解术语与指代，不要翻译此摘要）：\n${ctx.summary}`);
  }

  // 术语：合并候选与强制术语表（术语表优先）
  const merged = mergeTerms(opts?.glossary || [], ctx?.terms || []);
  if (merged.length > 0) {
    const constraint = buildGlossaryConstraint(merged);
    if (constraint) parts.push(constraint);
  }

  return parts.join('\n\n');
}

/* ---------- AI 上下文（页面摘要 + 术语） ---------- */

/** 上下文生成 prompt（严格 JSON 输出） */
export function buildContextPrompt(text: string, termCandidates: string[]): string {
  const candidates = termCandidates.length
    ? `\n\n术语候选（仅供参考）：${termCandidates.join('、')}`
    : '';
  return (
    `请阅读以下网页文本片段，输出严格 JSON（不要输出 JSON 以外的任何内容，不要用代码块包裹）：\n` +
    `{"summary": "用 2-3 句话概括页面主题与论述脉络", "terms": [{"source": "原文术语", "target": "建议中文译法"}]}\n` +
    `terms 数组给出 5-15 个全文应保持一致的术语（人名/机构/专业名词/产品名），target 为目标语言译法。${candidates}\n\n` +
    `网页文本：\n${text}`
  );
}

/**
 * 解析 LLM 返回的上下文 JSON（容错：允许代码块包裹 / 前后有解释文字）。
 * 解析失败返回 null（不阻塞翻译）。
 */
export function parseContextResponse(content: string): PageContext | null {
  if (!content) return null;
  // 优先取 ```json ... ``` 块，其次取第一个 {...} 对象
  let jsonStr = '';
  const fence = content.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fence) {
    jsonStr = fence[1].trim();
  } else {
    const start = content.indexOf('{');
    const end = content.lastIndexOf('}');
    if (start >= 0 && end > start) jsonStr = content.slice(start, end + 1);
  }
  if (!jsonStr) return null;

  try {
    const obj = JSON.parse(jsonStr);
    const summary = typeof obj.summary === 'string' ? obj.summary.trim() : '';
    const terms: GlossaryEntry[] = Array.isArray(obj.terms)
      ? obj.terms
          .filter((t: any) => t && typeof t.source === 'string' && typeof t.target === 'string')
          .map((t: any) => ({ source: t.source.trim(), target: t.target.trim() }))
          .filter((t: GlossaryEntry) => t.source && t.target)
      : [];
    if (!summary && terms.length === 0) return null;
    return { summary, terms };
  } catch {
    return null;
  }
}
