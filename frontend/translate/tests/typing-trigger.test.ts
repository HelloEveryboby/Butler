/* ============================================================
   单元测试 — 三连空格触发判定 + 快捷键 + 输入方向
   ============================================================ */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  checkTripleSpace,
  matchHotkey,
  resolveInputTargetLang,
} from '../utils/typing-trigger';

test('三连空格触发：吞掉 3 个空格', () => {
  const r = checkTripleSpace('hello   ');
  assert.equal(r.triggered, true);
  assert.equal(r.restText, 'hello');
});

test('两连空格不触发', () => {
  const r = checkTripleSpace('hello  ');
  assert.equal(r.triggered, false);
  assert.equal(r.restText, 'hello  ');
});

test('四个及以上空格不触发（避免重复触发）', () => {
  assert.equal(checkTripleSpace('hello    ').triggered, false);
  assert.equal(checkTripleSpace('hello     ').triggered, false);
});

test('光标前判定（后面还有内容）', () => {
  const r = checkTripleSpace('hello   world', 8);
  assert.equal(r.triggered, true);
  assert.equal(r.restText, 'helloworld');
});

test('行首 3 个空格不触发（前面必须有非空格内容）', () => {
  assert.equal(checkTripleSpace('   ').triggered, false);
  assert.equal(checkTripleSpace('').triggered, false);
});

test('中文输入三连空格同样触发', () => {
  const r = checkTripleSpace('你好世界   ');
  assert.equal(r.triggered, true);
  assert.equal(r.restText, '你好世界');
});

test('matchHotkey：Ctrl+Enter / Alt+Shift+T', () => {
  assert.ok(matchHotkey('Ctrl+Enter', 'Enter', { ctrl: true, alt: false, shift: false, meta: false }));
  assert.ok(!matchHotkey('Ctrl+Enter', 'Enter', { ctrl: false, alt: false, shift: false, meta: false }));
  // Mac 的 Meta 也认作 Ctrl
  assert.ok(matchHotkey('Ctrl+Enter', 'Enter', { ctrl: false, alt: false, shift: false, meta: true }));
  assert.ok(matchHotkey('Alt+Shift+T', 't', { ctrl: false, alt: true, shift: true, meta: false }));
  assert.ok(!matchHotkey('Alt+Shift+T', 't', { ctrl: false, alt: true, shift: false, meta: false }));
});

test('输入方向：双向自动切换', () => {
  // 中文输入 + 目标中文 → 互译为英文
  assert.equal(resolveInputTargetLang('zh-CN', 'zh-CN', 'auto'), 'en');
  // 英文输入 + 目标中文 → 中文
  assert.equal(resolveInputTargetLang('en', 'zh-CN', 'auto'), 'zh-CN');
  // 日文输入 + 目标中文 → 中文
  assert.equal(resolveInputTargetLang('ja', 'zh-CN', 'auto'), 'zh-CN');
});

test('输入方向：强制中→外 / 外→中', () => {
  assert.equal(resolveInputTargetLang('zh-CN', 'en', 'zh-to-foreign'), 'en');
  // 目标是中文时降级为英文（中→外）
  assert.equal(resolveInputTargetLang('zh-CN', 'zh-CN', 'zh-to-foreign'), 'en');
  assert.equal(resolveInputTargetLang('en', 'en', 'foreign-to-zh'), 'zh-CN');
  assert.equal(resolveInputTargetLang('ja', 'en', 'foreign-to-zh'), 'zh-CN');
});
