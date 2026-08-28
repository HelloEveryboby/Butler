/* ============================================================
   IntersectionObserver — 视口懒翻译
   只翻译滚动到可视区域的内容
   ============================================================ */

import { TextSegment } from '../../utils/types';

let viewportObserver: IntersectionObserver | null = null;
const pendingSegments = new Map<Element, TextSegment>();
let onVisible: ((segments: TextSegment[]) => void) | null = null;

/** 初始化视口观察器 */
export function initViewportObserver(
  callback: (segments: TextSegment[]) => void
): void {
  stopViewportObserver();
  onVisible = callback;

  viewportObserver = new IntersectionObserver(
    (entries) => {
      const visibleSegments: TextSegment[] = [];
      for (const entry of entries) {
        if (entry.isIntersecting) {
          const segment = pendingSegments.get(entry.target);
          if (segment) {
            visibleSegments.push(segment);
            pendingSegments.delete(entry.target);
            viewportObserver?.unobserve(entry.target);
          }
        }
      }
      if (visibleSegments.length > 0) {
        onVisible?.(visibleSegments);
      }
    },
    {
      rootMargin: '200px', // 预加载 200px
      threshold: 0.1,
    }
  );
}

/** 注册需要懒翻译的段落 */
export function observeSegment(segment: TextSegment): void {
  if (!viewportObserver) return;
  pendingSegments.set(segment.parentElement, segment);
  viewportObserver.observe(segment.parentElement);
}

/** 批量注册 */
export function observeSegments(segments: TextSegment[]): void {
  for (const seg of segments) {
    observeSegment(seg);
  }
}

/** 停止视口观察 */
export function stopViewportObserver(): void {
  viewportObserver?.disconnect();
  viewportObserver = null;
  pendingSegments.clear();
}
