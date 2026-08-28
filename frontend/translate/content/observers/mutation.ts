/* ============================================================
   MutationObserver — SPA 动态内容自动翻译
   ============================================================ */

import { TranslateConfig } from '../../utils/types';

let observer: MutationObserver | null = null;
let onNewContent: ((nodes: Element[]) => void) | null = null;
let debounceTimer: ReturnType<typeof setTimeout> | null = null;

/** 开始监听 DOM 变化 */
export function startObserving(
  config: TranslateConfig,
  callback: (nodes: Element[]) => void
): void {
  stopObserving();
  onNewContent = callback;

  observer = new MutationObserver((mutations) => {
    const newElements: Element[] = [];

    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType !== Node.ELEMENT_NODE) continue;
        const el = node as Element;

        // 跳过翻译注入的节点
        if (el.classList?.contains('bt-translated') ||
            el.classList?.contains('bt-trans-loading') ||
            el.classList?.contains('bt-bubble') ||
            el.classList?.contains('bt-floating-ball')) {
          continue;
        }

        // 跳过脚本/样式
        if (['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(el.tagName)) continue;

        newElements.push(el);
      }
    }

    if (newElements.length > 0) {
      // 防抖：等待 DOM 稳定后再翻译
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        onNewContent?.(newElements);
      }, 500);
    }
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });
}

/** 停止监听 */
export function stopObserving(): void {
  observer?.disconnect();
  observer = null;
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
}
