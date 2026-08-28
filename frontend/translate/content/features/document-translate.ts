/* ============================================================
   文档翻译 — 上传文件翻译，支持多种格式
   PDF / TXT / SRT / VTT / Epub / Markdown / HTML
   Word / Excel 通过 Butler 后端处理
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { injectStyles } from '../styles/styles';
import { ocrImage, translateDocumentImages } from './image-translate';

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
      const outputName = file.name.replace(ext, `_translated${ext}`);
      downloadFile(translatedContent, outputName);
    });

  } catch (err) {
    if (statusTextEl) statusTextEl.textContent = `翻译失败: ${err}`;
    if (progressEl) progressEl.style.background = '#e74c3c';
  }
}

// ---------- 纯文本翻译 ----------
async function translateTextFile(
  file: File, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<string> {
  const text = await file.text();
  const lines = text.split('\n');

  // 按段落分组（每 20 行一批）
  const BATCH = 20;
  const translatedLines: string[] = [];

  for (let i = 0; i < lines.length; i += BATCH) {
    const batch = lines.slice(i, i + BATCH);
    const progress = Math.min(90, 10 + (i / lines.length) * 80);
    if (progressEl) progressEl.style.width = `${progress}%`;
    if (statusEl) statusEl.textContent = `翻译中... ${i}/${lines.length} 行`;

    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts: batch,
      to: targetLang,
    });

    if (resp.type === 'TRANSLATE_RESULT') {
      translatedLines.push(...resp.results.map(r => r.translated));
    } else {
      translatedLines.push(...batch); // 失败保留原文
    }
  }

  return translatedLines.join('\n');
}

// ---------- 字幕翻译（SRT/VTT/ASS）----------
async function translateSubtitleFile(
  file: File, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<string> {
  const text = await file.text();
  const ext = file.name.split('.').pop()?.toLowerCase();

  if (ext === 'srt') return translateSrt(text, targetLang, config, progressEl, statusEl);
  if (ext === 'vtt') return translateVtt(text, targetLang, config, progressEl, statusEl);
  if (ext === 'ass') return translateAss(text, targetLang, config, progressEl, statusEl);
  return text;
}

async function translateSrt(
  srt: string, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<string> {
  // SRT 格式：序号 → 时间 → 文本 → 空行
  const blocks = srt.split(/\n\n+/);
  const textBlocks: { index: number; text: string }[] = [];

  blocks.forEach((block, idx) => {
    const lines = block.trim().split('\n');
    if (lines.length >= 3) {
      const text = lines.slice(2).join('\n');
      if (text.trim()) textBlocks.push({ index: idx, text });
    }
  });

  // 批量翻译
  const BATCH = 30;
  const translated = new Map<number, string>();

  for (let i = 0; i < textBlocks.length; i += BATCH) {
    const batch = textBlocks.slice(i, i + BATCH);
    const progress = Math.min(90, 10 + (i / textBlocks.length) * 80);
    if (progressEl) progressEl.style.width = `${progress}%`;
    if (statusEl) statusEl.textContent = `翻译字幕... ${i}/${textBlocks.length} 条`;

    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts: batch.map(b => b.text),
      to: targetLang,
    });

    if (resp.type === 'TRANSLATE_RESULT') {
      batch.forEach((b, j) => {
        translated.set(b.index, resp.results[j]?.translated || b.text);
      });
    }
  }

  // 重组 SRT
  return blocks.map((block, idx) => {
    const lines = block.trim().split('\n');
    if (lines.length >= 3 && translated.has(idx)) {
      return [lines[0], lines[1], translated.get(idx)].join('\n');
    }
    return block;
  }).join('\n\n');
}

async function translateVtt(
  vtt: string, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<string> {
  // VTT 格式类似 SRT，但有 WEBVTT 头
  const header = 'WEBVTT\n\n';
  const content = vtt.replace(/^WEBVTT\n*/, '');
  const translated = await translateSrt(content, targetLang, config, progressEl, statusEl);
  return header + translated;
}

async function translateAss(
  ass: string, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<string> {
  // ASS 格式：Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,文本
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

  // 重组 ASS
  return lines.map((line, idx) => {
    if (translated.has(idx)) {
      const parts = line.split(',');
      parts[9] = translated.get(idx)!;
      return parts.join(',');
    }
    return line;
  }).join('\n');
}

// ---------- HTML 翻译 ----------
async function translateHtmlFile(
  file: File, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<string> {
  const html = await file.text();
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');

  // 提取可见文本
  const textNodes: { node: Text; text: string }[] = [];
  const walker = document.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent) return NodeFilter.FILTER_REJECT;
      if (['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(parent.tagName)) return NodeFilter.FILTER_REJECT;
      if (!node.textContent?.trim()) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });

  let node: Text | null;
  while ((node = walker.nextNode() as Text | null)) {
    const text = node.textContent?.trim();
    if (text && text.length >= 2) {
      textNodes.push({ node, text });
    }
  }

  // 批量翻译
  const BATCH = 20;
  for (let i = 0; i < textNodes.length; i += BATCH) {
    const batch = textNodes.slice(i, i + BATCH);
    if (progressEl) progressEl.style.width = `${Math.min(90, 10 + (i / textNodes.length) * 80)}%`;
    if (statusEl) statusEl.textContent = `翻译 HTML... ${i}/${textNodes.length} 段`;

    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts: batch.map(b => b.text),
      to: targetLang,
    });

    if (resp.type === 'TRANSLATE_RESULT') {
      batch.forEach((b, j) => {
        const translated = resp.results[j]?.translated;
        if (translated) b.node.textContent = translated;
      });
    }
  }

  return '<!DOCTYPE html>\n' + doc.documentElement.outerHTML;
}

// ---------- Epub 翻译 ----------
async function translateEpubFile(
  file: File, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<Blob> {
  // Epub 是 ZIP 包含 HTML 文件
  // 需要 JSZip 库（动态加载）
  if (!(window as any).JSZip) {
    await loadScript('https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js');
  }

  const JSZip = (window as any).JSZip;
  const zip = await JSZip.loadAsync(file);
  const newZip = new JSZip();

  const htmlFiles: string[] = [];
  zip.forEach((path: string) => {
    if (path.endsWith('.html') || path.endsWith('.xhtml') || path.endsWith('.htm')) {
      htmlFiles.push(path);
    }
  });

  let processed = 0;
  for (const path of htmlFiles) {
    if (progressEl) progressEl.style.width = `${Math.min(90, 10 + (processed / htmlFiles.length) * 80)}%`;
    if (statusEl) statusEl.textContent = `翻译 Epub... ${processed + 1}/${htmlFiles.length} 页`;

    const content = await zip.file(path)?.async('string');
    if (content) {
      const translated = await translateHtmlString(content, targetLang, config);
      newZip.file(path, translated);
    }
    processed++;
  }

  // 复制非 HTML 文件
  zip.forEach((path: string) => {
    if (!newZip.file(path)) {
      newZip.file(path, zip.file(path)!);
    }
  });

  return newZip.generateAsync({ type: 'blob' });
}

async function translateHtmlString(html: string, targetLang: string, config: TranslateConfig): Promise<string> {
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');
  const textNodes: { node: Text; text: string }[] = [];

  const walker = document.createTreeWalker(doc.body || doc.documentElement, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent || ['SCRIPT', 'STYLE'].includes(parent.tagName)) return NodeFilter.FILTER_REJECT;
      if (!node.textContent?.trim() || node.textContent.trim().length < 2) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });

  let node: Text | null;
  while ((node = walker.nextNode() as Text | null)) {
    textNodes.push({ node, text: node.textContent!.trim() });
  }

  const texts = textNodes.map(n => n.text);
  if (texts.length === 0) return html;

  const resp = await sendMessage({ type: 'TRANSLATE', texts, to: targetLang });
  if (resp.type === 'TRANSLATE_RESULT') {
    textNodes.forEach((n, i) => {
      const t = resp.results[i]?.translated;
      if (t) n.node.textContent = t;
    });
  }

  return '<!DOCTYPE html>\n' + doc.documentElement.outerHTML;
}

// ---------- PDF 文件翻译 ----------
async function translatePdfFile(
  file: File, targetLang: string, config: TranslateConfig,
  progressEl: HTMLElement | null, statusEl: HTMLElement | null
): Promise<string> {
  // 加载 pdf.js
  if (!window.pdfjsLib) {
    await loadScript('https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.9.155/pdf.min.js');
    window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.9.155/pdf.worker.min.js';
  }

  const translateImages = (panelEl?.querySelector('#bt-doc-translate-images') as HTMLInputElement)?.checked ?? false;

  const arrayBuffer = await file.arrayBuffer();
  const pdf = await window.pdfjsLib.getDocument({ data: arrayBuffer }).promise;
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
    document.head.appendChild(script);
  });
}

// 类型声明
declare global {
  interface Window {
    pdfjsLib: any;
    JSZip: any;
  }
}
