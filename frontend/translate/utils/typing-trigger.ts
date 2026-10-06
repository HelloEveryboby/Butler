/* ============================================================
   输入框翻译触发判定 — 纯函数，便于单测
   ------------------------------------------------------------
   「三连空格」触发（对标沉浸式翻译）：
   光标前以「非空格 + 3 个连续空格」结尾时判定触发，
   触发后 3 个空格被吞掉（restText 不含它们）。
   4 个及以上连续空格不会反复触发（前一字符是空格则不匹配）。
   ============================================================ */

export interface TripleSpaceResult {
  triggered: boolean;
  /** 触发时去掉 3 个空格后的文本；未触发时原样返回 */
  restText: string;
}

/**
 * 判定三连空格触发。
 * @param text     输入框当前全文
 * @param caretPos 光标位置（默认取文本末尾）
 */
export function checkTripleSpace(text: string, caretPos?: number): TripleSpaceResult {
  const pos = caretPos ?? text.length;
  const before = text.slice(0, pos);
  // 非空格 + 恰好 3 个空格结尾
  if (!/(\S)[ ]{3}$/.test(before)) {
    return { triggered: false, restText: text };
  }
  const restText = before.slice(0, before.length - 3) + text.slice(pos);
  return { triggered: true, restText };
}

/** 快捷键判定（纯函数）：如 'Ctrl+Enter' / 'Alt+Shift+T' */
export function matchHotkey(
  spec: string,
  key: string,
  mods: { ctrl: boolean; alt: boolean; shift: boolean; meta: boolean }
): boolean {
  const keys = spec.split('+').map(k => k.trim().toLowerCase()).filter(Boolean);
  if (keys.length === 0) return false;
  const mainKey = keys[keys.length - 1];
  const needCtrl = keys.includes('ctrl') || keys.includes('control') || keys.includes('cmd');
  const needAlt = keys.includes('alt');
  const needShift = keys.includes('shift');

  if (needCtrl !== (mods.ctrl || mods.meta)) return false;
  if (needAlt !== mods.alt) return false;
  if (needShift !== mods.shift) return false;
  return key.toLowerCase() === mainKey;
}

/** 输入翻译方向 */
export type InputDirection = 'auto' | 'zh-to-foreign' | 'foreign-to-zh';

/**
 * 解析输入框翻译的目标语言（纯函数，支持中→外 / 外→中双向）：
 * - 'zh-to-foreign'：中文输入 → 外语（targetLang 为中文时降级为英文）
 * - 'foreign-to-zh'：外文输入 → 中文（简体）
 * - 'auto'：输入已是目标语言 → 互译为英文；否则译为目标语言
 */
export function resolveInputTargetLang(
  detected: string,
  targetLang: string,
  direction: InputDirection
): string {
  if (direction === 'foreign-to-zh') return 'zh-CN';
  if (direction === 'zh-to-foreign') return targetLang.startsWith('zh') ? 'en' : targetLang;
  const isSame = detected === targetLang || (detected.startsWith('zh') && targetLang.startsWith('zh'));
  return isSame ? 'en' : targetLang;
}
