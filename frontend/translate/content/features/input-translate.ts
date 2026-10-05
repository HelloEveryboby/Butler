/* ============================================================
   输入框翻译 — 在任意输入框内打字，一键/三连空格翻译
   ------------------------------------------------------------
   触发方式：
   1. 快捷键（默认 Ctrl+Enter，可配置 inputTranslateKey）
   2. 三连空格（对标沉浸式翻译，可配置 inputTripleSpace）：
      光标前「非空格 + 3 个连续空格」触发，3 个空格被吞掉
   方向：中→外 / 外→中双向（inputDirection: auto / zh-to-foreign / foreign-to-zh）
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { detectLanguageQuick } from '../../utils/languages';
import {
  checkTripleSpace,
  matchHotkey,
  resolveInputTargetLang,
} from '../../utils/typing-trigger';

let isEnabled = true;

/** 初始化输入框翻译 */
export function initInputTranslate(config: TranslateConfig): void {
  // 快捷键触发（input / textarea / contentEditable 通用）
  document.addEventListener('keydown', (e) => {
    if (!isEnabled) return;

    const match = matchHotkey(config.inputTranslateKey, e.key, {
      ctrl: e.ctrlKey,
      alt: e.altKey,
      shift: e.shiftKey,
      meta: e.metaKey,
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

  // 三连空格触发（input / textarea；contentEditable 的光标文本节点定位不稳定，
  // 仅支持快捷键触发 —— 不静默失败，见设置页说明）
  document.addEventListener('keyup', (e) => {
    if (!isEnabled || !config.inputTripleSpace) return;
    if (e.key !== ' ') return;

    const target = e.target as HTMLElement;
    if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') return;
    if (!isEditableElement(target)) return;

    const field = target as HTMLInputElement | HTMLTextAreaElement;
    const caret = field.selectionStart ?? field.value.length;
    const check = checkTripleSpace(field.value, caret);
    if (!check.triggered) return;

    // 吞掉 3 个空格并翻译
    field.value = check.restText;
    const newCaret = Math.max(0, caret - 3);
    try {
      field.setSelectionRange(newCaret, newCaret);
    } catch {
      /* number 等 input 不支持 setSelectionRange，忽略 */
    }
    field.dispatchEvent(new Event('input', { bubbles: true }));

    const text = check.restText.trim();
    if (text.length >= 2) {
      translateInputElement(target, text, config);
    }
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
  // 双向：中→外 / 外→中（auto 自动判断，可强制方向）
  const detected = detectLanguageQuick(text);
  const to = resolveInputTargetLang(detected, config.targetLang, config.inputDirection || 'auto');

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
