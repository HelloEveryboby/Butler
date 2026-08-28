/* ============================================================
   PDF 翻译 — 浏览器中打开 PDF 时实时翻译
   使用 pdf.js 提取文本 + 坐标，翻译后 CSS 定位覆盖
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { injectStyles } from '../styles/styles';

// ---------- 状态 ----------
let isEnabled = false;
let pdfContainer: HTMLDivElement | null = null;
let translatedPages = new Set<number>();
let pageTextCache = new Map<number, Array<{ text: string; x: number; y: number; width: number; height: number; fontSize: number }>>();

// ---------- PDF 检测 ----------
export function isPDFPage(): boolean {
  // 检查 URL
  if (location.href.includes('.pdf') || location.pathname.endsWith('.pdf')) return true;
  // 检查 Content-Type meta
  const meta = document.querySelector('meta[http-equiv="Content-Type"]');
  if (meta?.getAttribute('content')?.includes('application/pdf')) return true;
  // 检查 embed/object
  if (document.querySelector('embed[type="application/pdf"]')) return true;
  if (document.querySelector('object[type="application/pdf"]')) return true;
  // Chrome 内置 PDF viewer
  if (document.querySelector('#viewer.pdfViewer')) return true;
  if (document.querySelector('pdf-viewer')) return true;
  return false;
}

// ---------- 初始化 ----------
export function initPDFTranslate(config: TranslateConfig): void {
  if (!isPDFPage()) return;
  console.log('[ButlerTranslate] PDF page detected');
  injectStyles();
  injectPDFStyles();
}

/** 开始 PDF 翻译 */
export async function startPDFTranslate(config: TranslateConfig): Promise<void> {
  if (!isPDFPage()) return;
  isEnabled = true;

  // 等待 PDF 渲染完成
  await waitForPDFReady();

  // 方案 A：Chrome 内置 PDF viewer（最常见）
  if (document.querySelector('#viewer.pdfViewer')) {
    await translateChromePDF(config);
    return;
  }

  // 方案 B：embed/object 标签
  const embed = document.querySelector('embed[type="application/pdf"]') as HTMLEmbedElement;
  const obj = document.querySelector('object[type="application/pdf"]') as HTMLObjectElement;
  if (embed || obj) {
    await translateEmbeddedPDF(config, embed || obj);
    return;
  }

  // 方案 C：通用 — 通过 pdf.js 从 URL 加载
  await translatePDFUrl(config, location.href);
}

/** 停止 PDF 翻译 */
export function stopPDFTranslate(): void {
  isEnabled = false;
  // 移除所有翻译覆盖
  document.querySelectorAll('.bt-pdf-translated').forEach(el => el.remove());
  document.querySelectorAll('.bt-pdf-container').forEach(el => el.remove());
  translatedPages.clear();
}

export function isPDFTranslateEnabled(): boolean {
  return isEnabled;
}

// ---------- Chrome 内置 PDF viewer ----------
async function translateChromePDF(config: TranslateConfig): Promise<void> {
  const viewer = document.querySelector('#viewer.pdfViewer');
  if (!viewer) return;

  // 监听页面渲染（PDF 页面懒加载）
  const observer = new MutationObserver(async (mutations) => {
    if (!isEnabled) return;
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType !== Node.ELEMENT_NODE) continue;
        const page = (node as Element).closest?.('.page') || (node as Element);
        if (page.classList?.contains('page')) {
          const pageNum = parseInt(page.getAttribute('data-page-number') || '0');
          if (pageNum > 0 && !translatedPages.has(pageNum)) {
            await translatePage(page as HTMLElement, pageNum, config);
          }
        }
      }
    }
  });

  observer.observe(viewer, { childList: true, subtree: true });

  // 翻译已渲染的页面
  const pages = viewer.querySelectorAll('.page');
  for (const page of pages) {
    const pageNum = parseInt(page.getAttribute('data-page-number') || '0');
    if (pageNum > 0) {
      await translatePage(page as HTMLElement, pageNum, config);
    }
  }
}

// ---------- 翻译单页 ----------
async function translatePage(
  pageEl: HTMLElement,
  pageNum: number,
  config: TranslateConfig
): Promise<void> {
  if (translatedPages.has(pageNum) || !isEnabled) return;
  translatedPages.add(pageNum);

  // 提取文本层
  const textLayer = pageEl.querySelector('.textLayer');
  if (!textLayer) return;

  // 收集文本段
  const textSpans = textLayer.querySelectorAll('span');
  const segments: Array<{ text: string; el: HTMLElement }> = [];
  let currentText = '';
  let currentEl: HTMLElement | null = null;

  for (const span of textSpans) {
    const text = span.textContent?.trim();
    if (!text) continue;

    // 同一行的文本合并
    const style = window.getComputedStyle(span);
    const top = style.top;

    if (currentEl && currentEl.style.top === top) {
      currentText += text;
    } else {
      if (currentText && currentEl) {
        segments.push({ text: currentText, el: currentEl });
      }
      currentText = text;
      currentEl = span as HTMLElement;
    }
  }
  if (currentText && currentEl) {
    segments.push({ text: currentText, el: currentEl });
  }

  // 过滤太短的
  const toTranslate = segments.filter(s => s.text.length >= 3);
  if (toTranslate.length === 0) return;

  // 批量翻译
  const texts = toTranslate.map(s => s.text);

  try {
    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts,
      to: config.targetLang,
    });

    if (resp.type === 'TRANSLATE_RESULT') {
      const results = resp.results;

      // 在每个文本段下方注入翻译
      toTranslate.forEach((seg, idx) => {
        const translated = results[idx]?.translated;
        if (!translated) return;

        const overlay = document.createElement('div');
        overlay.className = 'bt-pdf-translated';
        overlay.textContent = translated;

        // 定位到原文下方
        const rect = seg.el.getBoundingClientRect();
        const pageRect = pageEl.getBoundingClientRect();
        overlay.style.position = 'absolute';
        overlay.style.left = `${rect.left - pageRect.left}px`;
        overlay.style.top = `${rect.bottom - pageRect.top + 2}px`;
        overlay.style.width = `${rect.width}px`;
        overlay.style.fontSize = `${Math.max(10, parseFloat(seg.el.style.fontSize || '14') * 0.75)}px`;

        // 确保页面容器是 relative
        const pageContainer = pageEl.querySelector('.canvasWrapper')?.parentElement || pageEl;
        (pageContainer as HTMLElement).style.position = 'relative';
        pageContainer.appendChild(overlay);
      });
    }
  } catch (err) {
    console.warn(`[ButlerTranslate] PDF page ${pageNum} translation failed:`, err);
  }
}

// ---------- embed/object PDF ----------
async function translateEmbeddedPDF(config: TranslateConfig, el: HTMLElement): Promise<void> {
  const pdfUrl = el.getAttribute('src') || el.getAttribute('data');
  if (!pdfUrl) return;
  await translatePDFUrl(config, pdfUrl);
}

// ---------- 通用 PDF URL（通过 pdf.js）----------
async function translatePDFUrl(config: TranslateConfig, url: string): Promise<void> {
  // 动态加载 pdf.js
  if (!window.pdfjsLib) {
    await loadPdfJs();
  }

  if (!window.pdfjsLib) {
    console.error('[ButlerTranslate] Failed to load pdf.js');
    return;
  }

  try {
    const pdf = await window.pdfjsLib.getDocument(url).promise;
    console.log(`[ButlerTranslate] PDF loaded: ${pdf.numPages} pages`);

    // 创建翻译覆盖容器
    createPDFContainer();

    for (let i = 1; i <= pdf.numPages; i++) {
      if (!isEnabled) break;
      await translatePdfJsPage(pdf, i, config);
    }
  } catch (err) {
    console.error('[ButlerTranslate] PDF load failed:', err);
  }
}

async function translatePdfJsPage(pdf: any, pageNum: number, config: TranslateConfig): Promise<void> {
  const page = await pdf.getPage(pageNum);
  const viewport = page.getViewport({ scale: 1.5 });
  const textContent = await page.getTextContent();

  // 提取文本段和坐标
  const items = textContent.items.filter((item: any) => item.str?.trim().length >= 3);
  if (items.length === 0) return;

  const texts = items.map((item: any) => item.str);

  try {
    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts,
      to: config.targetLang,
    });

    if (resp.type !== 'TRANSLATE_RESULT') return;

    // 为每页创建翻译层
    const pageDiv = document.createElement('div');
    pageDiv.className = 'bt-pdf-page-overlay';
    pageDiv.style.position = 'relative';
    pageDiv.style.width = `${viewport.width}px`;
    pageDiv.style.height = `${viewport.height}px`;
    pageDiv.style.marginBottom = '12px';

    items.forEach((item: any, idx: number) => {
      const translated = resp.results[idx]?.translated;
      if (!translated) return;

      const tx = item.transform;
      // pdf.js 坐标系：左下角为原点，需要转换
      const x = tx[4];
      const y = viewport.height - tx[5];

      const span = document.createElement('div');
      span.className = 'bt-pdf-translated';
      span.textContent = translated;
      span.style.position = 'absolute';
      span.style.left = `${x}px`;
      span.style.top = `${y + 2}px`;
      span.style.fontSize = `${Math.max(10, (tx[0] || 14) * 0.75)}px`;
      span.style.color = '#4a9eff';
      span.style.whiteSpace = 'nowrap';
      span.style.pointerEvents = 'none';

      pageDiv.appendChild(span);
    });

    pdfContainer?.appendChild(pageDiv);
  } catch (err) {
    console.warn(`[ButlerTranslate] PDF page ${pageNum} failed:`, err);
  }
}

// ---------- 辅助 ----------
async function waitForPDFReady(): Promise<void> {
  return new Promise((resolve) => {
    if (document.querySelector('#viewer.pdfViewer, embed[type="application/pdf"], object[type="application/pdf"]')) {
      setTimeout(resolve, 1000);
      return;
    }
    // 等待 PDF 加载
    const observer = new MutationObserver(() => {
      if (document.querySelector('#viewer.pdfViewer, embed, object')) {
        observer.disconnect();
        setTimeout(resolve, 500);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    // 超时
    setTimeout(() => { observer.disconnect(); resolve(); }, 10000);
  });
}

function createPDFContainer(): void {
  if (pdfContainer) return;
  pdfContainer = document.createElement('div');
  pdfContainer.className = 'bt-pdf-container';
  pdfContainer.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 999998;
    pointer-events: none;
    overflow: auto;
    background: rgba(255, 255, 255, 0.02);
  `;
  document.body.appendChild(pdfContainer);
}

async function loadPdfJs(): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.9.155/pdf.min.mjs';
    script.type = 'module';
    script.onload = () => {
      // 设置 worker
      if (window.pdfjsLib) {
        window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.9.155/pdf.worker.min.mjs';
      }
      resolve();
    };
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

function injectPDFStyles(): void {
  const style = document.createElement('style');
  style.id = 'butler-pdf-styles';
  style.textContent = `
    .bt-pdf-translated {
      color: #4a9eff;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      line-height: 1.3;
      opacity: 0.85;
      pointer-events: none;
      z-index: 999999;
    }
    .bt-pdf-page-overlay {
      position: relative;
    }
  `;
  document.head.appendChild(style);
}

// 类型声明
declare global {
  interface Window {
    pdfjsLib: any;
  }
}
