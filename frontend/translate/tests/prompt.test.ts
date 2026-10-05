/* ============================================================
   单元测试 — 术语进 prompt 的构造（双保险前半部分）
   ============================================================ */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildGlossaryConstraint,
  mergeTerms,
  buildSystemPrompt,
  buildContextPrompt,
  parseContextResponse,
} from '../background/prompt';

test('术语强制约束格式：- "X" 必须译为 "Y"', () => {
  const out = buildGlossaryConstraint([
    { source: 'API Gateway', target: 'API 网关' },
    { source: 'cache', target: '缓存' },
  ]);
  assert.ok(out.startsWith('术语强制约束'));
  assert.ok(out.includes('"API Gateway" 必须译为 "API 网关"'));
  assert.ok(out.includes('"cache" 必须译为 "缓存"'));
});

test('空术语表输出空字符串（不注入噪声）', () => {
  assert.equal(buildGlossaryConstraint([]), '');
  assert.equal(buildGlossaryConstraint([{ source: '', target: '' }] as any), '');
});

test('mergeTerms：术语表优先于上下文候选，长词优先排序', () => {
  const merged = mergeTerms(
    [{ source: 'US', target: '美国' }],
    [
      { source: 'us', target: '美利坚' },      // 与术语表冲突（忽略大小写）→ 术语表胜
      { source: 'machine learning', target: '机器学习' },
    ]
  );
  const us = merged.find(t => t.source.toLowerCase() === 'us');
  assert.equal(us?.target, '美国');
  // 长词排前
  assert.ok(merged[0].source.length >= merged[merged.length - 1].source.length);
});

test('buildSystemPrompt：基础指令 + 预设 + 上下文摘要 + 术语约束', () => {
  const prompt = buildSystemPrompt(
    '请将以下{from}文本翻译为{to}，只输出译文。',
    '英语',
    '中文（简体）',
    {
      glossary: [{ source: 'transformer', target: '变换器' }],
      context: {
        summary: '本文介绍 Transformer 架构。',
        terms: [{ source: 'attention', target: '注意力' }],
      },
      preset: {
        id: 'tech-doc',
        name: '技术文档',
        identity: '你是一名资深技术文档译员。',
        tone: '准确',
        termStyle: '社区通用译法',
        rules: { numbers: '原样保留', units: '保留符号', code: '不翻译' },
      },
    }
  );

  // 基础指令占位符替换
  assert.ok(prompt.includes('请将以下英语文本翻译为中文（简体）'));
  // 预设
  assert.ok(prompt.includes('你是一名资深技术文档译员'));
  // 上下文摘要
  assert.ok(prompt.includes('本文介绍 Transformer 架构'));
  // 术语进 prompt（术语表 + 候选都出现）
  assert.ok(prompt.includes('"transformer" 必须译为 "变换器"'));
  assert.ok(prompt.includes('"attention" 必须译为 "注意力"'));
});

test('buildSystemPrompt：无选项时只输出基础指令', () => {
  const prompt = buildSystemPrompt('translate {from} to {to}', 'en', 'zh-CN');
  assert.equal(prompt, 'translate en to zh-CN');
});

test('buildContextPrompt：严格 JSON 指令 + 术语候选', () => {
  const p = buildContextPrompt('一些网页文本', ['Kubernetes', 'Pod']);
  assert.ok(p.includes('严格 JSON'));
  assert.ok(p.includes('Kubernetes、Pod'));
  assert.ok(p.includes('一些网页文本'));
});

test('parseContextResponse：标准 JSON / 代码块包裹 / 脏输出', () => {
  const ctx1 = parseContextResponse('{"summary":"概要","terms":[{"source":"a","target":"b"}]}');
  assert.equal(ctx1?.summary, '概要');
  assert.deepEqual(ctx1?.terms, [{ source: 'a', target: 'b' }]);

  const ctx2 = parseContextResponse('```json\n{"summary":"x","terms":[]}\n```');
  assert.equal(ctx2?.summary, 'x');

  const ctx3 = parseContextResponse('这是解释文字 {"summary":"y","terms":[]} 结尾');
  assert.equal(ctx3?.summary, 'y');

  assert.equal(parseContextResponse('完全不是 JSON'), null);
  assert.equal(parseContextResponse('{broken'), null);
  assert.equal(parseContextResponse('{"summary":"","terms":[]}'), null);
});
