/* ============================================================
   翻译缓存 — LRU + chrome.storage 持久化
   ------------------------------------------------------------
   缓存键 = 全文哈希 + 长度 + 目标语言 + 翻译源 + 术语签名。
   旧实现只取前 100 字符 + 长度 + 目标语言，长文本前缀相同会串味；
   且不区分翻译源/术语表，换源或改术语后仍命中旧译文。
   ============================================================ */

import { GlossaryEntry } from '../utils/types';

const CACHE_KEY = 'butler_translate_cache';

interface CacheEntry {
  translated: string;
  provider: string;
  timestamp: number;
}

/** FNV-1a 32-bit 哈希（覆盖全文，避免长文本前缀碰撞） */
function hashText(text: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, '0');
}

/** 术语签名：术语内容变化时缓存随之失效 */
export function glossarySignature(glossary: GlossaryEntry[]): string {
  if (!glossary || glossary.length === 0) return '';
  const parts = glossary
    .filter(g => g && g.source)
    .map(g => `${g.source}\u0001${g.target}`)
    .sort();
  return hashText(parts.join('\u0002'));
}

export class TranslationCache {
  private memoryCache = new Map<string, CacheEntry>();
  private maxSize: number;
  private persistTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(maxSize = 2000) {
    this.maxSize = maxSize;
    this.loadFromStorage();
  }

  private makeKey(text: string, to: string, provider = '', glossarySig = ''): string {
    return `${hashText(text)}|${text.length}|${to}|${provider}|${glossarySig}`;
  }

  get(text: string, to: string, provider = '', glossarySig = ''): CacheEntry | null {
    const key = this.makeKey(text, to, provider, glossarySig);
    const entry = this.memoryCache.get(key);
    if (entry) {
      // 移到最新（LRU）
      this.memoryCache.delete(key);
      this.memoryCache.set(key, entry);
    }
    return entry ?? null;
  }

  set(text: string, to: string, translated: string, provider: string, glossarySig = ''): void {
    const key = this.makeKey(text, to, provider, glossarySig);
    // 超过容量淘汰最旧的
    if (this.memoryCache.size >= this.maxSize) {
      const oldest = this.memoryCache.keys().next().value;
      if (oldest !== undefined) this.memoryCache.delete(oldest);
    }
    this.memoryCache.set(key, {
      translated,
      provider,
      timestamp: Date.now(),
    });
    this.schedulePersist();
  }

  has(text: string, to: string, provider = '', glossarySig = ''): boolean {
    return this.memoryCache.has(this.makeKey(text, to, provider, glossarySig));
  }

  clear(): void {
    this.memoryCache.clear();
    chrome.storage.local.remove(CACHE_KEY);
  }

  get size(): number {
    return this.memoryCache.size;
  }

  /** 批量查找，返回 { hits, misses } */
  batchLookup(texts: string[], to: string, provider = '', glossarySig = ''): {
    hits: Map<number, string>;
    misses: Map<number, string>;
  } {
    const hits = new Map<number, string>();
    const misses = new Map<number, string>();
    texts.forEach((text, idx) => {
      const entry = this.get(text, to, provider, glossarySig);
      if (entry) {
        hits.set(idx, entry.translated);
      } else {
        misses.set(idx, text);
      }
    });
    return { hits, misses };
  }

  private schedulePersist(): void {
    if (this.persistTimer) clearTimeout(this.persistTimer);
    this.persistTimer = setTimeout(() => this.persistToStorage(), 5000);
  }

  private async persistToStorage(): Promise<void> {
    try {
      // 只持久化最近 500 条
      const entries = Array.from(this.memoryCache.entries()).slice(-500);
      await chrome.storage.local.set({ [CACHE_KEY]: Object.fromEntries(entries) });
    } catch (e) {
      console.warn('[ButlerTranslate] Cache persist failed:', e);
    }
  }

  private async loadFromStorage(): Promise<void> {
    try {
      const result = await chrome.storage.local.get(CACHE_KEY);
      if (result[CACHE_KEY]) {
        const entries = Object.entries(result[CACHE_KEY]) as [string, CacheEntry][];
        for (const [key, value] of entries) {
          this.memoryCache.set(key, value);
        }
      }
    } catch (e) {
      console.warn('[ButlerTranslate] Cache load failed:', e);
    }
  }
}
