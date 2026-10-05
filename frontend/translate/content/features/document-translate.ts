/* ============================================================
   文档翻译 — 上传文件翻译，支持多种格式
   PDF / TXT / SRT / VTT / Epub / Markdown / HTML
   Word / Excel 通过 Butler 后端处理
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { injectStyles } from '../styles/styles';
import { ocrImage, translateDocumentImages } from './image-translate';
import { loadPdfJs } from '../../utils/vendor';
import {
  exportBilingualTxtFromText,
  exportBilingualMarkdownFromText,
  buildBilingualEpub,
  exportBilingualSubtitle,
  bilingualizeHtmlString,
} from './export-translate';
import { parseSubtitle } from '../../utils/subtitle-io';
import { saveSubtitleSession } from '../../utils/subtitle-history';

/** 支持的文件格式 */
const SUPPORTED_FORMATS: Record<string, { name: string; handler: string }> = {
  '.txt': { name: '纯文本', handler: 'text' },
  '.md': { name: 'Markdown', handler: 'text' },
  '.html': { name: 'HTML', handler: 'html' },
  '.htm': { name: 'HTML', handler: 'html' },
  '.srt': { name: 'SRT 字幕', handler: 'subtitle' },
  '.vtt': { name: 'VTT 字幕', handler: 'subtitle' },
  '.ass': { name: 'ASS 字幕', handler: 'subtitle' },
  '.epub': { name: 'Epub 电子书', handler: 'epub' },
  '.pdf': { name: 'PDF 文档', handler: 'pdf' },
  '.docx': { name: 'Word 文档', handler: 'butler' },
  '.xlsx': { name: 'Excel 表格', handler: 'butler' },
  '.pptx': { name: 'PPT 演示', handler: 'butler' },
};

// ---------- UI：文档翻译面板 ----------
let panelEl: HTMLDivElement | null = null;

export function showDocumentTranslator(config: TranslateConfig): void {
  injectStyles();
  removeDocumentTranslator();

  panelEl = document.createElement('div');
  panelEl.className = 'bt-doc-panel';
  panelEl.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 2147483647;
    width: 520px;
    max-height: 80vh;
    background: #fff;
    border-radius: 14px;
    box-shadow: 0 12px 60px rgba(0, 0, 0, 0.25);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  `;

  const formats = Object.entries(SUPPORTED_FORMATS).map(([ext, info]) => `${info.name} (${ext})`).join('、');

  panelEl.innerHTML = `
    <div style="padding: 20px 24px; border-bottom: 1px solid #f0f0f0; display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h2 style="margin: 0; font-size: 18px; font-weight: 700; color: #1a1a1a;">📄 文档翻译</h2>
        <p style="margin: 6px 0 0; font-size: 12px; color: #999;">上传文件，翻译后下载</p>
      </div>
      <button id="bt-doc-close" style="background: none; border: none; font-size: 22px; cursor: pointer; color: #999; padding: 4px;">✕</button>
    </div>

    <div style="padding: 24px; flex: 1; overflow-y: auto;">
      <!-- 上传区 -->
      <div id="bt-doc-dropzone" style="
        border: 2px dashed #d0d0d0;
        border-radius: 12px;
        padding: 40px 20px;
        text-align: center;
        cursor: pointer;
        transition: all 0.2s;
        background: #fafafa;
      ">
        <div style="font-size: 48px; margin-bottom: 12px;">📁</div>
        <div style="font-size: 15px; font-weight: 600; color: #333; margin-bottom: 6px;">
          点击选择文件 或 拖拽到此处
        </div>
        <div style="font-size: 12px; color: #999;">
          支持格式：${formats}
        </div>
      </div>

      <input type="file" id="bt-doc-file-input" accept="${Object.keys(SUPPORTED_FORMATS).join(',')}" style="display: none;">

      <!-- 翻译选项 -->
      <div style="margin-top: 16px; display: flex; gap: 12px; align-items: center;">
        <label style="font-size: 13px; color: #666;">目标语言</label>
        <select id="bt-doc-lang" style="padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px;">
          <option value="zh-CN" selected>中文（简体）</option>
          <option value="en">English</option>
          <option value="ja">日本語</option>
          <option value="ko">한국어</option>
        </select>

        <label style="font-size: 13px; color: #666;">翻译源</label>
        <select id="bt-doc-provider" style="padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px;">
          <option value="">默认</option>
        </select>
      </div>
      <div style="margin-top: 10px; display: flex; gap: 16px; align-items: center;">
        <label style="font-size: 13px; color: #666; display: flex; align-items: center; gap: 6px; cursor: pointer;">
          <input type="checkbox" id="bt-doc-translate-images"> 🖼️ 翻译文档内图片（OCR）
        </label>
      </div>

      <!-- 状态 -->
      <div id="bt-doc-status" style="margin-top: 16px; display: none;">
        <div style="background: #f0f8ff; border-radius: 8px; padding: 14px 16px;">
          <div id="bt-doc-filename" style="font-size: 14px; font-weight: 600; color: #333; margin-bottom: 8px;"></div>
          <div style="background: #e0e0e0; border-radius: 4px; height: 6px; overflow: hidden;">
            <div id="bt-doc-progress" style="background: #4a9eff; height: 100%; width: 0%; transition: width 0.3s; border-radius: 4px;"></div>
          </div>
          <div id="bt-doc-status-text" style="font-size: 12px; color: #666; margin-top: 6px;">准备中...</div>
        </div>
      </div>

      <!-- 结果 -->
      <div id="bt-doc-result" style="margin-top: 16px; display: none;">
        <div style="background: #d4edda; border-radius: 8px; padding: 14px 16px;">
          <div style="font-size: 14px; font-weight: 600; color: #155724; margin-bottom: 8px;">✅ 翻译完成</div>
          <button id="bt-doc-download" style="
            background: #4a9eff; color: #fff; border: none; padding: 8px 20px;
            border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600;
          ">📥 下载译文</button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(panelEl);

  // 事件绑定
  const dropzone = panelEl.querySelector('#bt-doc-dropzone') as HTMLElement;
  const fileInput = panelEl.querySelector('#bt-doc-file-input') as HTMLInputElement;
  const closeBtn = panelEl.querySelector('#bt-doc-close') as HTMLButtonElement;

  dropzone.addEventListener('click', () => fileInput.click());
  closeBtn.addEventListener('click', removeDocumentTranslator);

  // 拖拽
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = '#4a9eff';
    dropzone.style.background = '#f0f8ff';
  });
  dropzone.addEventListener('dragleave', () => {
    dropzone.style.borderColor = '#d0d0d0';
    dropzone.style.background = '#fafafa';
  });
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = '#d0d0d0';
    dropzone.style.background = '#fafafa';
    if (e.dataTransfer?.files.length) {
      handleFile(e.dataTransfer.files[0], config);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files?.length) {
      handleFile(fileInput.files[0], config);
    }
  });
}

export function removeDocumentTranslator(): void {
  panelEl?.remove();
  panelEl = null;
}

// ---------- 文件处理 ----------
async function handleFile(file: File, config: TranslateConfig): Promise<void> {
  const ext = '.' + file.name.split('.').pop()?.toLowerCase();
  const format = SUPPORTED_FORMATS[ext];

  if (!format) {
    alert(`不支持的文件格式: ${ext}`);
    return;
  }

  // 显示状态
  const statusEl = panelEl?.querySelector('#bt-doc-status') as HTMLElement;
  const filenameEl = panelEl?.querySelector('#bt-doc-filename') as HTMLElement;
  const progressEl = panelEl?.querySelector('#bt-doc-progress') as HTMLElement;
  const statusTextEl = panelEl?.querySelector('#bt-doc-status-text') as HTMLElement;
  const resultEl = panelEl?.querySelector('#bt-doc-result') as HTMLElement;

  if (statusEl) statusEl.style.display = 'block';
  if (resultEl) resultEl.style.display = 'none';
  if (filenameEl) filenameEl.textContent = `📄 ${file.name} (${format.name})`;
  if (progressEl) progressEl.style.width = '10%';
  if (statusTextEl) statusTextEl.textContent = '读取文件...';

  try {
    let translatedContent: string | Blob;
    const targetLang = (panelEl?.querySelector('#bt-doc-lang') as HTMLSelectElement)?.value || config.targetLang;

    switch (format.handler) {
      case 'text':
        translatedContent = await translateTextFile(file, targetLang, config, progressEl, statusTextEl);
        break;
      case 'subtitle':
        translatedContent = await translateSubtitleFile(file, targetLang, config, progressEl, statusTextEl);
        break;
      case 'html':
        translatedContent = await translateHtmlFile(file, targetLang, config, progressEl, statusTextEl);
        break;
      case 'epub':
        translatedContent = await translateEpubFile(file, targetLang, config, progressEl, statusTextEl);
        break;
      case 'pdf':
        translatedContent = await translatePdfFile(file, targetLang, config, progressEl, statusTextEl);
        break;
      case 'butler':
        alert(`${format.name} 需要 Butler 后端处理，请确保 Butler 正在运行。`);
        return;
      default:
        alert('不支持的格式');
        return;
    }

    // 显示下载
    if (progressEl) progressEl.style.width = '100%';
    if (statusTextEl) statusTextEl.textContent = '翻译完成！';
    if (resultEl) resultEl.style.display = 'block';

    const downloadBtn = panelEl?.querySelector('#bt-doc-download') as HTMLButtonElement;
    downloadBtn?.addEventListener('click', () => {
      const outputName = file.name.replace(ext, `_双语${ext}`);
      downloadFile(translatedContent, outputName);
    });

  } catch (err) {
    if (statusTextEl) statusTextEl.textContent = `翻译失败: ${err}`;
    if (progressEl) progressEl.style.background = '#e74c3c';
  }
}

// ---------- 纯文本翻译（双语交错：原文 + 译文，段落交错） ----------
async function translateTextFile(
  file: File, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<string> {
  const text = await file.text();
  const cfg = { ...config, targetLang };
  const ext = file.name.split('.').pop()?.toLowerCase();
  if (statusEl) statusEl.textContent = '生成双语文本...';
  // 段落交错：原文 + 译文（代码块不翻译）
  return ext === 'md'
    ? exportBilingualMarkdownFromText(text, cfg)
    : exportBilingualTxtFromText(text, cfg);
}

// ---------- 字幕翻译（SRT/VTT/ASS）：双语输出，时间轴不动 ----------
async function translateSubtitleFile(
  file: File, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<string> {
  const text = await file.text();
  const ext = file.name.split('.').pop()?.toLowerCase();

  if (ext === 'ass') return translateAss(text, targetLang, config, progressEl, statusEl);

  // SRT / VTT：每条 cue 两行（原文 + 译文），时间行原样保留，VTT 保留 WEBVTT 头
  const isVtt = ext === 'vtt' || /^WEBVTT/.test(text.trim());
  const doc = parseSubtitle(text, isVtt ? 'vtt' : 'srt');
  if (doc.cues.length === 0) {
    throw new Error('未解析出任何字幕条目（请检查 SRT/VTT 格式）');
  }
  const result = await exportBilingualSubtitle(doc, isVtt ? 'vtt' : 'srt', { ...config, targetLang }, (s) => {
    if (statusEl) statusEl.textContent = s;
    if (progressEl) progressEl.style.width = '60%';
  });

  // 记入字幕翻译历史（支持后续双语 SRT/VTT 导出，2.5）
  await saveSubtitleSession({
    id: `file-${Date.now()}`,
    ts: Date.now(),
    title: file.name.replace(/\.(srt|vtt|ass)$/i, ''),
    targetLang,
    preciseTiming: true,
    pairs: result.pairs,
  });

  return result.content;
}

async function translateAss(
  ass: string, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<string> {
  // ASS 格式：Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,文本
  // 双语输出：文本字段写「原文\N译文」（ASS 换行符 \N），时间轴不动
  const lines = ass.split('\n');
  const dialogueLines: { index: number; text: string }[] = [];

  lines.forEach((line, idx) => {
    if (line.startsWith('Dialogue:')) {
      const parts = line.split(',');
      if (parts.length >= 10) {
        const text = parts.slice(9).join(',').replace(/\{[^}]*\}/g, ''); // 去掉样式标签
        if (text.trim()) dialogueLines.push({ index: idx, text });
      }
    }
  });

  // 批量翻译
  const translated = new Map<number, string>();
  const BATCH = 30;

  for (let i = 0; i < dialogueLines.length; i += BATCH) {
    const batch = dialogueLines.slice(i, i + BATCH);
    if (progressEl) progressEl.style.width = `${Math.min(90, 10 + (i / dialogueLines.length) * 80)}%`;
    if (statusEl) statusEl.textContent = `翻译 ASS 字幕... ${i}/${dialogueLines.length}`;

    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts: batch.map(b => b.text),
      to: targetLang,
    });

    if (resp.type === 'TRANSLATE_RESULT') {
      batch.forEach((b, j) => translated.set(b.index, resp.results[j]?.translated || b.text));
    }
  }

  // 重组 ASS（双语：原文\N译文，时间轴不动）
  return lines.map((line, idx) => {
    if (translated.has(idx)) {
      const parts = line.split(',');
      const original = parts.slice(9).join(',');
      parts.length = 9;
      parts.push(`${original.trim()}\N${translated.get(idx)!}`);
      return parts.join(',');
    }
    return line;
  }).join('\n');
}

// ---------- HTML 翻译（双语交错：原文段落 + 译文块） ----------
async function translateHtmlFile(
  file: File, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<string> {
  const html = await file.text();
  return bilingualizeHtmlString(html, { ...config, targetLang }, false, (done, total) => {
    if (progressEl) progressEl.style.width = `${Math.min(90, 10 + (done / Math.max(total, 1)) * 80)}%`;
    if (statusEl) statusEl.textContent = `翻译 HTML... ${done}/${total} 段`;
  });
}

// ---------- Epub 翻译（双语交错，保留原 EPUB 结构） ----------
async function translateEpubFile(
  file: File, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<Blob> {
  // 产品定位：双语对照导出（不是覆盖原文），结构保持不变
  return buildBilingualEpub(file, { ...config, targetLang }, (msg, pct) => {
    if (progressEl) progressEl.style.width = `${pct}%`;
    if (statusEl) statusEl.textContent = msg;
  });
}

// ---------- PDF 文件翻译 ----------
async function translatePdfFile(
  file: File, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<string> {
  // 加载 pdf.js（本地 vendor chunk，worker 指向本地）
  const pdfjsLib = await loadPdfJs();

  const translateImages = (panelEl?.querySelector('#bt-doc-translate-images') as HTMLInputElement)?.checked ?? false;

  const arrayBuffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
  const translatedPages: string[] = [];

  for (let i = 1; i <= pdf.numPages; i++) {
    if (progressEl) progressEl.style.width = `${Math.min(90, 10 + (i / pdf.numPages) * 80)}%`;
    if (statusEl) statusEl.textContent = `翻译 PDF 第 ${i}/${pdf.numPages} 页`;

    const page = await pdf.getPage(i);
    const textContent = await page.getTextContent();
    const texts = textContent.items
      .filter((item: any) => item.str?.trim().length >= 2)
      .map((item: any) => item.str);

    let pageResult = '';

    // 翻译文字
    if (texts.length > 0) {
      const resp = await sendMessage({ type: 'TRANSLATE', texts, to: targetLang });
      if (resp.type === 'TRANSLATE_RESULT') {
        pageResult = resp.results.map(r => r.translated).join('\n');
      } else {
        pageResult = texts.join('\n');
      }
    }

    // OCR 翻译图片
    if (translateImages) {
      const viewport = page.getViewport({ scale: 2.0 });
      const canvas = document.createElement('canvas');
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      const ctx = canvas.getContext('2d')!;

      await page.render({ canvasContext: ctx, viewport }).promise;

      try {
        const ocrResult = await ocrImage(canvas);
        if (ocrResult.text.length >= 3) {
          if (statusEl) statusEl.textContent = `翻译 PDF 第 ${i} 页图片...`;
          const imgResp = await sendMessage({ type: 'TRANSLATE', texts: [ocrResult.text], to: targetLang });
          if (imgResp.type === 'TRANSLATE_RESULT') {
            const imgTranslated = imgResp.results[0]?.translated;
            if (imgTranslated) {
              pageResult += '\n\n[图片文字]\n' + imgTranslated;
            }
          }
        }
      } catch (err) {
        console.warn(`[ButlerTranslate] PDF page ${i} image OCR failed:`, err);
      }

      // 清理 canvas
      canvas.remove();
    }

    translatedPages.push(pageResult);
  }

  return translatedPages.join('\n\n--- 第 {} 页 ---\n\n'.replace('{}', ''));
}

// ---------- 工具 ----------
function downloadFile(content: string | Blob, filename: string): void {
  const blob = content instanceof Blob ? content : new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = () => resolve();
    script.onerror = reject;
    (document.head || document.documentElement).appendChild(script);
  });
}

// 类型声明
declare global {
  interface Window {
    pdfjsLib: any;
    JSZip: any;
  }
}
