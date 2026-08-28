/* ============================================================
   DOM Injector — 译文注入 + 样式继承 + 还原
   ============================================================ */

import { TextSegment } from '../../utils/types';

/** 译文容器 class */
const TRANSLATED_CLASS = 'bt-translated';
const LOADING_CLASS = 'bt-trans-loading';

/**
 * 在原文后注入译文（双语对照模式）
 */
export function injectBilingual(segment: TextSegment, translated: string): void {
  // 检查是否已经注入过
  const existing = segment.parentElement.querySelector(`.${TRANSLATED_CLASS}`);
  if (existing) {
    existing.textContent = translated;
    return;
  }

  const wrapper = document.createElement('div');
  wrapper.className = TRANSLATED_CLASS;
  wrapper.setAttribute('data-bt-id', segment.id);
  wrapper.textContent = translated;

  // 继承原文样式
  const computedStyle = window.getComputedStyle(segment.parentElement);
  wrapper.style.color = computedStyle.color;
  wrapper.style.fontSize = computedStyle.fontSize;
  wrapper.style.fontFamily = computedStyle.fontFamily;
  wrapper.style.lineHeight = computedStyle.lineHeight;
  wrapper.style.margin = '0';
  wrapper.style.padding = '0';

  // 注入到原文后
  segment.parentElement.insertAdjacentElement('afterend', wrapper);
}

/**
 * 替换模式：隐藏原文，显示译文
 */
export function injectReplace(segment: TextSegment, translated: string): void {
  // 隐藏原文所有文本节点
  for (const node of segment.elements) {
    if (node.parentElement) {
      node.parentElement.style.visibility = 'hidden';
      node.parentElement.style.height = '0';
      node.parentElement.style.overflow = 'hidden';
    }
  }

  // 注入译文
  const wrapper = document.createElement('div');
  wrapper.className = TRANSLATED_CLASS;
  wrapper.setAttribute('data-bt-id', segment.id);
  wrapper.textContent = translated;

  const computedStyle = window.getComputedStyle(segment.parentElement);
  wrapper.style.color = computedStyle.color;
  wrapper.style.fontSize = computedStyle.fontSize;

  segment.parentElement.insertAdjacentElement('afterend', wrapper);
}

/**
 * 悬停模式：给原文添加 tooltip
 */
export function injectHover(segment: TextSegment, translated: string): void {
  segment.parentElement.setAttribute('title', translated);
  segment.parentElement.classList.add('bt-hover-enabled');
}

/**
 * 显示 loading 状态
 */
export function showLoading(segment: TextSegment): void {
  const existing = segment.parentElement.querySelector(`.${LOADING_CLASS}`);
  if (existing) return;

  const loader = document.createElement('span');
  loader.className = LOADING_CLASS;
  loader.setAttribute('data-bt-id', segment.id);
  loader.innerHTML = ' <span class="bt-spinner"></span>';

  segment.parentElement.insertAdjacentElement('afterend', loader);
}

/**
 * 移除 loading 状态
 */
export function removeLoading(segment: TextSegment): void {
  const loader = segment.parentElement.parentElement?.querySelector(
    `.${LOADING_CLASS}[data-bt-id="${segment.id}"]`
  );
  loader?.remove();
}

/**
 * 还原：移除所有翻译节点，恢复原文
 */
export function restoreAll(): void {
  // 移除所有翻译节点
  document.querySelectorAll(`.${TRANSLATED_CLASS}`).forEach(el => el.remove());
  // 移除所有 loading
  document.querySelectorAll(`.${LOADING_CLASS}`).forEach(el => el.remove());
  // 恢复被隐藏的原文
  document.querySelectorAll('[style*="visibility: hidden"]').forEach(el => {
    (el as HTMLElement).style.visibility = '';
    (el as HTMLElement).style.height = '';
    (el as HTMLElement).style.overflow = '';
  });
  // 移除 hover 效果
  document.querySelectorAll('.bt-hover-enabled').forEach(el => {
    el.removeAttribute('title');
    el.classList.remove('bt-hover-enabled');
  });
}

/**
 * 检查页面是否已翻译
 */
export function isTranslated(): boolean {
  return document.querySelectorAll(`.${TRANSLATED_CLASS}`).length > 0;
}
