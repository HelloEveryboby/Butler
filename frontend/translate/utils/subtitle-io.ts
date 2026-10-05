/* ============================================================
   字幕解析 / 双语序列化（SRT / VTT）— 纯函数，便于单测
   ------------------------------------------------------------
   核心保证：
   1. 时间轴不动：序列化时原样输出解析时保存的时间行
   2. 双语导出：每条 cue 两行（原文 + 译文），序号自动重排
   3. VTT 保留 WEBVTT 头（含头部元数据行）
   ============================================================ */

/** 一条字幕 cue */
export interface SubtitleCue {
  /** SRT 序号（解析时保留，序列化时按顺序重排） */
  index?: number;
  /** VTT cue 标识行（可选） */
  cueId?: string;
  /** 原始时间行（例如 "00:00:01,000 --> 00:00:04,000"），序列化原样输出 */
  timing: string;
  /** 起止毫秒（便于构造新 cue） */
  startMs: number;
  endMs: number;
  /** cue 文本（多行用 \n 连接） */
  text: string;
}

/** 解析结果 */
export interface SubtitleDoc {
  format: 'srt' | 'vtt';
  /** VTT 头（"WEBVTT" 及其后的元数据行，不含结尾空行）；SRT 为空字符串 */
  header: string;
  cues: SubtitleCue[];
}

/** 时间戳 → 毫秒。兼容 SRT 逗号与 VTT 句点毫秒，兼容 0:00:01.000 短格式 */
export function parseTimestamp(ts: string): number {
  const m = ts.trim().match(/^(?:(\d+):)?(\d{1,2}):(\d{1,2})[,.](\d{1,3})$/);
  if (!m) return 0;
  const h = m[1] ? parseInt(m[1], 10) : 0;
  const min = parseInt(m[2], 10);
  const s = parseInt(m[3], 10);
  const ms = parseInt(m[4].padEnd(3, '0'), 10);
  return ((h * 60 + min) * 60 + s) * 1000 + ms;
}

/** 解析时间轴行，返回 [起始毫秒, 结束毫秒]；解析失败返回 [0, 0] */
export function parseTimingLine(line: string): [number, number] {
  const parts = line.split('-->');
  if (parts.length !== 2) return [0, 0];
  // VTT 时间行右侧可能带 settings（"00:00:01.000 --> 00:00:04.000 line:90%"）
  const endToken = parts[1].trim().split(/\s+/)[0];
  return [parseTimestamp(parts[0]), parseTimestamp(endToken)];
}

/** 判断是否是时间轴行 */
function isTimingLine(line: string): boolean {
  return line.includes('-->');
}

/** 解析 SRT 文本 */
export function parseSrt(content: string): SubtitleDoc {
  return parseSubtitle(content, 'srt');
}

/** 解析 VTT 文本（保留 WEBVTT 头） */
export function parseVtt(content: string): SubtitleDoc {
  return parseSubtitle(content, 'vtt');
}

/** 统一解析（SRT / VTT 结构几乎一致） */
export function parseSubtitle(content: string, format: 'srt' | 'vtt'): SubtitleDoc {
  const normalized = content.replace(/\r\n?/g, '\n');
  let header = '';
  let body = normalized;

  if (format === 'vtt') {
    // WEBVTT 头：首行 "WEBVTT" 起，到第一个空行结束
    const headerMatch = normalized.match(/^WEBVTT[^\n]*\n(?:[^\n]+\n)*?(?:\n|$)/);
    if (headerMatch) {
      header = headerMatch[0].replace(/\n+$/, '');
      body = normalized.slice(headerMatch[0].length);
    } else {
      header = 'WEBVTT';
    }
  }

  const cues: SubtitleCue[] = [];
  const blocks = body.split(/\n{2,}/);

  for (const block of blocks) {
    const lines = block.split('\n').map(l => l.trim()).filter((l, i, arr) => !(l === '' && i === arr.length - 1));
    if (lines.length === 0) continue;

    let idx = 0;
    let cueId: string | undefined;
    let index: number | undefined;

    // 第一行可能是序号（纯数字，SRT）或 cue 标识（VTT）
    if (!isTimingLine(lines[0])) {
      if (format === 'srt' && /^\d+$/.test(lines[0])) {
        index = parseInt(lines[0], 10);
      } else {
        cueId = lines[0];
      }
      idx = 1;
    }
    if (idx >= lines.length || !isTimingLine(lines[idx])) continue;

    const timing = lines[idx];
    const [startMs, endMs] = parseTimingLine(timing);
    const text = lines.slice(idx + 1).join('\n');

    cues.push({ index, cueId, timing, startMs, endMs, text });
  }

  return { format, header, cues };
}

/**
 * 双语文本：每条 cue 两行 —— 第 1 行原文（多行折叠为空格分隔），
 * 第 2 行译文（多行折叠为空格分隔）。
 */
export function bilingualCueText(original: string, translated: string): string {
  const o = original.replace(/\s*\n\s*/g, ' ').trim();
  const t = translated.replace(/\s*\n\s*/g, ' ').trim();
  return `${o}\n${t}`;
}

/** 给 cue 列表配双语（translations 与 cues 一一对应，缺译文时保留原文） */
export function makeBilingualCues(
  cues: SubtitleCue[],
  translations: (string | undefined)[]
): SubtitleCue[] {
  return cues.map((cue, i) => {
    const t = translations[i];
    return {
      ...cue,
      text: t ? bilingualCueText(cue.text, t) : cue.text,
    };
  });
}

/** 序列化为 SRT（序号重排，时间行原样输出 → 时间轴不动） */
export function serializeSrt(cues: SubtitleCue[]): string {
  return cues
    .map((cue, i) => `${i + 1}\n${cue.timing}\n${cue.text}`)
    .join('\n\n') + '\n';
}

/** 序列化为 VTT（保留 WEBVTT 头，时间行原样输出） */
export function serializeVtt(doc: { header: string; cues: SubtitleCue[] }): string {
  const header = doc.header || 'WEBVTT';
  const body = doc.cues
    .map(cue => {
      const idLine = cue.cueId ? `${cue.cueId}\n` : '';
      return `${idLine}${cue.timing}\n${cue.text}`;
    })
    .join('\n\n');
  return `${header}\n\n${body}\n`;
}

/** 毫秒 → SRT 时间戳（构造新 cue 用） */
export function formatSrtTimestamp(ms: number): string {
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const frac = Math.floor(ms % 1000);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(frac).padStart(3, '0')}`;
}

/** 毫秒 → VTT 时间戳 */
export function formatVttTimestamp(ms: number): string {
  return formatSrtTimestamp(ms).replace(',', '.');
}

/** 构造一条新 cue（自动补 timing 行） */
export function makeCue(
  index: number,
  startMs: number,
  endMs: number,
  text: string,
  format: 'srt' | 'vtt' = 'srt'
): SubtitleCue {
  const timing = format === 'srt'
    ? `${formatSrtTimestamp(startMs)} --> ${formatSrtTimestamp(endMs)}`
    : `${formatVttTimestamp(startMs)} --> ${formatVttTimestamp(endMs)}`;
  return { index, timing, startMs, endMs, text };
}
