/* ============================================================
   剪贴板翻译 — 复制外语自动翻译
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { detectLanguageQuick } from '../../utils/languages';

let isEnabled = false; // 默认关闭，需用户开启
let lastClipboard = '';
let toastEl: HTMLDivElement | null = null;

/** 初始化剪贴板翻译 */
export function initClipboardTranslate(config: TranslateConfig): void {
  // 监听复制事件
  document.addEventListener('copy', () => {
    if (!isEnabled) return;
    setTimeout(() => handleClipboard(config), 100);
  });
}

async function handleClipboard(config: TranslateConfig): Promise<void> {
  try {
    const text = await navigator.clipboard.readText();
    if (!text || text.length < 2 || text.length > 5000) return;
    if (text === lastClipboard) return;
    lastClipboard = text;

    const detected = detectLanguageQuick(text);
    if (detected === config.targetLang) return;

    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts: [text],
      to: config.targetLang,
    });

    if (resp.type === 'TRANSLATE_RESULT') {
      const translated = resp.results[0]?.translated;
      if (translated) {
        showToast(text, translated);
      }
    }
  } catch (err) {
    // clipboard read 可能因权限失败，静默忽略
  }
}

function showToast(original: string, translated: string): void {
  removeToast();

  toastEl = document.createElement('div');
  toastEl.className = 'bt-clipboard-toast';
  toastEl.innerHTML = `
    <div class="bt-clipboard-header">
      <span>📋 剪贴板已翻译</span>
      <button class="bt-clipboard-close">✕</button>
    </div>
    <div class="bt-clipboard-body">
      <div class="bt-clipboard-original">${escapeHtml(original.slice(0, 200))}</div>
      <div class="bt-clipboard-translated">${escapeHtml(translated)}</div>
    </div>
    <div class="bt-clipboard-actions">
      <button class="bt-clipboard-copy">📋 复制译文</button>
    </div>
  `;

  document.body.appendChild(toastEl);

  toastEl.querySelector('.bt-clipboard-close')?.addEventListener('click', removeToast);
  toastEl.querySelector('.bt-clipboard-copy')?.addEventListener('click', () => {
    navigator.clipboard.writeText(translated);
    const btn = toastEl?.querySelector('.bt-clipboard-copy');
    if (btn) {
      btn.textContent = '✓ 已复制';
      setTimeout(removeToast, 1000);
    }
  });

  // 10 秒后自动关闭
  setTimeout(removeToast, 10000);
}

function removeToast(): void {
  toastEl?.remove();
  toastEl = null;
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function enable(): void { isEnabled = true; }
export function disable(): void { isEnabled = false; removeToast(); }
export function toggle(): boolean { isEnabled = !isEnabled; return isEnabled; }
