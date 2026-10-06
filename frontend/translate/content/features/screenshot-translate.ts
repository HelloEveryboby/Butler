/* ============================================================
   截图翻译 — 选区截图 → OCR → 翻译 → 悬浮窗
   对接 Butler Python 后端
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { ocrImage } from './image-translate';

let overlayEl: HTMLDivElement | null = null;
let resultEl: HTMLDivElement | null = null;

/** 初始化截图翻译（快捷键触发） */
export function initScreenshotTranslate(config: TranslateConfig): void {
  document.addEventListener('keydown', (e) => {
    // Alt+S 触发
    if (e.altKey && e.key.toLowerCase() === 's') {
      e.preventDefault();
      startScreenshotTranslate(config);
    }
  });
}

export function startScreenshotTranslate(config: TranslateConfig): void {
  if (overlayEl) return; // 已在选区中

  // 创建遮罩层
  overlayEl = document.createElement('div');
  overlayEl.className = 'bt-screenshot-overlay';
  overlayEl.innerHTML = `
    <div class="bt-screenshot-hint">拖拽选择要翻译的区域，按 Esc 取消</div>
  `;
  document.body.appendChild(overlayEl);

  let startX = 0, startY = 0;
  let selectionBox: HTMLDivElement | null = null;

  overlayEl.addEventListener('mousedown', (e) => {
    startX = e.clientX;
    startY = e.clientY;

    selectionBox = document.createElement('div');
    selectionBox.className = 'bt-screenshot-selection';
    overlayEl!.appendChild(selectionBox);
  });

  overlayEl.addEventListener('mousemove', (e) => {
    if (!selectionBox) return;
    const x = Math.min(startX, e.clientX);
    const y = Math.min(startY, e.clientY);
    const w = Math.abs(e.clientX - startX);
    const h = Math.abs(e.clientY - startY);
    selectionBox.style.left = `${x}px`;
    selectionBox.style.top = `${y}px`;
    selectionBox.style.width = `${w}px`;
    selectionBox.style.height = `${h}px`;
  });

  overlayEl.addEventListener('mouseup', async (e) => {
    if (!selectionBox) return;

    const x = Math.min(startX, e.clientX);
    const y = Math.min(startY, e.clientY);
    const w = Math.abs(e.clientX - startX);
    const h = Math.abs(e.clientY - startY);

    if (w < 10 || h < 10) {
      cleanup();
      return;
    }

    // 截图
    cleanup();

    try {
      // 真实截图：content script 无权调 captureVisibleTab，由 background 中转后按 DPR 裁剪
      showResultWindow('截图中...', '', config);
      const canvas = await captureRegion(x, y, w, h);

      // 优先本地 OCR（tesseract 已随扩展打包，离线可用）
      showResultWindow('识别中...', '', config);
      let original = '';
      try {
        const ocr = await ocrImage(canvas);
        original = ocr.text.trim();
      } catch (ocrErr) {
        console.warn('[ButlerTranslate] 本地 OCR 失败，尝试 Butler 后端:', ocrErr);
      }

      if (!original) {
        // 本地 OCR 不可用时才走 Butler 后端（需 python 后端 + OCR 组件）
        const base64 = canvas.toDataURL('image/png').split(',')[1];
        const resp = await sendMessage({ type: 'TRANSLATE_IMAGE', base64 });
        if (resp.type === 'IMAGE_TRANSLATE_RESULT') {
          updateResultWindow(resp.original, resp.translated);
          return;
        }
        throw new Error(
          resp.type === 'TRANSLATE_ERROR'
            ? `本地 OCR 不可用，后端也不可用：${resp.error}`
            : 'OCR 未识别到文字'
        );
      }

      // 翻译识别出的文本（走常规翻译链，含缓存/降级）
      showResultWindow(original, '翻译中...', config);
      const transResp = await sendMessage({
        type: 'TRANSLATE',
        texts: [original],
        to: config.targetLang,
      });

      if (transResp.type === 'TRANSLATE_RESULT') {
        updateResultWindow(original, transResp.results[0]?.translated || '');
      } else {
        updateResultWindow(original, `翻译失败: ${(transResp as any).error || '未知错误'}`);
      }
    } catch (err) {
      updateResultWindow('', `截图翻译失败: ${err}`);
    }
  });

  // Esc 取消
  const escHandler = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      cleanup();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);

  function cleanup() {
    overlayEl?.remove();
    overlayEl = null;
    selectionBox = null;
  }
}

/** 截取页面区域（chrome.tabs.captureVisibleTab 中转 + DPR 裁剪） */
async function captureRegion(x: number, y: number, w: number, h: number): Promise<HTMLCanvasElement> {
  const resp = await sendMessage({ type: 'CAPTURE_VISIBLE_TAB' });
  if (resp.type !== 'CAPTURE_RESULT') {
    throw new Error(
      resp.type === 'TRANSLATE_ERROR' ? resp.error : '无法截取当前标签页'
    );
  }

  const img = await loadImage(resp.dataUrl);
  const dpr = window.devicePixelRatio || 1;

  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(w * dpr));
  canvas.height = Math.max(1, Math.round(h * dpr));
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(
    img,
    Math.round(x * dpr), Math.round(y * dpr), canvas.width, canvas.height,
    0, 0, canvas.width, canvas.height
  );
  return canvas;
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('截图解码失败'));
    img.src = src;
  });
}

function showResultWindow(original: string, translated: string, config: TranslateConfig): void {
  removeResultWindow();

  resultEl = document.createElement('div');
  resultEl.className = 'bt-screenshot-result';
  resultEl.innerHTML = `
    <div class="bt-screenshot-result-header">
      <span>📷 截图翻译</span>
      <button class="bt-screenshot-result-close">✕</button>
    </div>
    <div class="bt-screenshot-result-body">
      ${original ? `<div class="bt-screenshot-original"><strong>原文:</strong> ${escapeHtml(original)}</div>` : ''}
      <div class="bt-screenshot-translated"><strong>译文:</strong> ${escapeHtml(translated)}</div>
    </div>
    <div class="bt-screenshot-result-actions">
      <button class="bt-screenshot-copy-trans">📋 复制译文</button>
      ${original ? `<button class="bt-screenshot-copy-orig">📋 复制原文</button>` : ''}
    </div>
  `;

  document.body.appendChild(resultEl);

  // 拖拽
  makeDraggable(resultEl);

  resultEl.querySelector('.bt-screenshot-result-close')?.addEventListener('click', removeResultWindow);
  resultEl.querySelector('.bt-screenshot-copy-trans')?.addEventListener('click', () => {
    navigator.clipboard.writeText(translated);
  });
  resultEl.querySelector('.bt-screenshot-copy-orig')?.addEventListener('click', () => {
    navigator.clipboard.writeText(original);
  });
}

function updateResultWindow(original: string, translated: string): void {
  if (!resultEl) return;
  const body = resultEl.querySelector('.bt-screenshot-result-body');
  if (body) {
    body.innerHTML = `
      ${original ? `<div class="bt-screenshot-original"><strong>原文:</strong> ${escapeHtml(original)}</div>` : ''}
      <div class="bt-screenshot-translated"><strong>译文:</strong> ${escapeHtml(translated)}</div>
    `;
  }
}

function removeResultWindow(): void {
  resultEl?.remove();
  resultEl = null;
}

function makeDraggable(el: HTMLElement): void {
  const header = el.querySelector('.bt-screenshot-result-header') as HTMLElement;
  if (!header) return;

  let isDragging = false;
  let offsetX = 0, offsetY = 0;

  header.addEventListener('mousedown', (e) => {
    isDragging = true;
    offsetX = e.clientX - el.offsetLeft;
    offsetY = e.clientY - el.offsetTop;
    header.style.cursor = 'grabbing';
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    el.style.left = `${e.clientX - offsetX}px`;
    el.style.top = `${e.clientY - offsetY}px`;
  });

  document.addEventListener('mouseup', () => {
    isDragging = false;
    header.style.cursor = 'grab';
  });
}

function escapeHtml(str: string): string {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
