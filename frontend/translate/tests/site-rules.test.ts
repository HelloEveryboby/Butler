/* ============================================================
   单元测试 — 站点规则匹配 + 自定义规则导入导出
   ============================================================ */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  getSiteRules,
  getSiteSelectors,
  getSiteExcludes,
  parseCustomRules,
  serializeCustomRules,
  mergeSiteRules,
  getBuiltinRules,
} from '../content/dom/site-rules';

test('内置规则 ≥ 30 条域名规则（不含通用 fallback）', () => {
  const builtin = getBuiltinRules();
  const domainRules = builtin.filter(r => typeof r.domain === 'string');
  assert.ok(domainRules.length >= 30, `域名规则数 ${domainRules.length} < 30`);
});

test('站点匹配：GitHub / arXiv / HN / 掘金 / ReadTheDocs', () => {
  const gh = getSiteRules('github.com');
  assert.ok(gh && gh.selectors?.includes('.markdown-body'));
  assert.ok(gh?.exclude?.includes('pre code'));

  const arxiv = getSiteRules('arxiv.org');
  assert.ok(arxiv && arxiv.selectors?.includes('#abs'));

  const hn = getSiteRules('news.ycombinator.com');
  assert.ok(hn && hn.selectors?.includes('.commtext'));

  const juejin = getSiteRules('juejin.cn');
  assert.ok(juejin && juejin.selectors?.includes('.article-content'));

  const rtd = getSiteRules('butler.readthedocs.io');
  assert.ok(rtd && rtd.selectors?.length);
});

test('邮件 / 会议站点规则注册', () => {
  const gmail = getSiteRules('mail.google.com');
  assert.ok(gmail && gmail.selectors?.includes('.a3s.aiL'));
  const outlook = getSiteRules('outlook.live.com');
  assert.ok(outlook && outlook.selectors?.length);
});

test('未知站点回退到通用规则', () => {
  const rule = getSiteRules('unknown-site.example.org');
  assert.ok(rule);
  assert.ok(rule!.selectors?.includes('article'));
});

test('自定义规则优先于内置规则', () => {
  const custom = parseCustomRules(JSON.stringify([
    { domain: 'github.com', selectors: ['.my-custom'], exclude: ['nav'] },
  ]));
  assert.equal(custom.rules.length, 1);
  const rule = getSiteRules('github.com', custom.rules);
  assert.deepEqual(rule?.selectors, ['.my-custom']);
});

test('自定义规则导入：非法条目跳过并报告', () => {
  const bad = parseCustomRules('{not json');
  assert.equal(bad.rules.length, 0);
  assert.ok(bad.error);

  const mixed = parseCustomRules(JSON.stringify([
    { domain: 'example.com', selectors: ['article'] },
    { foo: 'bar' },
    42,
  ]));
  assert.equal(mixed.rules.length, 1);
  assert.ok(mixed.error?.includes('2')); // 第 2、3 条非法

  const wrongShape = parseCustomRules('{"nope": 1}');
  assert.equal(wrongShape.rules.length, 0);
  assert.ok(wrongShape.error);
});

test('自定义规则导出：serialize 与 parse 往返', () => {
  const json = serializeCustomRules([
    { domain: 'example.com', selectors: ['article', 'main'], exclude: ['pre'] },
  ]);
  const { rules, error } = parseCustomRules(json);
  assert.equal(error, undefined);
  assert.equal(rules.length, 1);
  assert.equal(rules[0].domain, 'example.com');
  assert.deepEqual(rules[0].selectors, ['article', 'main']);
});

test('mergeSiteRules：自定义在前、fallback 殿后', () => {
  const merged = mergeSiteRules([{ domain: 'custom-site.com', selectors: ['.x'] }]);
  assert.equal(merged[0].domain, 'custom-site.com');
  assert.ok(merged[merged.length - 1].domain instanceof RegExp);
});

test('getSiteSelectors / getSiteExcludes 透传', () => {
  assert.ok(getSiteSelectors('medium.com').includes('article section'));
  assert.ok(getSiteExcludes('wikipedia.org').includes('.infobox'));
});
