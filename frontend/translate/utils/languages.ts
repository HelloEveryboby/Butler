/* ============================================================
   Butler Translate — 语言列表
   ============================================================ */

import { LangItem } from './types';

export const LANGUAGES: LangItem[] = [
  { code: 'zh-CN', name: '中文（简体）', nameEn: 'Chinese (Simplified)' },
  { code: 'zh-TW', name: '中文（繁体）', nameEn: 'Chinese (Traditional)' },
  { code: 'en', name: '英语', nameEn: 'English' },
  { code: 'ja', name: '日语', nameEn: 'Japanese' },
  { code: 'ko', name: '韩语', nameEn: 'Korean' },
  { code: 'fr', name: '法语', nameEn: 'French' },
  { code: 'de', name: '德语', nameEn: 'German' },
  { code: 'es', name: '西班牙语', nameEn: 'Spanish' },
  { code: 'pt', name: '葡萄牙语', nameEn: 'Portuguese' },
  { code: 'ru', name: '俄语', nameEn: 'Russian' },
  { code: 'ar', name: '阿拉伯语', nameEn: 'Arabic' },
  { code: 'it', name: '意大利语', nameEn: 'Italian' },
  { code: 'th', name: '泰语', nameEn: 'Thai' },
  { code: 'vi', name: '越南语', nameEn: 'Vietnamese' },
  { code: 'id', name: '印尼语', nameEn: 'Indonesian' },
  { code: 'nl', name: '荷兰语', nameEn: 'Dutch' },
  { code: 'pl', name: '波兰语', nameEn: 'Polish' },
  { code: 'tr', name: '土耳其语', nameEn: 'Turkish' },
];

/** 语言代码 → 中文名 */
export function langName(code: string): string {
  return LANGUAGES.find(l => l.code === code)?.name ?? code;
}

/** 简单语言检测（规则版，不调 API） */
export function detectLanguageQuick(text: string): string {
  if (/[\u4e00-\u9fff]/.test(text)) return 'zh-CN';
  if (/[\u3040-\u309f\u30a0-\u30ff]/.test(text)) return 'ja';
  if (/[\uac00-\ud7af]/.test(text)) return 'ko';
  if (/[\u0400-\u04ff]/.test(text)) return 'ru';
  if (/[\u0600-\u06ff]/.test(text)) return 'ar';
  if (/[\u0e00-\u0e7f]/.test(text)) return 'th';
  return 'en'; // 默认英文
}
