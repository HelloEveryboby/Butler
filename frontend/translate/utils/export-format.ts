/* ============================================================
   双语导出格式构造（TXT / Markdown）— 纯函数，便于单测
   ------------------------------------------------------------
   段落交错输出「原文 + 译文」；Markdown 保留标题层级，
   代码块不翻译（原样输出）。
   ============================================================ */

/** 一个待导出段落 */
export interface BilingualParagraph {
  original: string;
  translation: string;
}

/** Markdown 分段结果 */
export interface MdSegment {
  type: 'heading' | 'paragraph' | 'code';
  /** 标题层级（1-6），仅 heading 有效 */
  level?: number;
  /** 原文（code 时为整段代码块原文，含栅栏） */
  text: string;
}

/** TXT 双语交错：每段「原文\n译文」，段间空行 */
export function buildBilingualTxt(paras: BilingualParagraph[]): string {
  return paras
    .map(p => `${p.original}\n${p.translation}`)
    .join('\n\n') + '\n';
}

/**
 * Markdown 分段（纯文本解析，不引第三方库）：
 * - ``` / ~~~ 围栏代码块 → code（含栅栏行本身，原样保留）
 * - #{1,6} 标题 → heading（保留层级）
 * - 其余连续非空行 → paragraph
 */
export function splitMarkdownSegments(md: string): MdSegment[] {
  const lines = md.replace(/\r\n?/g, '\n').split('\n');
  const segments: MdSegment[] = [];

  let i = 0;
  let paraBuf: string[] = [];

  const flushPara = () => {
    if (paraBuf.length > 0) {
      segments.push({ type: 'paragraph', text: paraBuf.join('\n') });
      paraBuf = [];
    }
  };

  while (i < lines.length) {
    const line = lines[i];

    // 围栏代码块（``` 或 ~~~）
    const fence = line.match(/^(```+|~~~+)\s*\S*/);
    if (fence) {
      flushPara();
      const fenceMark = fence[1][0].repeat(fence[1].length);
      const codeLines = [line];
      i++;
      while (i < lines.length && !lines[i].startsWith(fenceMark)) {
        codeLines.push(lines[i]);
        i++;
      }
      if (i < lines.length) codeLines.push(lines[i]); // 收尾栅栏
      i++;
      segments.push({ type: 'code', text: codeLines.join('\n') });
      continue;
    }

    // 标题
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      flushPara();
      segments.push({ type: 'heading', level: heading[1].length, text: heading[2] });
      i++;
      continue;
    }

    // 空行分段
    if (line.trim() === '') {
      flushPara();
      i++;
      continue;
    }

    paraBuf.push(line);
    i++;
  }
  flushPara();

  return segments;
}

/**
 * 双语 Markdown：
 * - heading：`# 原文` + `# 译文`（层级保持一致）
 * - paragraph：原文 + 译文（交错）
 * - code：原样输出（代码块不翻译）
 */
export function buildBilingualMarkdown(
  segments: MdSegment[],
  translations: (string | undefined)[]
): string {
  const out: string[] = [];
  segments.forEach((seg, i) => {
    if (seg.type === 'code') {
      out.push(seg.text);
    } else if (seg.type === 'heading') {
      const prefix = '#'.repeat(seg.level || 1);
      const t = translations[i];
      out.push(t ? `${prefix} ${seg.text}\n${prefix} ${t}` : `${prefix} ${seg.text}`);
    } else {
      const t = translations[i];
      out.push(t ? `${seg.text}\n${t}` : seg.text);
    }
  });
  return out.join('\n\n') + '\n';
}

/** 双语 HTML 段落交错片段（EPUB / 网页快照共用） */
export function bilingualBlock(originalHtml: string, translation: string): string {
  return `${originalHtml}<span class="bt-translation" style="display:block;">${escapeHtml(translation)}</span>`;
}

/** 极简 HTML 转义（纯函数） */
export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** EPUB / 网页快照中译文块的统一样式（写入 stylesheet） */
export const BT_TRANSLATION_CSS = `
span.bt-translation {
  display: block;
  margin: 2px 0 8px 0;
  padding: 2px 8px;
  border-left: 3px solid #4a9eff;
  background: rgba(74, 158, 255, 0.06);
  color: #444;
}
`.trim();
