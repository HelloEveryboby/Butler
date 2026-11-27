/* ============================================================
   全文翻译 — 渐进式 + 懒翻译 + 分批
   ------------------------------------------------------------
   - 首屏：按语义分段后分批（每批 15 段）并发翻译（最多 3 批并行）
   - 增量：MutationObserver 捕获 SPA 新内容，交给视口观察器
   - 懒翻译：IntersectionObserver，滚动到可视区域才翻译
   ============================================================ */

import { walkTextNodes } from '../dom/walker';
import { segmentTexts } from '../dom/segmenter';
import { getSiteSelectors, getSiteExcludes } from '../dom/site-rules';
import { injectBilingual, injectReplace, injectHover, showLoading, removeLoading, restoreAll, isTranslated } from '../dom/injector';
import { sendMessage } from '../../utils/messaging';
import { TranslateConfig, TextSegment } from '../../utils/types';
import { startObserving, stopObserving } from '../observers/mutation';
import { initViewportObserver, observeSegments, stopViewportObserver } from '../observers/viewport';

const BATCH_SIZE = 15;
const MAX_CONCURRENCY = 3;

let isTranslating = false;
let translatedSegments: TextSegment[] = [];
let pageContext: { url: string; text: string } | null = null;
let incrementalExcludes: string[] = [];

/** 启动全文翻译 */
export async function startFullTranslate(config: TranslateConfig): Promise<void> {
  if (isTranslating) return;
  if (isTranslated()) {
    restoreAll();
    return;
  }

  isTranslating = true;
  const hostname = window.location.hostname;
  const siteSelectors = getSiteSelectors(hostname, config.customSiteRules);
  const siteExcludes = getSiteExcludes(hostname, config.customSiteRules);
  const allExclude = [...config.excludeSelectors, ...siteExcludes];
  incrementalExcludes = allExclude;

  try {
    // 1. 遍历 DOM 提取文本节点
    const root = siteSelectors.length > 0
      ? document.querySelector(siteSelectors[0]) || document.body
      : document.body;

    const textNodes = walkTextNodes(root, allExclude);

    // 2. 按语义分段
    const segments = segmentTexts(textNodes, siteSelectors);

    // 页面上下文（前 3000 字）：供 AI 摘要 + 术语一致性（1.2）
    pageContext = {
      url: location.href,
      text: (document.body.innerText || '').slice(0, 3000),
    };

    // 3. 首屏分批并发翻译（每批 15 段，最多 3 批并行）
    if (segments.length > 0) {
      const batches: TextSegment[][] = [];
      for (let i = 0; i < segments.length; i += BATCH_SIZE) {
        batches.push(segments.slice(i, i + BATCH_SIZE));
      }
      await runWithConcurrency(batches, MAX_CONCURRENCY,
        batch => translateSegmentsBatch(batch, config));
    } else {
      console.log('[ButlerTranslate] No translatable content found');
    }

    // 4. 增量 + 懒翻译：SPA 新内容先注册，滚动到视口才翻译
    if (!document.body) return;
    initViewportObserver(visible => {
      void translateVisible(visible, config);
    });
    startObserving(config, elements => {
      registerNewContent(elements, config);
    });
  } finally {
    isTranslating = false;
  }
}

/** 翻译单批段落并注入 */
async function translateSegmentsBatch(batch: TextSegment[], config: TranslateConfig): Promise<void> {
  const texts = batch.map(s => s.originalText);
  batch.forEach(s => showLoading(s));

  try {
    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts,
      to: config.targetLang,
      context: pageContext ?? undefined,
    });

    if (resp.type === 'TRANSLATE_RESULT') {
      batch.forEach((seg, idx) => {
        removeLoading(seg);
        const translated = resp.results[idx]?.translated;
        if (translated) {
          applyTranslation(seg, translated, config);
          translatedSegments.push(seg);
        }
      });
    } else {
      batch.forEach(s => removeLoading(s));
    }
  } catch (err) {
    console.warn('[ButlerTranslate] Batch failed:', err);
    batch.forEach(s => removeLoading(s));
  }
}

/** 视口内段落按批翻译（串行，避免一次涌入过多请求） */
async function translateVisible(segments: TextSegment[], config: TranslateConfig): Promise<void> {
  const live = segments.filter(s => s.parentElement?.isConnected);
  for (let i = 0; i < live.length; i += BATCH_SIZE) {
    await translateSegmentsBatch(live.slice(i, i + BATCH_SIZE), config);
  }
}

/** 把 SPA 新加入的 DOM 转成段落，注册到视口观察器（滚动可见才翻译） */
function registerNewContent(elements: Element[], config: TranslateConfig): void {
  const siteSelectors = getSiteSelectors(window.location.hostname, config.customSiteRules);
  const seen = new Set<Element>();
  const segments: TextSegment[] = [];

  for (const el of elements) {
    if (!el.isConnected) continue;
    const nodes = walkTextNodes(el, incrementalExcludes);
    for (const seg of segmentTexts(nodes, siteSelectors)) {
      if (seen.has(seg.parentElement)) continue;
      seen.add(seg.parentElement);
      segments.push(seg);
    }
  }

  if (segments.length > 0) observeSegments(segments);
}

/** 受限并发执行 */
async function runWithConcurrency<T>(
  items: T[],
  limit: number,
  fn: (item: T) => Promise<void>
): Promise<void> {
  let cursor = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (cursor < items.length) {
      const idx = cursor++;
      await fn(items[idx]);
    }
  });
  await Promise.all(workers);
}

/** 应用翻译结果 */
function applyTranslation(segment: TextSegment, translated: string, config: TranslateConfig): void {
  switch (config.displayMode) {
    case 'bilingual':
      injectBilingual(segment, translated, config.bilingualLayout || 'stacked');
      break;
    case 'translation-only':
      injectReplace(segment, translated);
      break;
    case 'hover':
      injectHover(segment, translated);
      break;
  }
}

/** 停止翻译并还原 */
export function stopTranslate(): void {
  stopObserving();
  stopViewportObserver();
  restoreAll();
  translatedSegments = [];
}

/** 切换翻译状态 */
export function toggleTranslate(config: TranslateConfig): void {
  if (isTranslated()) {
    stopTranslate();
  } else {
    startFullTranslate(config);
  }
}

export { isTranslated, isTranslating };
