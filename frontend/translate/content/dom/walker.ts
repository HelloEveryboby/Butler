/* ============================================================
   DOM Walker — 遍历页面文本节点，提取可翻译段落
   ============================================================ */

/** 需要跳过的标签 */
const SKIP_TAGS = new Set([
  'SCRIPT', 'STYLE', 'NOSCRIPT', 'CODE', 'PRE', 'KBD', 'SAMP', 'VAR',
  'SVG', 'MATH', 'CANVAS', 'VIDEO', 'AUDIO', 'IFRAME', 'OBJECT', 'EMBED',
  'INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'OPTION',
  'BR', 'HR', 'WBR',
]);

/** 需要跳过的 CSS 选择器 */
const SKIP_SELECTORS = [
  '[contenteditable="true"]',
  '[translate="no"]',
  '[data-no-translate]',
  '.bt-translated',        // 已翻译节点
  '.bt-trans-loading',     // 加载中节点
  '.bt-bubble',            // 划词翻译气泡
  '.bt-floating-ball',     // 悬浮球
];

/** 需要跳过的 role */
const SKIP_ROLES = new Set([
  'textbox', 'button', 'menu', 'menuitem', 'navigation',
]);

export interface DOMTextNode {
  node: Text;
  parentElement: Element;
  text: string;
}

/**
 * 遍历指定根元素下所有可翻译的文本节点
 */
export function walkTextNodes(root: Element, extraExcludeSelectors: string[] = []): DOMTextNode[] {
  const allExclude = [...SKIP_SELECTORS, ...extraExcludeSelectors];
  const results: DOMTextNode[] = [];

  // 先检查根本身是否应跳过
  if (shouldSkipElement(root, allExclude)) return [];

  const walker = document.createTreeWalker(
    root,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;

        // 跳过空白文本
        if (!node.textContent?.trim()) return NodeFilter.FILTER_REJECT;

        // 跳过特殊标签
        if (SKIP_TAGS.has(parent.tagName)) return NodeFilter.FILTER_REJECT;

        // 跳过不可见元素
        if (!isVisible(parent)) return NodeFilter.FILTER_REJECT;

        // 跳过排除选择器
        if (shouldSkipElement(parent, allExclude)) return NodeFilter.FILTER_REJECT;

        // 跳过 role
        const role = parent.getAttribute('role');
        if (role && SKIP_ROLES.has(role)) return NodeFilter.FILTER_REJECT;

        return NodeFilter.FILTER_ACCEPT;
      },
    }
  );

  let node: Text | null;
  while ((node = walker.nextNode() as Text | null)) {
    const text = node.textContent?.trim();
    if (text && text.length >= 2) {
      results.push({
        node,
        parentElement: node.parentElement!,
        text,
      });
    }
  }

  return results;
}

function shouldSkipElement(el: Element, selectors: string[]): boolean {
  for (const sel of selectors) {
    try {
      if (el.matches(sel) || el.closest(sel)) return true;
    } catch {}
  }
  return false;
}

function isVisible(el: Element): boolean {
  const style = window.getComputedStyle(el);
  if (style.display === 'none' || style.visibility === 'hidden') return false;
  if (style.opacity === '0') return false;
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) return false;
  return true;
}
