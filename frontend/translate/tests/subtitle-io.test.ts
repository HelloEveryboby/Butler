/* ============================================================
   单元测试 — 字幕解析 / 双语序列化（SRT / VTT）
   核心断言：时间轴不动、每条 cue 两行、VTT 保留 WEBVTT 头
   ============================================================ */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  parseSrt,
  parseVtt,
  parseSubtitle,
  parseTimestamp,
  parseTimingLine,
  bilingualCueText,
  makeBilingualCues,
  serializeSrt,
  serializeVtt,
  makeCue,
  formatSrtTimestamp,
} from '../utils/subtitle-io';

const SRT = `1
00:00:01,000 --> 00:00:04,500
Hello world

2
00:00:05,000 --> 00:00:08,200
Second line
with wrap
`;

test('SRT 解析：序号 / 时间轴 / 文本', () => {
  const doc = parseSrt(SRT);
  assert.equal(doc.cues.length, 2);
  assert.equal(doc.cues[0].index, 1);
  assert.equal(doc.cues[0].timing, '00:00:01,000 --> 00:00:04,500');
  assert.equal(doc.cues[0].startMs, 1000);
  assert.equal(doc.cues[0].endMs, 4500);
  assert.equal(doc.cues[0].text, 'Hello world');
  assert.equal(doc.cues[1].text, 'Second line\nwith wrap');
});

test('SRT 双语序列化：时间轴不动、每条 cue 两行', () => {
  const doc = parseSrt(SRT);
  const bilingual = makeBilingualCues(doc.cues, ['你好世界', '第二行\n换行']);
  const out = serializeSrt(bilingual);

  // 时间轴行逐字不动
  assert.ok(out.includes('1\n00:00:01,000 --> 00:00:04,500'));
  assert.ok(out.includes('00:00:01,000 --> 00:00:04,500'));
  assert.ok(out.includes('00:00:05,000 --> 00:00:08,200'));

  // 每条 cue 两行文本（原文 + 译文，多行折叠）
  const lines = out.split('\n');
  const firstCueText = lines.slice(2, 4).join('\n');
  assert.equal(firstCueText, 'Hello world\n你好世界');
  assert.ok(out.includes('Second line with wrap\n第二行 换行'));

  // 重新解析后时间轴保持一致
  const reparsed = parseSrt(out);
  assert.equal(reparsed.cues[0].startMs, 1000);
  assert.equal(reparsed.cues[0].endMs, 4500);
  assert.equal(reparsed.cues[1].startMs, 5000);
  assert.equal(reparsed.cues[1].endMs, 8200);
});

const VTT = `WEBVTT - 测试字幕
Kind: captions

intro
00:00:01.000 --> 00:00:04.500 line:90%
Hello world

00:00:05.000 --> 00:00:08.200
Second cue
`;

test('VTT 解析：WEBVTT 头保留 / cue 标识 / settings', () => {
  const doc = parseVtt(VTT);
  assert.equal(doc.format, 'vtt');
  assert.ok(doc.header.startsWith('WEBVTT'));
  assert.ok(doc.header.includes('Kind: captions'));
  assert.equal(doc.cues.length, 2);
  assert.equal(doc.cues[0].cueId, 'intro');
  // 右侧 settings 保留在原始时间行里
  assert.ok(doc.cues[0].timing.includes('line:90%'));
  assert.equal(doc.cues[0].startMs, 1000);
});

test('VTT 双语序列化：WEBVTT 头保留、时间轴不动', () => {
  const doc = parseVtt(VTT);
  const bilingual = makeBilingualCues(doc.cues, ['你好世界', undefined]);
  const out = serializeVtt({ header: doc.header, cues: bilingual });

  assert.ok(out.startsWith('WEBVTT'));
  assert.ok(out.includes('Kind: captions'));
  assert.ok(out.includes('00:00:01.000 --> 00:00:04.500 line:90%'));
  assert.ok(out.includes('00:00:05.000 --> 00:00:08.200'));
  // 第一条双语（两行），第二条无译文保留原文
  assert.ok(out.includes('Hello world\n你好世界'));
  assert.ok(out.includes('Second cue\n\n') || out.trim().endsWith('Second cue'));
});

test('时间戳解析兼容 SRT 逗号 / VTT 句点 / 短格式', () => {
  assert.equal(parseTimestamp('00:00:01,500'), 1500);
  assert.equal(parseTimestamp('00:00:01.500'), 1500);
  assert.equal(parseTimestamp('0:01:02.250'), 62250);
  assert.equal(parseTimestamp('01:00:00,000'), 3600000);
  const [s, e] = parseTimingLine('00:00:01.000 --> 00:00:04.500 line:90%');
  assert.equal(s, 1000);
  assert.equal(e, 4500);
});

test('bilingualCueText：每条 cue 两行（多行折叠）', () => {
  assert.equal(bilingualCueText('a\nb', 'c\nd'), 'a b\nc d');
  assert.equal(bilingualCueText('only', 'y'), 'only\ny');
});

test('makeCue / serializeSrt 时间戳格式', () => {
  const cue = makeCue(1, 1500, 4500, 'x');
  assert.equal(cue.timing, `${formatSrtTimestamp(1500)} --> ${formatSrtTimestamp(4500)}`);
  const out = serializeSrt([cue]);
  assert.ok(out.startsWith('1\n00:00:01,500 --> 00:00:04,500\n'));
});

test('Windows 换行（\\r\\n）也能解析', () => {
  const doc = parseSubtitle(SRT.replace(/\n/g, '\r\n'), 'srt');
  assert.equal(doc.cues.length, 2);
  assert.equal(doc.cues[0].text, 'Hello world');
});
