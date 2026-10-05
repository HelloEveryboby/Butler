/* ============================================================
   双语导出 — 产品护城河功能
   ------------------------------------------------------------
   支持 5 类双语导出（原文 + 译文交错，译文包 <span class="bt-translation">）：
   1. 双语 EPUB：JSZip 解包，逐段交错，保留原 EPUB 结构
      （container.xml / OPF / spine / 目录 / 封面），CSS 类写入 stylesheet
   2. 双语 PDF：background 转发给 Butler 后端 CLI（EXPORT_PDF），
      后端不存在/不支持时明确提示，不假装成功
   3. 双语 SRT / VTT：每条 cue 两行，时间轴不动，VTT 保留 WEBVTT 头
   4. 双语 TXT / Markdown：段落交错，Markdown 保留标题层级，代码块不翻译
   5. 网页快照：当前页面 DOM 双语序列化为自带内联 CSS 的 HTML
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { injectStyles } from '../styles/styles';
import {
  parseSubtitle, makeBilingualCues, serializeSrt, serializeVtt,
  bilingualCueText, SubtitleDoc,
} from '../../utils/subtitle-io';
import {
  buildBilingualTxt, splitMarkdownSegments, buildBilingualMarkdown,
  BT_TRANSLATION_CSS, BilingualParagraph,
} from '../../utils/export-format';
import { getLatestSubtitleSession, sessionToBilingualCues, SubtitlePair, saveSubtitleSession } from '../../utils/subtitle-history';
import { loadJsZip } from '../../utils/vendor';

/* ============================================================
   基础工具
   ============================================================ */

/** 下载 Blob（<a download> + Blob，离线可用） */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/** 下载文本 */
export function downloadText(text: string, filename: string, mime = 'text/plain;charset=utf-8'): void {
  downloadBlob(new Blob([text], { type: mime }), filename);
}

/** 分批翻译（带进度回调） */
export async function translateTextsBatched(
  texts: string[],
  to: string,
  onProgress?: (done: number, total: number) => void
): Promise<string[]> {
  const BATCH = 20;
  const out: string[] = [];
  for (let i = 0; i < texts.length; i += BATCH) {
    const batch = texts.slice(i, i + BATCH);
    onProgress?.(i, texts.length);
    const resp = await sendMessage({ type: 'TRANSLATE', texts: batch, to });
    if (resp.type === 'TRANSLATE_RESULT') {
      out.push(...resp.results.map(r => r.translated));
    } else {
      out.push(...batch); // 失败保留原文（绝不静默丢内容）
    }
  }
  onProgress?.(texts.length, texts.length);
  return out;
}

/* ============================================================
   页面内容收集（TXT / Markdown / 网页快照共用）
   ============================================================ */

export interface PageBlock {
  type: 'heading' | 'paragraph' | 'code';
  level?: number;
  text: string;
}

/** 收集页面段落（标题带层级，代码块单独标出不翻译） */
export function collectPageBlocks(root: Element = document.body): PageBlock[] {
  const blocks: PageBlock[] = [];
  const seen = new Set<Element>();

  const candidates = root.querySelectorAll('h1, h2, h3, h4, h5, h6, p, li, blockquote, figcaption, pre');
  for (const el of Array.from(candidates)) {
    if (seen.has(el)) continue;
    // 跳过嵌套（li 里的 p 等）
    let nested = false;
    for (const s of seen) {
      if (s.contains(el)) { nested = true; break; }
    }
    if (nested) continue;
    seen.add(el);

    if (el.closest('pre') && el.tagName !== 'PRE') continue;

    const text = (el.textContent || '').trim();
    if (text.length < 2) continue;

    if (el.tagName === 'PRE' || el.closest('code')) {
      blocks.push({ type: 'code', text });
      continue;
    }
    const headingMatch = el.tagName.match(/^H([1-6])$/);
    if (headingMatch) {
      blocks.push({ type: 'heading', level: parseInt(headingMatch[1], 10), text });
      continue;
    }
    blocks.push({ type: 'paragraph', text });
  }
  return blocks;
}

/** 页面 URL / 标题（导出文件命名） */
function pageTitle(): string {
  return document.title || 'page';
}

/* ============================================================
   1. 双语 TXT / Markdown（页面 或 文档）
   ============================================================ */

export async function exportBilingualTxtFromPage(config: TranslateConfig, setStatus?: (s: string) => void): Promise<void> {
  const blocks = collectPageBlocks().filter(b => b.type !== 'code'); // TXT 也不翻译代码块
  if (blocks.length === 0) throw new Error('当前页面没有可导出的文本段落');
  setStatus?.(`翻译中... 0/${blocks.length}`);
  const translations = await translateTextsBatched(blocks.map(b => b.text), config.targetLang, (d, t) =>
    setStatus?.(`翻译中... ${d}/${t}`)
  );
  const paras: BilingualParagraph[] = blocks.map((b, i) => ({
    original: b.text,
    translation: translations[i],
  }));
  downloadText(buildBilingualTxt(paras), `${pageTitle()}_双语.txt`);
}

export async function exportBilingualMarkdownFromPage(config: TranslateConfig, setStatus?: (s: string) => void): Promise<void> {
  const blocks = collectPageBlocks();
  if (blocks.length === 0) throw new Error('当前页面没有可导出的文本段落');
  const toTranslate = blocks.filter(b => b.type !== 'code');
  setStatus?.(`翻译中... 0/${toTranslate.length}`);
  const translations = await translateTextsBatched(toTranslate.map(b => b.text), config.targetLang, (d, t) =>
    setStatus?.(`翻译中... ${d}/${t}`)
  );
  // 回填（代码块译文为 undefined → 原样输出）
  let ti = 0;
  const all: (string | undefined)[] = blocks.map(b => (b.type === 'code' ? undefined : translations[ti++]));
  const md = buildBilingualMarkdown(
    blocks.map(b => ({ type: b.type, level: b.level, text: b.text })),
    all
  );
  downloadText(md, `${pageTitle()}_双语.md`, 'text/markdown;charset=utf-8');
}

/** 文档（TXT）→ 双语 TXT：按空行分段交错 */
export async function exportBilingualTxtFromText(text: string, config: TranslateConfig): Promise<string> {
  const parasText = text.replace(/\r\n?/g, '\n').split(/\n{2,}/).map(p => p.trim()).filter(Boolean);
  const translations = await translateTextsBatched(parasText, config.targetLang);
  return buildBilingualTxt(parasText.map((p, i) => ({ original: p, translation: translations[i] })));
}

/** 文档（Markdown）→ 双语 Markdown：保留标题层级，代码块不翻译 */
export async function exportBilingualMarkdownFromText(text: string, config: TranslateConfig): Promise<string> {
  const segments = splitMarkdownSegments(text);
  const toTranslate = segments.filter(s => s.type !== 'code');
  const translations = await translateTextsBatched(toTranslate.map(s => s.text), config.targetLang);
  let ti = 0;
  const all = segments.map(s => (s.type === 'code' ? undefined : translations[ti++]));
  return buildBilingualMarkdown(segments, all);
}

/* ============================================================
   2. 双语 SRT / VTT（时间轴不动）
   ============================================================ */

/** 字幕文档 → 双语文本（format: srt | vtt），时间行原样保留；同时产出历史记录用的 pairs */
export interface SubtitleExportResult {
  content: string;
  pairs: SubtitlePair[];
}

export async function exportBilingualSubtitle(
  doc: SubtitleDoc,
  format: 'srt' | 'vtt',
  config: TranslateConfig,
  setStatus?: (s: string) => void
): Promise<SubtitleExportResult> {
  const texts = doc.cues.map(c => c.text.replace(/\n/g, ' ').trim()).filter(Boolean);
  setStatus?.(`翻译字幕... 0/${texts.length}`);
  const translations = await translateTextsBatched(texts, config.targetLang, (d, t) =>
    setStatus?.(`翻译字幕... ${d}/${t}`)
  );

  // 对齐：cues 与 translations 一一对应
  let ti = 0;
  const perCue = doc.cues.map(c => {
    const t = c.text.trim();
    return t ? translations[ti++] : undefined;
  });

  const bilingual = makeBilingualCues(doc.cues, perCue);
  const content = format === 'srt' ? serializeSrt(bilingual) : serializeVtt({ header: doc.header, cues: bilingual });

  const pairs: SubtitlePair[] = doc.cues.map((c, i) => ({
    startMs: c.startMs,
    endMs: c.endMs,
    original: c.text,
    translated: perCue[i] || c.text,
  }));

  return { content, pairs };
}

/** 上传的字幕文件 → 双语文件下载 */
export async function exportBilingualSubtitleFile(
  file: File,
  config: TranslateConfig,
  setStatus?: (s: string) => void
): Promise<void> {
  const text = await file.text();
  const isVtt = file.name.toLowerCase().endsWith('.vtt') || /^WEBVTT/.test(text.trim());
  const doc = parseSubtitle(text, isVtt ? 'vtt' : 'srt');
  if (doc.cues.length === 0) throw new Error('未解析出任何字幕条目（请检查 SRT/VTT 格式）');
  const result = await exportBilingualSubtitle(doc, isVtt ? 'vtt' : 'srt', config, setStatus);
  downloadText(
    result.content,
    file.name.replace(/\.(srt|vtt)$/i, '') + '_双语.' + (isVtt ? 'vtt' : 'srt'),
    isVtt ? 'text/vtt;charset=utf-8' : 'application/x-subrip;charset=utf-8'
  );
  // 记入字幕翻译历史（后续可再导出）
  await saveSubtitleSession({
    id: `file-${Date.now()}`,
    ts: Date.now(),
    title: file.name.replace(/\.(srt|vtt)$/i, ''),
    targetLang: config.targetLang,
    preciseTiming: true,
    pairs: result.pairs,
  });
}

/** 字幕翻译历史 → 双语 SRT/VTT 导出（2.5） */
export async function exportSubtitleHistoryBilingual(format: 'srt' | 'vtt'): Promise<void> {
  const session = await getLatestSubtitleSession();
  if (!session || session.pairs.length === 0) {
    throw new Error('暂无字幕翻译历史：请先开启字幕翻译，或使用文档翻译处理 SRT/VTT 文件');
  }
  const cues = sessionToBilingualCues(session);
  const content = format === 'srt'
    ? serializeSrt(cues)
    : serializeVtt({ header: 'WEBVTT', cues });
  downloadText(
    content,
    `${session.title || 'subtitles'}_双语.${format}`,
    format === 'vtt' ? 'text/vtt;charset=utf-8' : 'application/x-subrip;charset=utf-8'
  );
}

/* ============================================================
   3. 双语 EPUB（保留原结构）
   ============================================================ */

/** 解析 EPUB/HTML 页面（xhtml 走 XML 解析保留结构，失败回退 HTML 解析） */
function parseHtmlDoc(html: string, isXhtml: boolean): { doc: Document; useXml: boolean } {
  if (isXhtml) {
    try {
      const xmlDoc = new DOMParser().parseFromString(html, 'application/xhtml+xml');
      if (!xmlDoc.querySelector('parsererror')) return { doc: xmlDoc, useXml: true };
    } catch {
      /* 回退 */
    }
  }
  return { doc: new DOMParser().parseFromString(html, 'text/html'), useXml: false };
}

/** 把一段 HTML 双语化：块级段落交错输出原文 + 译文 */
export async function bilingualizeHtmlString(
  html: string,
  config: TranslateConfig,
  isXhtml: boolean,
  onProgress?: (done: number, total: number) => void
): Promise<string> {
  const { doc, useXml } = parseHtmlDoc(html, isXhtml);

  const root = doc.body || doc.documentElement;
  // 段落元素：块级、不含嵌套块、非代码
  const blocks = Array.from(
    root.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, blockquote, dt, dd, figcaption, caption, td, th')
  ).filter(el => {
    if (el.querySelector('p, div, li, blockquote')) return false;
    if (el.closest('pre, code, script, style, nav')) return false;
    const t = (el.textContent || '').trim();
    return t.length >= 2;
  });

  const texts = blocks.map(el => (el.textContent || '').trim());
  const translations = await translateTextsBatched(texts, config.targetLang, onProgress);

  blocks.forEach((el, i) => {
    const span = doc.createElement('span');
    span.setAttribute('class', 'bt-translation');
    span.textContent = translations[i] || '';
    el.appendChild(span);
  });

  // CSS 类样式写入 stylesheet（EPUB 内的 <style>，随文件走）
  const head = doc.head || doc.querySelector('head');
  if (head) {
    const styleEl = doc.createElement('style');
    styleEl.setAttribute('data-bt-style', '1');
    styleEl.textContent = BT_TRANSLATION_CSS;
    head.appendChild(styleEl);
  }

  return useXml
    ? new XMLSerializer().serializeToString(doc)
    : '<!DOCTYPE html>\n' + doc.documentElement.outerHTML;
}

/**
 * 双语 EPUB：JSZip 解包 → 每个 html/xhtml 段落交错 → 重新打包。
 * 非 HTML 资源（container.xml / OPF / spine / 目录 / 封面 / 字体 / 图片）
 * 原样复制，路径不变，保留原 EPUB 结构。
 * 译文块样式同时追加到包内已有 *.css（stylesheet），并在每个 html 头注入 <style> 兜底。
 */
export async function buildBilingualEpub(
  file: File,
  config: TranslateConfig,
  onProgress?: (msg: string, percent: number) => void
): Promise<Blob> {
  const JSZip = await loadJsZip();
  const zip = await JSZip.loadAsync(file);
  const outZip = new JSZip();

  const htmlFiles: string[] = [];
  const cssFiles: string[] = [];
  const otherFiles: string[] = [];
  zip.forEach((path: string) => {
    if (path.endsWith('.html') || path.endsWith('.xhtml') || path.endsWith('.htm')) htmlFiles.push(path);
    else if (path.endsWith('.css')) cssFiles.push(path);
    else otherFiles.push(path);
  });

  if (htmlFiles.length === 0) {
    throw new Error('EPUB 内未找到 html/xhtml 页面文件，无法生成双语版');
  }

  let processed = 0;
  for (const path of htmlFiles) {
    onProgress?.(`翻译 EPUB 页面 ${processed + 1}/${htmlFiles.length}`, Math.round((processed / htmlFiles.length) * 90));
    const content = await zip.file(path)?.async('string');
    if (content) {
      const isXhtml = path.endsWith('.xhtml') || /xmlns\s*=\s*["']http:\/\/www\.w3\.org\/1999\/xhtml/.test(content.slice(0, 500));
      const bilingual = await bilingualizeHtmlString(content, config, isXhtml);
      outZip.file(path, bilingual);
    }
    processed++;
  }

  // stylesheet：把译文块样式追加到包内已有 CSS
  for (const path of cssFiles) {
    const css = await zip.file(path)?.async('string');
    outZip.file(path, (css || '') + '\n' + BT_TRANSLATION_CSS + '\n');
  }

  // 其余文件（container.xml / OPF / nav / 封面 / 字体…）原样复制
  for (const path of otherFiles) {
    const entry = zip.file(path);
    if (entry) outZip.file(path, await entry.async('uint8array'));
  }
  // 目录条目（空文件夹）保留
  zip.forEach((relPath: string, entry: any) => {
    if (entry.dir && !outZip.folder(relPath)) outZip.folder(relPath);
  });

  onProgress?.('打包中...', 95);
  return outZip.generateAsync({ type: 'blob' });
}

/* ============================================================
   4. 双语 PDF（走 Butler 后端 CLI，不支持时明确报错）
   ============================================================ */

export async function exportBilingualPdf(file: File, config: TranslateConfig): Promise<void> {
  const base64 = await fileToBase64(file);
  const resp = await sendMessage({
    type: 'EXPORT_PDF',
    pdfBase64: base64,
    filename: file.name,
    to: config.targetLang,
  });

  if (resp.type === 'EXPORT_RESULT' && resp.success && resp.dataUrl) {
    // dataUrl → Blob 下载
    const blob = dataUrlToBlob(resp.dataUrl);
    downloadBlob(blob, resp.filename || file.name.replace(/\.pdf$/i, '_双语.pdf'));
    return;
  }
  const message = resp.type === 'EXPORT_RESULT' ? resp.message : '未知错误';
  // 绝不假装成功：明确告知用户怎么办
  throw new Error(message || 'PDF 导出失败：请启动 Butler 后端或使用文档翻译导出 TXT/EPUB');
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || '');
      resolve(result.includes(',') ? result.split(',')[1] : result);
    };
    reader.onerror = () => reject(new Error('读取 PDF 文件失败'));
    reader.readAsDataURL(file);
  });
}

function dataUrlToBlob(dataUrl: string): Blob {
  const [header, data] = dataUrl.split(',');
  const mime = /data:([^;]+)/.exec(header)?.[1] || 'application/octet-stream';
  const bin = atob(data);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

/* ============================================================
   5. 网页快照（当前页面 DOM 双语序列化，自带内联 CSS）
   ============================================================ */

export async function exportWebpageSnapshot(config: TranslateConfig, setStatus?: (s: string) => void): Promise<void> {
  // 克隆 DOM（不改动真实页面）
  const clone = document.documentElement.cloneNode(true) as HTMLElement;

  // 去掉脚本与外部样式引用
  clone.querySelectorAll('script, noscript, iframe, link[rel="stylesheet"], style').forEach(el => el.remove());
  // 去掉扩展自己的 UI / 已有译文（重新翻译保证一致性）
  clone.querySelectorAll('.bt-translated, .bt-floating-ball, .bt-bubble, .bt-subtitle-overlay, .bt-trans-loading, .bt-doc-panel').forEach(el => el.remove());

  // 收集可访问的页面 CSS（跨域样式表无法读取，见报告"已知限制"）
  let css = BT_TRANSLATION_CSS + '\n';
  try {
    for (const sheet of Array.from(document.styleSheets)) {
      try {
        const rules = (sheet as CSSStyleSheet).cssRules;
        for (const rule of Array.from(rules)) css += rule.cssText + '\n';
      } catch {
        // 跨域样式表：跳过（不能静默假装成功，写入快照注释）
        css += `/* 跳过无法读取的跨域样式表: ${sheet.href || '(inline)'} */\n`;
      }
    }
  } catch {
    /* 忽略 */
  }

  // 翻译克隆 DOM 的段落并交错注入译文
  const blocks = Array.from(
    clone.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, blockquote, figcaption')
  ).filter(el => {
    if (el.querySelector('p, div, li')) return false;
    if (el.closest('pre, code')) return false;
    return (el.textContent || '').trim().length >= 2;
  });

  const texts = blocks.map(el => (el.textContent || '').trim());
  setStatus?.(`翻译中... 0/${texts.length}`);
  const translations = await translateTextsBatched(texts, config.targetLang, (d, t) =>
    setStatus?.(`翻译中... ${d}/${t}`)
  );

  blocks.forEach((el, i) => {
    const span = clone.ownerDocument.createElement('span');
    span.setAttribute('class', 'bt-translation');
    // 内联样式：快照脱离原站也能看
    span.setAttribute('style', 'display:block;margin:2px 0 8px 0;padding:2px 8px;border-left:3px solid #4a9eff;background:rgba(74,158,255,0.06);color:#444;');
    span.textContent = translations[i] || '';
    el.appendChild(span);
  });

  const head = clone.querySelector('head') || clone;
  const styleEl = clone.ownerDocument.createElement('style');
  styleEl.textContent = css;
  head.insertBefore(styleEl, head.firstChild);

  const html = '<!DOCTYPE html>\n' + clone.outerHTML;
  downloadText(html, `${pageTitle()}_双语快照.html`, 'text/html;charset=utf-8');
}

/* ============================================================
   导出面板 UI
   ============================================================ */

let panelEl: HTMLDivElement | null = null;

export function removeExportPanel(): void {
  panelEl?.remove();
  panelEl = null;
}

export function showExportPanel(config: TranslateConfig): void {
  injectStyles();
  removeExportPanel();

  panelEl = document.createElement('div');
  panelEl.className = 'bt-doc-panel';
  panelEl.style.cssText = `
    position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
    z-index: 2147483647; width: 520px; max-height: 82vh; background: #fff;
    border-radius: 14px; box-shadow: 0 12px 60px rgba(0,0,0,0.25);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    overflow: hidden; display: flex; flex-direction: column;
  `;

  panelEl.innerHTML = `
    <div style="padding: 18px 24px; border-bottom: 1px solid #f0f0f0; display:flex; justify-content:space-between; align-items:center;">
      <div>
        <h2 style="margin:0; font-size:18px; font-weight:700; color:#1a1a1a;">📤 双语导出</h2>
        <p style="margin:6px 0 0; font-size:12px; color:#999;">原文 + 译文交错，可离线阅读</p>
      </div>
      <button id="bt-export-close" style="background:none;border:none;font-size:22px;cursor:pointer;color:#999;padding:4px;">✕</button>
    </div>

    <div style="padding: 20px 24px; flex:1; overflow-y:auto;">
      <!-- 当前网页 -->
      <div style="font-size:13px; font-weight:600; color:#555; margin-bottom:10px;">🌐 当前网页</div>
      <div style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px;">
        <button class="bt-export-btn" data-act="snapshot">🖼 网页快照 HTML</button>
        <button class="bt-export-btn" data-act="txt">📄 双语 TXT</button>
        <button class="bt-export-btn" data-act="md">📝 双语 Markdown</button>
      </div>

      <!-- 字幕历史 -->
      <div style="font-size:13px; font-weight:600; color:#555; margin-bottom:10px;">🎬 字幕双语导出（来自字幕翻译历史）</div>
      <div style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px;">
        <button class="bt-export-btn" data-act="hist-srt">双语 SRT</button>
        <button class="bt-export-btn" data-act="hist-vtt">双语 VTT</button>
      </div>

      <!-- 文档文件 -->
      <div style="font-size:13px; font-weight:600; color:#555; margin-bottom:10px;">📁 文档文件（EPUB / PDF / SRT / VTT / TXT / MD）</div>
      <div id="bt-export-drop" style="border:2px dashed #d0d0d0; border-radius:12px; padding:28px 20px; text-align:center; cursor:pointer; background:#fafafa;">
        <div style="font-size:36px; margin-bottom:8px;">📥</div>
        <div style="font-size:14px; font-weight:600; color:#333;">选择文件生成双语版</div>
        <div style="font-size:12px; color:#999; margin-top:4px;">
          EPUB 保留原结构 · SRT/VTT 时间轴不变 · PDF 需要 Butler 后端
        </div>
      </div>
      <input type="file" id="bt-export-file" accept=".epub,.pdf,.srt,.vtt,.txt,.md,.markdown" style="display:none;">

      <!-- 状态 -->
      <div id="bt-export-status" style="margin-top:14px; display:none;">
        <div style="background:#f0f8ff; border-radius:8px; padding:12px 14px;">
          <div id="bt-export-status-text" style="font-size:13px; color:#333;">准备中...</div>
          <div style="background:#e0e0e0; border-radius:4px; height:6px; margin-top:8px; overflow:hidden;">
            <div id="bt-export-progress" style="background:#4a9eff; height:100%; width:0%; transition:width .3s;"></div>
          </div>
        </div>
      </div>
      <div id="bt-export-error" style="margin-top:12px; display:none; background:#fdecea; border-radius:8px; padding:12px 14px; color:#b3261e; font-size:13px;"></div>
    </div>
    <style>
      .bt-export-btn {
        padding: 8px 14px; border: 1px solid #4a9eff; background:#fff; color:#4a9eff;
        border-radius: 8px; font-size: 13px; cursor: pointer;
      }
      .bt-export-btn:hover { background: #f0f8ff; }
      .bt-export-btn:disabled { opacity: .5; cursor: not-allowed; }
    </style>
  `;

  document.body.appendChild(panelEl);

  const setStatus = (text: string, percent?: number) => {
    const s = panelEl?.querySelector('#bt-export-status') as HTMLElement;
    const t = panelEl?.querySelector('#bt-export-status-text') as HTMLElement;
    const p = panelEl?.querySelector('#bt-export-progress') as HTMLElement;
    if (s) s.style.display = 'block';
    if (t) t.textContent = text;
    if (p && percent !== undefined) p.style.width = `${percent}%`;
  };
  const setError = (text: string) => {
    const e = panelEl?.querySelector('#bt-export-error') as HTMLElement;
    if (e) {
      e.style.display = 'block';
      e.textContent = text;
    }
  };
  const clearError = () => {
    const e = panelEl?.querySelector('#bt-export-error') as HTMLElement;
    if (e) e.style.display = 'none';
  };

  panelEl.querySelector('#bt-export-close')!.addEventListener('click', removeExportPanel);

  // 网页导出按钮
  panelEl.querySelectorAll('.bt-export-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      clearError();
      const act = (btn as HTMLElement).dataset.act;
      try {
        if (act === 'snapshot') {
          await exportWebpageSnapshot(config, (s) => setStatus(s));
          setStatus('✅ 网页快照已下载', 100);
        } else if (act === 'txt') {
          await exportBilingualTxtFromPage(config, (s) => setStatus(s));
          setStatus('✅ 双语 TXT 已下载', 100);
        } else if (act === 'md') {
          await exportBilingualMarkdownFromPage(config, (s) => setStatus(s));
          setStatus('✅ 双语 Markdown 已下载', 100);
        } else if (act === 'hist-srt') {
          await exportSubtitleHistoryBilingual('srt');
          setStatus('✅ 双语 SRT 已下载', 100);
        } else if (act === 'hist-vtt') {
          await exportSubtitleHistoryBilingual('vtt');
          setStatus('✅ 双语 VTT 已下载', 100);
        }
      } catch (err) {
        setStatus('导出失败');
        setError(String(err));
      }
    });
  });

  // 文件导出
  const drop = panelEl.querySelector('#bt-export-drop') as HTMLElement;
  const fileInput = panelEl.querySelector('#bt-export-file') as HTMLInputElement;
  drop.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    if (fileInput.files?.length) void handleExportFile(fileInput.files[0], config, setStatus, setError);
    fileInput.value = '';
  });

  async function handleExportFile(
    file: File,
    cfg: TranslateConfig,
    setStatus: (text: string, percent?: number) => void,
    setError: (text: string) => void
  ) {
    clearError();
    const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();
    try {
      if (ext === '.epub') {
        const blob = await buildBilingualEpub(file, cfg, (msg, pct) => setStatus(msg, pct));
        setStatus('✅ 双语 EPUB 已生成，开始下载', 100);
        downloadBlob(blob, file.name.replace(/\.epub$/i, '_双语.epub'));
      } else if (ext === '.pdf') {
        setStatus('正在请求 Butler 后端生成双语 PDF...');
        await exportBilingualPdf(file, cfg);
        setStatus('✅ 双语 PDF 已下载', 100);
      } else if (ext === '.srt' || ext === '.vtt') {
        await exportBilingualSubtitleFile(file, cfg, (s) => setStatus(s));
        setStatus('✅ 双语字幕已下载', 100);
      } else if (ext === '.txt' || ext === '.md' || ext === '.markdown') {
        const text = await file.text();
        const out = ext === '.txt'
          ? await exportBilingualTxtFromText(text, cfg)
          : await exportBilingualMarkdownFromText(text, cfg);
        downloadText(
          out,
          file.name.replace(/\.(txt|md|markdown)$/i, '') + '_双语' + (ext === '.txt' ? '.txt' : '.md'),
          ext === '.txt' ? 'text/plain;charset=utf-8' : 'text/markdown;charset=utf-8'
        );
        setStatus('✅ 双语文件已下载', 100);
      } else {
        setError(`不支持的格式: ${ext}（支持 EPUB / PDF / SRT / VTT / TXT / MD）`);
        setStatus('已取消');
      }
    } catch (err) {
      setStatus('导出失败');
      setError(String(err));
    }
  }
}
