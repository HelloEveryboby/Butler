/* ============================================================
   Butler Translate — 语言列表（40+）+ Unicode script 语言检测
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
  // ---------- Phase 2 扩展：40+ 语言 ----------
  { code: 'hi', name: '印地语', nameEn: 'Hindi' },
  { code: 'bn', name: '孟加拉语', nameEn: 'Bengali' },
  { code: 'ur', name: '乌尔都语', nameEn: 'Urdu' },
  { code: 'fa', name: '波斯语', nameEn: 'Persian' },
  { code: 'he', name: '希伯来语', nameEn: 'Hebrew' },
  { code: 'el', name: '希腊语', nameEn: 'Greek' },
  { code: 'uk', name: '乌克兰语', nameEn: 'Ukrainian' },
  { code: 'bg', name: '保加利亚语', nameEn: 'Bulgarian' },
  { code: 'sr', name: '塞尔维亚语', nameEn: 'Serbian' },
  { code: 'hr', name: '克罗地亚语', nameEn: 'Croatian' },
  { code: 'cs', name: '捷克语', nameEn: 'Czech' },
  { code: 'sk', name: '斯洛伐克语', nameEn: 'Slovak' },
  { code: 'hu', name: '匈牙利语', nameEn: 'Hungarian' },
  { code: 'ro', name: '罗马尼亚语', nameEn: 'Romanian' },
  { code: 'da', name: '丹麦语', nameEn: 'Danish' },
  { code: 'fi', name: '芬兰语', nameEn: 'Finnish' },
  { code: 'sv', name: '瑞典语', nameEn: 'Swedish' },
  { code: 'no', name: '挪威语', nameEn: 'Norwegian' },
  { code: 'is', name: '冰岛语', nameEn: 'Icelandic' },
  { code: 'lt', name: '立陶宛语', nameEn: 'Lithuanian' },
  { code: 'lv', name: '拉脱维亚语', nameEn: 'Latvian' },
  { code: 'et', name: '爱沙尼亚语', nameEn: 'Estonian' },
  { code: 'sl', name: '斯洛文尼亚语', nameEn: 'Slovenian' },
  { code: 'ms', name: '马来语', nameEn: 'Malay' },
  { code: 'tl', name: '菲律宾语', nameEn: 'Filipino' },
  { code: 'sw', name: '斯瓦希里语', nameEn: 'Swahili' },
  { code: 'af', name: '南非荷兰语', nameEn: 'Afrikaans' },
  { code: 'ca', name: '加泰罗尼亚语', nameEn: 'Catalan' },
  { code: 'eu', name: '巴斯克语', nameEn: 'Basque' },
  { code: 'gl', name: '加利西亚语', nameEn: 'Galician' },
  { code: 'kk', name: '哈萨克语', nameEn: 'Kazakh' },
  { code: 'uz', name: '乌兹别克语', nameEn: 'Uzbek' },
  { code: 'my', name: '缅甸语', nameEn: 'Burmese' },
  { code: 'km', name: '高棉语', nameEn: 'Khmer' },
  { code: 'lo', name: '老挝语', nameEn: 'Lao' },
  { code: 'si', name: '僧伽罗语', nameEn: 'Sinhala' },
  { code: 'ta', name: '泰米尔语', nameEn: 'Tamil' },
  { code: 'te', name: '泰卢固语', nameEn: 'Telugu' },
  { code: 'kn', name: '卡纳达语', nameEn: 'Kannada' },
  { code: 'ml', name: '马拉雅拉姆语', nameEn: 'Malayalam' },
  { code: 'ne', name: '尼泊尔语', nameEn: 'Nepali' },
  { code: 'am', name: '阿姆哈拉语', nameEn: 'Amharic' },
  { code: 'ka', name: '格鲁吉亚语', nameEn: 'Georgian' },
  { code: 'hy', name: '亚美尼亚语', nameEn: 'Armenian' },
  { code: 'mn', name: '蒙古语', nameEn: 'Mongolian' },
  { code: 'sq', name: '阿尔巴尼亚语', nameEn: 'Albanian' },
  { code: 'mk', name: '马其顿语', nameEn: 'Macedonian' },
  { code: 'be', name: '白俄罗斯语', nameEn: 'Belarusian' },
  { code: 'cy', name: '威尔士语', nameEn: 'Welsh' },
  { code: 'ga', name: '爱尔兰语', nameEn: 'Irish' },
];

/** 语言代码 → 中文名 */
export function langName(code: string): string {
  return LANGUAGES.find(l => l.code === code)?.name ?? code;
}

/* ------------------------------------------------------------
   Unicode script 语言检测（纯函数，规则版，不调 API）
   优先级：具有唯一文字系统的语言（中/日/韩/泰/天城/西里尔/
   阿拉伯/希伯来/希腊/格鲁吉亚/亚美尼亚/缅甸/高棉/老挝）优先，
   拉丁字母语言（英/法/德/西…）无法用字符集区分，默认返回 en。
   ------------------------------------------------------------ */

/** 各文字系统的 Unicode 区段（字母/音节类，不含标点数字） */
const SCRIPT_PATTERNS: Array<{ re: RegExp; code: string }> = [
  // 假名（含长音）→ 优先于汉字判定日语
  { re: /[\u3040-\u309f\u30a0-\u30ff]/, code: 'ja' },
  // 谚文音节
  { re: /[\uac00-\ud7af\u1100-\u11ff]/, code: 'ko' },
  // 泰文
  { re: /[\u0e00-\u0e7f]/, code: 'th' },
  // 天城文（印地语 / 梵文）
  { re: /[\u0900-\u097f]/, code: 'hi' },
  // 孟加拉文
  { re: /[\u0980-\u09ff]/, code: 'bn' },
  // 乌尔都语使用阿拉伯文，靠附加字符区分难度大，交给阿拉伯文规则
  // 僧伽罗文
  { re: /[\u0d80-\u0dff]/, code: 'si' },
  // 缅甸文
  { re: /[\u1000-\u109f]/, code: 'my' },
  // 高棉文
  { re: /[\u1780-\u17ff]/, code: 'km' },
  // 老挝文
  { re: /[\u0e80-\u0eff]/, code: 'lo' },
  // 格鲁吉亚文
  { re: /[\u10a0-\u10ff]/, code: 'ka' },
  // 亚美尼亚文
  { re: /[\u0530-\u058f]/, code: 'hy' },
  // 希伯来文
  { re: /[\u0590-\u05ff]/, code: 'he' },
  // 希腊文
  { re: /[\u0370-\u03ff\u1f00-\u1fff]/, code: 'el' },
  // 西里尔文（俄/乌/保/塞…默认归俄语）
  { re: /[\u0400-\u04ff]/, code: 'ru' },
  // 阿拉伯文（含波斯/乌尔都附加区）
  { re: /[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]/, code: 'ar' },
  // 埃塞俄比亚文（阿姆哈拉语）
  { re: /[\u1200-\u137f]/, code: 'am' },
  // 泰米尔文
  { re: /[\u0b80-\u0bff]/, code: 'ta' },
  // 泰卢固文
  { re: /[\u0c00-\u0c7f]/, code: 'te' },
  // 卡纳达文
  { re: /[\u0c80-\u0cff]/, code: 'kn' },
  // 马拉雅拉姆文
  { re: /[\u0d00-\u0d7f]/, code: 'ml' },
  // 蒙古文（传统字母）
  { re: /[\u1800-\u18af]/, code: 'mn' },
];

/** 汉字（中日共有，无假名时归中文） */
const HAN_RE = /[\u4e00-\u9fff\u3400-\u4dbf]/;

/**
 * 简单语言检测（规则版，不调 API）。
 * 基于 Unicode 文字系统判定，覆盖天城文/泰文/韩文/西里尔/阿拉伯/
 * 希腊/希伯来/格鲁吉亚/亚美尼亚/缅甸/高棉/老挝等 20+ 文字系统；
 * 拉丁字母语言无法用字符集区分，统一返回 'en'。
 */
export function detectLanguageQuick(text: string): string {
  if (!text || !text.trim()) return 'en';

  for (const { re, code } of SCRIPT_PATTERNS) {
    if (re.test(text)) return code;
  }
  if (HAN_RE.test(text)) return 'zh-CN';
  return 'en'; // 默认英文（拉丁字母）
}
