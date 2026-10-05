/* ============================================================
   AI 上下文（Context）— 页面摘要 + 术语一致性
   ------------------------------------------------------------
   流程：
   1. content script 收集页面全文（前 N 字 + 术语候选）
   2. 调一次 LLM 产出 {"summary","terms"}（严格 JSON）
   3. 按 (URL + content hash) 缓存 24h
   4. 后续每段翻译把「摘要 + 术语表」拼进 system prompt
   命中缓存后零额外 LLM 调用。
   ============================================================ */

import { GlossaryEntry, PageContext } from '../utils/types';
import { buildContextPrompt, parseContextResponse } from './prompt';
import { extractTermCandidates } from '../utils/text-utils';

const CTX_CACHE_KEY = 'butler_ctx_cache';
const CTX_TTL_MS = 24 * 60 * 60 * 1000; // 24 小时
const CTX_MAX_ENTRIES = 100;

/** LLM 调用抽象（由 OpenAI 兼容 Provider 实现 complete） */
export interface LlmCaller {
  complete(system: string, user: string): Promise<string>;
}

/* ---------- 纯函数 ---------- */

/** djb2 哈希（纯函数，供缓存 key 使用） */
export function hashString(text: string): string {
  let hash = 5381;
  for (let i = 0; i < text.length; i++) {
    hash = ((hash << 5) + hash + text.charCodeAt(i)) >>> 0;
  }
  return hash.toString(16);
}

/** 上下文缓存 key：URL hash + 内容 hash（纯函数） */
export function ctxCacheKey(url: string, text: string): string {
  // 内容可能很长，只对前 8000 字参与 hash（与送入 LLM 的量一致）
  return `${hashString(url)}|${hashString(text.slice(0, 8000))}`;
}

/* ---------- 缓存（chrome.storage，24h TTL） ---------- */

interface CtxCacheEntry {
  ts: number;
  summary: string;
  terms: GlossaryEntry[];
}

async function loadCtxCache(): Promise<Record<string, CtxCacheEntry>> {
  try {
    const r = await chrome.storage.local.get(CTX_CACHE_KEY);
    return (r[CTX_CACHE_KEY] as Record<string, CtxCacheEntry>) || {};
  } catch {
    return {};
  }
}

async function saveCtxCache(cache: Record<string, CtxCacheEntry>): Promise<void> {
  try {
    // 超容量淘汰最旧
    const entries = Object.entries(cache);
    if (entries.length > CTX_MAX_ENTRIES) {
      entries.sort((a, b) => a[1].ts - b[1].ts);
      const trimmed = entries.slice(entries.length - CTX_MAX_ENTRIES);
      await chrome.storage.local.set({ [CTX_CACHE_KEY]: Object.fromEntries(trimmed) });
      return;
    }
    await chrome.storage.local.set({ [CTX_CACHE_KEY]: cache });
  } catch (e) {
    console.warn('[ButlerTranslate] Context cache save failed:', e);
  }
}

/* ---------- 主入口 ---------- */

/**
 * 获取页面上下文。
 * @param url  页面 URL（缓存 key 之一）
 * @param text 页面全文前 N 字
 * @param llm  LLM 调用者（仅缓存未命中时调用一次）
 * @returns 上下文；LLM 失败/解析失败时返回 null（不阻塞翻译）
 */
export async function getPageContext(
  url: string,
  text: string,
  llm: LlmCaller | null
): Promise<PageContext | null> {
  const key = ctxCacheKey(url, text);

  // 1. 查缓存（命中且 24h 内 → 零 LLM 调用）
  const cache = await loadCtxCache();
  const hit = cache[key];
  if (hit && Date.now() - hit.ts < CTX_TTL_MS) {
    return { summary: hit.summary, terms: hit.terms };
  }

  // 2. 无 LLM 可用则直接返回 null
  if (!llm) return null;

  // 3. 调一次 LLM
  try {
    const candidates = extractTermCandidates(text);
    const userPrompt = buildContextPrompt(text.slice(0, 8000), candidates);
    const raw = await llm.complete(
      '你是翻译辅助引擎，只输出严格 JSON，不做任何解释。',
      userPrompt
    );
    const ctx = parseContextResponse(raw);
    if (!ctx) return null;

    // 4. 写缓存（24h 内后续翻译零额外调用）
    cache[key] = { ts: Date.now(), summary: ctx.summary, terms: ctx.terms };
    await saveCtxCache(cache);
    return ctx;
  } catch (err) {
    console.warn('[ButlerTranslate] Context generation failed:', err);
    return null;
  }
}
