/* ============================================================
   单元测试 — 术语表 applyGlossary
   运行：npm test
   ============================================================ */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { applyGlossary } from '../background/glossary';

test('空术语表 / 空文本原样返回', () => {
  assert.equal(applyGlossary('hello world', []), 'hello world');
  assert.equal(applyGlossary('', [{ source: 'a', target: 'b' }]), '');
  assert.equal(applyGlossary('hello', [{ source: '', target: 'b' }]), 'hello');
});

test('基础替换', () => {
  const out = applyGlossary('the cat sat', [{ source: 'cat', target: '猫' }]);
  assert.equal(out, 'the 猫 sat');
});

test('词边界保护：US 不会吃掉 focus / USB', () => {
  const g = [{ source: 'US', target: '美国' }];

  // 焦点 1：focus 中的 "us" 不能被替换
  assert.equal(applyGlossary('focus on this', g), 'focus on this');

  // 焦点 2：USB 中的 "US" 不能被替换
  assert.equal(applyGlossary('USB drive', g), 'USB drive');

  // 焦点 3：独立的 us / US 要替换，且大小写不敏感
  assert.equal(applyGlossary('in the US', g), 'in the 美国');
  assert.equal(applyGlossary('in the us', g), 'in the 美国');
});

test('长词优先：USB 先于 US 匹配', () => {
  const g = [
    { source: 'US', target: '美国' },
    { source: 'USB', target: '通用串行总线' },
  ];
  assert.equal(applyGlossary('USB and US', g), '通用串行总线 and 美国');
});

test('CJK 词不做词边界（中文无空格分词）', () => {
  const g = [{ source: '中国', target: 'China' }];
  assert.equal(applyGlossary('中国的经济', g), 'China的经济');
});

test('正则元字符按字面匹配，不会抛异常', () => {
  const g = [{ source: 'C++', target: 'C加加' }];
  assert.equal(applyGlossary('learn C++ and C#', g), 'learn C加加 and C#');
});

test('大小写不敏感', () => {
  const g = [{ source: 'OpenAI', target: '开放人工智能' }];
  assert.equal(applyGlossary('openai and OPENAI and OpenAI', g), '开放人工智能 and 开放人工智能 and 开放人工智能');
});

test('多条术语同时生效', () => {
  const g = [
    { source: 'machine learning', target: '机器学习' },
    { source: 'neural network', target: '神经网络' },
  ];
  assert.equal(
    applyGlossary('machine learning uses neural network', g),
    '机器学习 uses 神经网络'
  );
});

test('替换结果不被后续术语二次替换', () => {
  // A→B，B→C：文本中的 A 应只变成 B，不能连环变成 C
  const g = [
    { source: 'A', target: 'B' },
    { source: 'B', target: 'C' },
  ];
  assert.equal(applyGlossary('A', g), 'B');
});
