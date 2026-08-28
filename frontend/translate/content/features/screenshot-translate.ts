/* ============================================================
   截图翻译 — 选区截图 → OCR → 翻译 → 悬浮窗
   对接 Butler Python 后端
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';

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
      // 使用 html2canvas 或 Canvas API 截取区域
      const canvas = await captureRegion(x, y, w, h);
      const base64 = canvas.toDataURL('image/png').split(',')[1];

      // 显示结果窗口
      showResultWindow('翻译中...', '', config);

      // 发送到翻译服务
      const resp = await sendMessage({
        type: 'TRANSLATE_IMAGE',
        base64,
      });

      if (resp.type === 'IMAGE_TRANSLATE_RESULT') {
        updateResultWindow(resp.original, resp.translated);
      } else if (resp.type === 'TRANSLATE_ERROR') {
        updateResultWindow('', `翻译失败: ${resp.error}`);
      }
    } catch (err) {
      showResultWindow('', `截图失败: ${err}`, config);
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

/** 截取页面区域（使用 Canvas + 视口捕获） */
async function captureRegion(x: number, y: number, w: number, h: number): Promise<HTMLCanvasElement> {
  // 注意：这里简化实现，实际需要 html2canvas 或 chrome.tabs.captureVisibleTab
  // 由于 content script 无法直接调用 captureVisibleTab，需要通过 background 中转
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;

  // 创建一个临时的截图（简化方案：使用 window.getComputedStyle 无法截屏）
  // 实际生产中需要引入 html2canvas 库或通过 background 调用 chrome API
  ctx.fillStyle = '#f0f0f0';
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = '#333';
  ctx.font = '14px sans-serif';
  ctx.fillText('截图翻译需要 Butler 后端支持', 10, 30);
  ctx.fillText('或引入 html2canvas 库', 10, 50);

  return canvas;
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
