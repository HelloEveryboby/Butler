/* ============================================================
   DOM Injector — 译文注入 + 样式继承 + 还原
   ============================================================ */

import { TextSegment } from '../../utils/types';

/** 译文容器 class */
const TRANSLATED_CLASS = 'bt-translated';
const LOADING_CLASS = 'bt-trans-loading';
const BICOLUMN_CLASS = 'bt-bicolumn';

/**
 * 在原文后注入译文（双语对照模式）
 * layout: 'stacked' 上下堆叠 | 'columns' 双栏并排（解决英文长中文短的留白）
 */
export function injectBilingual(segment: TextSegment, translated: string,
                                layout: 'stacked' | 'columns' = 'stacked'): void {
  if (layout === 'columns') {
    injectBicolumn(segment, translated);
    return;
  }

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
 * 双栏并排：原文左栏、译文右栏，各自独立换行，消除长短不一的留白
 */
function injectBicolumn(segment: TextSegment, translated: string): void {
  const parent = segment.parentElement;

  // 已有双栏容器则只更新译文
  const existingWrap = parent.parentElement?.classList.contains(BICOLUMN_CLASS)
    ? parent.parentElement
    : null;
  if (existingWrap) {
    const target = existingWrap.querySelector(`.${TRANSLATED_CLASS}`);
    if (target) { target.textContent = translated; return; }
  }

  // 用 flex 容器包裹原文与译文
  const wrap = document.createElement('div');
  wrap.className = BICOLUMN_CLASS;
  wrap.setAttribute('data-bt-id', segment.id);

  const source = document.createElement('div');
  source.className = 'bt-bicolumn-source';
  source.appendChild(parent.cloneNode(true));

  const target = document.createElement('div');
  target.className = `${TRANSLATED_CLASS} bt-bicolumn-target`;
  target.setAttribute('data-bt-id', segment.id);
  target.textContent = translated;

  // 继承原文样式
  const cs = window.getComputedStyle(parent);
  target.style.color = cs.color;
  target.style.fontSize = cs.fontSize;
  target.style.fontFamily = cs.fontFamily;
  target.style.lineHeight = cs.lineHeight;

  wrap.appendChild(source);
  wrap.appendChild(target);

  // 替换原元素为双栏容器
  parent.replaceWith(wrap);
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
 * 悬停模式：不常驻 tooltip，只记录译文。
 * 「悬停 + 按住触发键（默认 Alt）」才显示整段译文，松开即消失（见 initHoverTranslate）。
 */
export function injectHover(segment: TextSegment, translated: string): void {
  segment.parentElement.setAttribute('data-bt-hover-text', translated);
  segment.parentElement.classList.add('bt-hover-enabled');
}

/* ---------- 悬停翻译：按住快捷键才显示 ---------- */

let hoverTriggerKey = 'alt';
let hoverKeyHeld = false;
let hoverTooltipEl: HTMLDivElement | null = null;
let hoverCurrentEl: Element | null = null;
let hoverInitialized = false;

function triggerKeyMatches(e: KeyboardEvent): boolean {
  const key = hoverTriggerKey.toLowerCase();
  if (key === 'alt') return e.key === 'Alt';
  if (key === 'control' || key === 'ctrl') return e.key === 'Control';
  if (key === 'shift') return e.key === 'Shift';
  if (key === 'meta' || key === 'cmd') return e.key === 'Meta';
  return e.key.toLowerCase() === key;
}

function ensureTooltip(): HTMLDivElement {
  if (hoverTooltipEl) return hoverTooltipEl;
  hoverTooltipEl = document.createElement('div');
  hoverTooltipEl.className = 'bt-hover-tooltip';
  document.body.appendChild(hoverTooltipEl);
  return hoverTooltipEl;
}

function showHoverTooltip(x: number, y: number): void {
  if (!hoverCurrentEl) return;
  const text = hoverCurrentEl.getAttribute('data-bt-hover-text');
  if (!text) return;
  const tip = ensureTooltip();
  tip.textContent = text;
  tip.style.display = 'block';
  // 避免超出视口
  const maxX = window.scrollX + window.innerWidth - tip.offsetWidth - 12;
  const maxY = window.scrollY + window.innerHeight - tip.offsetHeight - 12;
  tip.style.left = `${Math.min(x + 14, maxX)}px`;
  tip.style.top = `${Math.min(y + 16, maxY)}px`;
}

function hideHoverTooltip(): void {
  if (hoverTooltipEl) hoverTooltipEl.style.display = 'none';
}

/**
 * 初始化悬停翻译（按住触发键才显示整段译文）。
 * @param triggerKey 触发键名（'Alt' / 'Control' / 'Shift' / 任意键名）
 */
export function initHoverTranslate(triggerKey: string): void {
  hoverTriggerKey = triggerKey || 'Alt';
  if (hoverInitialized) return;
  hoverInitialized = true;

  document.addEventListener('keydown', (e) => {
    if (triggerKeyMatches(e)) {
      hoverKeyHeld = true;
      if (hoverCurrentEl) {
        showHoverTooltip(hoverLastX, hoverLastY);
      }
    }
  });

  document.addEventListener('keyup', (e) => {
    if (triggerKeyMatches(e)) {
      hoverKeyHeld = false;
      hideHoverTooltip();
    }
  });

  // 窗口失焦时松开状态复位，防止 tooltip 卡住
  window.addEventListener('blur', () => {
    hoverKeyHeld = false;
    hideHoverTooltip();
  });

  document.addEventListener('mouseover', (e) => {
    const el = (e.target as Element | null)?.closest?.('[data-bt-hover-text]') || null;
    hoverCurrentEl = el;
    if (el && hoverKeyHeld) showHoverTooltip(hoverLastX, hoverLastY);
    else hideHoverTooltip();
  });

  document.addEventListener('mousemove', (e) => {
    hoverLastX = e.clientX;
    hoverLastY = e.clientY;
    if (hoverKeyHeld && hoverCurrentEl) showHoverTooltip(e.clientX, e.clientY);
  });

  document.addEventListener('mouseout', (e) => {
    if (hoverCurrentEl && !hoverCurrentEl.contains(e.relatedTarget as Node)) {
      hoverCurrentEl = null;
      hideHoverTooltip();
    }
  });
}

let hoverLastX = 0;
let hoverLastY = 0;

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
  // 还原双栏容器：把原文放回去，移除容器和译文
  document.querySelectorAll(`.${BICOLUMN_CLASS}`).forEach(wrap => {
    const source = wrap.querySelector('.bt-bicolumn-source');
    if (source && source.firstElementChild) {
      wrap.replaceWith(source.firstElementChild);
    } else {
      wrap.remove();
    }
  });

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
    el.removeAttribute('data-bt-hover-text');
    el.classList.remove('bt-hover-enabled');
  });
  hideHoverTooltip();
}

/**
 * 检查页面是否已翻译
 */
export function isTranslated(): boolean {
  return document.querySelectorAll(`.${TRANSLATED_CLASS}`).length > 0;
}
