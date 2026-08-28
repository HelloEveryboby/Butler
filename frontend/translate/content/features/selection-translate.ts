/* ============================================================
   划词翻译 — 选中文字后自动弹出翻译气泡
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { detectLanguageQuick } from '../../utils/languages';

let bubbleEl: HTMLDivElement | null = null;
let isEnabled = true;

/** 初始化划词翻译 */
export function initSelectionTranslate(config: TranslateConfig): void {
  document.addEventListener('mouseup', (e) => {
    if (!isEnabled) return;
    // 忽略来自气泡自身的点击
    if (bubbleEl?.contains(e.target as Node)) return;

    const selection = window.getSelection();
    const text = selection?.toString().trim();

    if (!text || text.length < 2 || text.length > 5000) {
      removeBubble();
      return;
    }

    // 检测语言，如果已经是目标语言则跳过
    const detected = detectLanguageQuick(text);
    if (detected === config.targetLang) return;

    // 获取选区位置
    const range = selection?.getRangeAt(0);
    const rect = range?.getBoundingClientRect();
    if (!rect) return;

    showBubble(rect, text, config);
  });

  // 按 Esc 关闭气泡
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') removeBubble();
  });
}

async function showBubble(rect: DOMRect, text: string, config: TranslateConfig): Promise<void> {
  removeBubble();

  // 创建气泡
  bubbleEl = document.createElement('div');
  bubbleEl.className = 'bt-bubble';
  bubbleEl.innerHTML = `
    <div class="bt-bubble-content">
      <div class="bt-bubble-loading">
        <span class="bt-spinner"></span> 翻译中...
      </div>
    </div>
    <div class="bt-bubble-actions" style="display:none">
      <button class="bt-bubble-copy" title="复制译文">📋</button>
      <button class="bt-bubble-close" title="关闭">✕</button>
    </div>
  `;

  // 定位
  const top = rect.bottom + window.scrollY + 8;
  const left = rect.left + window.scrollX;
  bubbleEl.style.top = `${top}px`;
  bubbleEl.style.left = `${Math.min(left, window.innerWidth - 320)}px`;

  document.body.appendChild(bubbleEl);

  // 事件绑定
  bubbleEl.querySelector('.bt-bubble-close')?.addEventListener('click', removeBubble);
  bubbleEl.querySelector('.bt-bubble-copy')?.addEventListener('click', () => {
    const content = bubbleEl?.querySelector('.bt-bubble-content')?.textContent || '';
    navigator.clipboard.writeText(content);
    // 短暂提示已复制
    const copyBtn = bubbleEl?.querySelector('.bt-bubble-copy');
    if (copyBtn) {
      copyBtn.textContent = '✓';
      setTimeout(() => { copyBtn.textContent = '📋'; }, 1000);
    }
  });

  // 翻译
  try {
    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts: [text],
      to: config.targetLang,
    });

    if (resp.type === 'TRANSLATE_RESULT' && bubbleEl) {
      const translated = resp.results[0]?.translated || '翻译失败';
      bubbleEl.querySelector('.bt-bubble-content')!.innerHTML = translated;
      bubbleEl.querySelector('.bt-bubble-actions')!.style.display = 'flex';
    }
  } catch (err) {
    if (bubbleEl) {
      bubbleEl.querySelector('.bt-bubble-content')!.innerHTML = `<span class="bt-error">翻译失败: ${err}</span>`;
    }
  }
}

function removeBubble(): void {
  bubbleEl?.remove();
  bubbleEl = null;
}

export function enable(): void { isEnabled = true; }
export function disable(): void { isEnabled = false; removeBubble(); }
