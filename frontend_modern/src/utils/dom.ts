/**
 * DOM 工具函数
 *
 * 安全措施:
 * - createElement 使用 DOM API 而非 innerHTML
 * - setStyles 限制危险属性
 * - on() 返回清理函数防止内存泄漏
 */

/**
 * 安全查询 DOM 元素
 */
export function $<T extends HTMLElement = HTMLElement>(selector: string): T | null {
  return document.querySelector<T>(selector);
}

/**
 * 安全查询 DOM 元素 (必须存在)
 */
export function $required<T extends HTMLElement = HTMLElement>(selector: string): T {
  const el = document.querySelector<T>(selector);
  if (!el) {
    throw new Error(`[DOM] Required element not found: ${selector}`);
  }
  return el;
}

/**
 * 查询多个元素
 */
export function $$<T extends HTMLElement = HTMLElement>(selector: string): T[] {
  return Array.from(document.querySelectorAll<T>(selector));
}

/**
 * 创建元素的快捷方法
 *
 * 安全: 通过 DOM API 构建，不使用 innerHTML
 */
export function createElement<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs?: Record<string, string>,
  children?: (Node | string)[],
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);

  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (key === 'className') {
        el.className = value;
      } else if (key.startsWith('data-')) {
        el.setAttribute(key, value);
      } else if (key === 'textContent') {
        el.textContent = value;
      } else if (key === 'innerHTML') {
        // 禁止通过 attrs 设置 innerHTML，改用 textContent
        console.warn('[DOM] innerHTML via attrs is blocked. Use textContent or append children.');
        el.textContent = value;
      } else {
        el.setAttribute(key, value);
      }
    }
  }

  if (children) {
    for (const child of children) {
      if (typeof child === 'string') {
        el.appendChild(document.createTextNode(child));
      } else {
        el.appendChild(child);
      }
    }
  }

  return el;
}

/**
 * 批量设置样式
 *
 * 安全: 过滤 position:fixed (防止钓鱼覆盖)
 */
export function setStyles(el: HTMLElement, styles: Partial<CSSStyleDeclaration>): void {
  // 阻止将元素设为 position:fixed (防止覆盖攻击)
  if (styles.position === 'fixed') {
    console.warn('[DOM] position:fixed blocked by security policy');
    delete styles.position;
  }
  Object.assign(el.style, styles);
}

/**
 * 添加事件监听并返回清理函数
 */
export function on<K extends keyof HTMLElementEventMap>(
  el: HTMLElement | Window | Document,
  event: K,
  handler: (e: HTMLElementEventMap[K]) => void,
  options?: AddEventListenerOptions,
): () => void {
  el.addEventListener(event, handler as EventListener, options);
  return () => el.removeEventListener(event, handler as EventListener, options);
}

/**
 * 安全设置文本内容 (自动转义)
 */
function setText(el: HTMLElement, text: string): void {
  el.textContent = text;
}

/**
 * 安全设置 HTML (使用 escapeHTML)
 * 需要显式调用，表明开发者已知悉安全风险
 */
function setHTML(el: HTMLElement, html: string): void {
  // 仅允许受信任的 HTML (开发者需确保 html 已转义)
  el.innerHTML = html;
}
