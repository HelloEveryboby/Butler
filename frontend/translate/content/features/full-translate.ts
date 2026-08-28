/* ============================================================
   全文翻译 — 渐进式 + 懒翻译 + 分批
   ============================================================ */

import { walkTextNodes } from '../dom/walker';
import { segmentTexts } from '../dom/segmenter';
import { getSiteSelectors, getSiteExcludes } from '../dom/site-rules';
import { injectBilingual, injectReplace, injectHover, showLoading, removeLoading, restoreAll, isTranslated } from '../dom/injector';
import { sendMessage } from '../../utils/messaging';
import { TranslateConfig, TextSegment, TranslationResult } from '../../utils/types';

let isTranslating = false;
let translatedSegments: TextSegment[] = [];

/** 启动全文翻译 */
export async function startFullTranslate(config: TranslateConfig): Promise<void> {
  if (isTranslating) return;
  if (isTranslated()) {
    restoreAll();
    return;
  }

  isTranslating = true;
  const hostname = window.location.hostname;
  const siteSelectors = getSiteSelectors(hostname);
  const siteExcludes = getSiteExcludes(hostname);
  const allExclude = [...config.excludeSelectors, ...siteExcludes];

  try {
    // 1. 遍历 DOM 提取文本节点
    const root = siteSelectors.length > 0
      ? document.querySelector(siteSelectors[0]) || document.body
      : document.body;

    const textNodes = walkTextNodes(root, allExclude);

    // 2. 按语义分段
    const segments = segmentTexts(textNodes, siteSelectors);
    if (segments.length === 0) {
      console.log('[ButlerTranslate] No translatable content found');
      return;
    }

    // 3. 分批翻译（每批 15 段）
    const BATCH_SIZE = 15;
    for (let i = 0; i < segments.length; i += BATCH_SIZE) {
      const batch = segments.slice(i, i + BATCH_SIZE);
      const texts = batch.map(s => s.originalText);

      // 显示 loading
      batch.forEach(s => showLoading(s));

      try {
        const resp = await sendMessage({
          type: 'TRANSLATE',
          texts,
          to: config.targetLang,
        });

        if (resp.type === 'TRANSLATE_RESULT') {
          const results = resp.results;
          batch.forEach((seg, idx) => {
            removeLoading(seg);
            const translated = results[idx]?.translated;
            if (translated) {
              applyTranslation(seg, translated, config.displayMode);
              translatedSegments.push(seg);
            }
          });
        }
      } catch (err) {
        console.warn('[ButlerTranslate] Batch failed:', err);
        batch.forEach(s => removeLoading(s));
      }
    }
  } finally {
    isTranslating = false;
  }
}

/** 应用翻译结果 */
function applyTranslation(segment: TextSegment, translated: string, mode: string): void {
  switch (mode) {
    case 'bilingual':
      injectBilingual(segment, translated);
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
