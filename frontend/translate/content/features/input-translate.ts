/* ============================================================
   输入框翻译 — 在任意输入框内打中文，翻译成目标语言
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { detectLanguageQuick } from '../../utils/languages';

let isEnabled = true;

/** 初始化输入框翻译 */
export function initInputTranslate(config: TranslateConfig): void {
  document.addEventListener('keydown', (e) => {
    if (!isEnabled) return;

    // 检查快捷键（默认 Ctrl+Enter）
    const keys = config.inputTranslateKey.split('+').map(k => k.trim().toLowerCase());
    const match = keys.every(k => {
      if (k === 'ctrl') return e.ctrlKey || e.metaKey;
      if (k === 'alt') return e.altKey;
      if (k === 'shift') return e.shiftKey;
      if (k === 'enter') return e.key === 'Enter';
      return e.key.toLowerCase() === k;
    });

    if (!match) return;

    const target = e.target as HTMLElement;
    if (!isEditableElement(target)) return;

    const text = getElementText(target);
    if (!text || text.length < 2) return;

    e.preventDefault();
    e.stopPropagation();

    translateInputElement(target, text, config);
  });
}

function isEditableElement(el: HTMLElement): boolean {
  if (el.tagName === 'INPUT') {
    const type = (el as HTMLInputElement).type;
    return ['text', 'search', 'url', 'email', ''].includes(type);
  }
  if (el.tagName === 'TEXTAREA') return true;
  if (el.isContentEditable) return true;
  return false;
}

function getElementText(el: HTMLElement): string {
  if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
    return (el as HTMLInputElement | HTMLTextAreaElement).value;
  }
  if (el.isContentEditable) return el.innerText;
  return '';
}

function setElementText(el: HTMLElement, text: string): void {
  if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
    (el as HTMLInputElement | HTMLTextAreaElement).value = text;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  } else if (el.isContentEditable) {
    el.innerText = text;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }
}

async function translateInputElement(
  el: HTMLElement,
  text: string,
  config: TranslateConfig
): Promise<void> {
  // 检测语言
  const detected = detectLanguageQuick(text);

  // 如果已经是目标语言，翻译成英文（反向）
  const from = detected;
  const to = detected === config.targetLang ? 'en' : config.targetLang;

  // 显示翻译中状态
  const originalBg = el.style.backgroundColor;
  el.style.backgroundColor = '#fff3cd';
  el.style.transition = 'background-color 0.2s';

  try {
    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts: [text],
      to,
    });

    if (resp.type === 'TRANSLATE_RESULT') {
      const translated = resp.results[0]?.translated;
      if (translated) {
        setElementText(el, translated);
        el.style.backgroundColor = '#d4edda';
        setTimeout(() => { el.style.backgroundColor = originalBg; }, 1000);
      }
    }
  } catch (err) {
    el.style.backgroundColor = '#f8d7da';
    setTimeout(() => { el.style.backgroundColor = originalBg; }, 1000);
  }
}

export function enable(): void { isEnabled = true; }
export function disable(): void { isEnabled = false; }
