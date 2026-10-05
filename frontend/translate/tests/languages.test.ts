/* ============================================================
   单元测试 — 语言检测（Unicode script）
   ============================================================ */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { detectLanguageQuick, LANGUAGES, langName } from '../utils/languages';

test('CJK 检测：中文 / 日文 / 韩文', () => {
  assert.equal(detectLanguageQuick('这是一段中文文本'), 'zh-CN');
  assert.equal(detectLanguageQuick('これは日本語のテキストです'), 'ja');
  assert.equal(detectLanguageQuick('이것은 한국어 텍스트입니다'), 'ko');
  // 汉字 + 假名 → 日文（假名优先）
  assert.equal(detectLanguageQuick('日本語のテキストです'), 'ja');
});

test('Unicode script 检测：天城文 / 泰文 / 西里尔 / 阿拉伯 / 希腊 / 希伯来', () => {
  assert.equal(detectLanguageQuick('यह हिन्दी पाठ है'), 'hi');       // 天城文
  assert.equal(detectLanguageQuick('นี่คือข้อความภาษาไทย'), 'th');   // 泰文
  assert.equal(detectLanguageQuick('Это русский текст'), 'ru');      // 西里尔
  assert.equal(detectLanguageQuick('هذا نص عربي'), 'ar');            // 阿拉伯
  assert.equal(detectLanguageQuick('Αυτό είναι ελληνικό κείμενο'), 'el'); // 希腊
  assert.equal(detectLanguageQuick('זהו טקסט בעברית'), 'he');        // 希伯来
});

test('Unicode script 检测：格鲁吉亚 / 亚美尼亚 / 缅甸 / 高棉 / 老挝 / 阿姆哈拉', () => {
  assert.equal(detectLanguageQuick('ეს არის ქართული ტექსტი'), 'ka');
  assert.equal(detectLanguageQuick('Սա հայերեն տեքստ է'), 'hy');
  assert.equal(detectLanguageQuick('ဤသည် မြန်မာစာ ဖြစ်သည်'), 'my');
  assert.equal(detectLanguageQuick('នេះជាអត្ថបទខ្មែរ'), 'km');
  assert.equal(detectLanguageQuick('ນີ້ແມ່ນຂໍ້ຄວາມພາສາລາວ'), 'lo');
  assert.equal(detectLanguageQuick('ይህ የአማርኛ ጽሑፍ ነው'), 'am');
});

test('拉丁字母语言无法用字符集区分，默认 en', () => {
  assert.equal(detectLanguageQuick('This is English text'), 'en');
  assert.equal(detectLanguageQuick('Ceci est du français'), 'en');
  assert.equal(detectLanguageQuick('Dies ist deutscher Text'), 'en');
});

test('空文本兜底', () => {
  assert.equal(detectLanguageQuick(''), 'en');
  assert.equal(detectLanguageQuick('   '), 'en');
});

test('语言表 40+ 且代码唯一', () => {
  assert.ok(LANGUAGES.length >= 40, `语言数量 ${LANGUAGES.length} < 40`);
  const codes = new Set(LANGUAGES.map(l => l.code));
  assert.equal(codes.size, LANGUAGES.length);
  assert.ok(langName('zh-CN').includes('中文'));
});
