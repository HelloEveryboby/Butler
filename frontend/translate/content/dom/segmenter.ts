/* ============================================================
   Text Segmenter — 将文本节点按语义分组为翻译段落
   ============================================================ */

import { DOMTextNode } from './walker';
import { TextSegment } from '../../utils/types';

/** 块级标签列表（按这些标签分段） */
const BLOCK_TAGS = new Set([
  'P', 'DIV', 'LI', 'TD', 'TH', 'DT', 'DD',
  'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
  'BLOCKQUOTE', 'FIGCAPTION', 'CAPTION', 'SUMMARY',
  'ARTICLE', 'SECTION', 'HEADER', 'FOOTER', 'MAIN', 'ASIDE',
  'TR', 'THEAD', 'TBODY', 'TFOOT',
]);

/** 应该跳过的短文本 */
function shouldSkipText(text: string): boolean {
  if (text.length < 2) return true;
  // 纯数字
  if (/^[\d.,:%+\-*/=<>]+$/.test(text)) return true;
  // 纯符号
  if (/^[^\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]+$/.test(text)) return true;
  // 纯空白
  if (/^\s+$/.test(text)) return true;
  return false;
}

/**
 * 将 DOMTextNode 列表按父元素分组，生成 TextSegment
 * 相同父元素的文本节点合并为一个翻译单元
 */
export function segmentTexts(textNodes: DOMTextNode[], siteSelectors?: string[]): TextSegment[] {
  const segments: TextSegment[] = [];
  const processed = new Set<Element>();

  for (const item of textNodes) {
    const parent = findSegmentParent(item.parentElement, siteSelectors);
    if (processed.has(parent)) continue;
    processed.add(parent);

    // 收集该父元素下所有文本
    const texts: string[] = [];
    const nodes: Node[] = [];

    for (const tn of textNodes) {
      if (findSegmentParent(tn.parentElement, siteSelectors) === parent) {
        const t = tn.text;
        if (!shouldSkipText(t)) {
          texts.push(t);
          nodes.push(tn.node);
        }
      }
    }

    if (texts.length === 0) continue;

    const combined = texts.join(' ').trim();
    if (shouldSkipText(combined)) continue;

    segments.push({
      id: `bt-seg-${segments.length}`,
      elements: nodes,
      originalText: combined,
      parentElement: parent,
      isInline: isInlineElement(parent),
    });
  }

  return segments;
}

/**
 * 向上查找"语义父元素"作为分段边界
 * 优先用块级标签，其次用 data 属性
 */
function findSegmentParent(el: Element, siteSelectors?: string[]): Element {
  let current = el;
  let depth = 0;

  while (current && depth < 10) {
    // 站点规则匹配
    if (siteSelectors) {
      for (const sel of siteSelectors) {
        try {
          if (current.matches(sel)) return current;
        } catch {}
      }
    }

    // 块级标签
    if (BLOCK_TAGS.has(current.tagName)) return current;

    // 有明确语义的属性
    if (current.getAttribute('role') === 'paragraph') return current;
    if (current.hasAttribute('data-paragraph')) return current;

    current = current.parentElement!;
    depth++;
  }

  return el; // 兜底返回原始元素
}

function isInlineElement(el: Element): boolean {
  const display = window.getComputedStyle(el).display;
  return display === 'inline' || display === 'inline-block';
}
