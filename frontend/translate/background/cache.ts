/* ============================================================
   翻译缓存 — LRU + chrome.storage 持久化
   ============================================================ */

const CACHE_KEY = 'butler_translate_cache';

interface CacheEntry {
  translated: string;
  provider: string;
  timestamp: number;
}

export class TranslationCache {
  private memoryCache = new Map<string, CacheEntry>();
  private maxSize: number;
  private persistTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(maxSize = 2000) {
    this.maxSize = maxSize;
    this.loadFromStorage();
  }

  private makeKey(text: string, to: string): string {
    // 简单 hash：取前 100 字符 + 长度 + 目标语言
    const prefix = text.slice(0, 100);
    return `${prefix}|${text.length}|${to}`;
  }

  get(text: string, to: string): CacheEntry | null {
    const key = this.makeKey(text, to);
    const entry = this.memoryCache.get(key);
    if (entry) {
      // 移到最新（LRU）
      this.memoryCache.delete(key);
      this.memoryCache.set(key, entry);
    }
    return entry ?? null;
  }

  set(text: string, to: string, translated: string, provider: string): void {
    const key = this.makeKey(text, to);
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

  has(text: string, to: string): boolean {
    return this.memoryCache.has(this.makeKey(text, to));
  }

  clear(): void {
    this.memoryCache.clear();
    chrome.storage.local.remove(CACHE_KEY);
  }

  get size(): number {
    return this.memoryCache.size;
  }

  /** 批量查找，返回 { hits, misses, missTexts } */
  batchLookup(texts: string[], to: string): {
    hits: Map<number, string>;
    misses: Map<number, string>;
  } {
    const hits = new Map<number, string>();
    const misses = new Map<number, string>();
    texts.forEach((text, idx) => {
      const entry = this.get(text, to);
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
