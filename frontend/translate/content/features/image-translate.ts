/* ============================================================
   图片翻译 — OCR 识别图片中的文字 → 翻译 → 覆盖显示
   支持：文档内嵌图片 / 网页图片 / 截图
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { injectStyles } from '../styles/styles';

// ---------- Tesseract.js 动态加载 ----------
let tesseractReady = false;
let tesseractWorker: any = null;

async function loadTesseract(): Promise<boolean> {
  if (tesseractReady) return true;
  try {
    await loadScript('https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js');
    tesseractReady = true;
    return true;
  } catch {
    console.warn('[ButlerTranslate] Failed to load Tesseract.js');
    return false;
  }
}

async function getTesseractWorker(): Promise<any> {
  if (tesseractWorker) return tesseractWorker;
  const Tesseract = (window as any).Tesseract;
  if (!Tesseract) return null;

  tesseractWorker = await Tesseract.createWorker('chi_sim+eng', 1, {
    logger: (m: any) => {
      if (m.status === 'recognizing text') {
        updateOCRProgress(Math.round(m.progress * 100));
      }
    },
  });
  return tesseractWorker;
}

// ---------- OCR 进度提示 ----------
let progressEl: HTMLDivElement | null = null;

function showOCRProgress(): void {
  removeOCRProgress();
  progressEl = document.createElement('div');
  progressEl.className = 'bt-ocr-progress';
  progressEl.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 2147483647;
    background: rgba(0, 0, 0, 0.8);
    color: #fff;
    padding: 20px 30px;
    border-radius: 12px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14px;
    text-align: center;
    backdrop-filter: blur(8px);
  `;
  progressEl.innerHTML = `
    <div style="margin-bottom: 10px;">🔍 OCR 识别中...</div>
    <div style="background: rgba(255,255,255,0.2); border-radius: 4px; height: 6px; width: 200px; overflow: hidden;">
      <div class="bt-ocr-bar" style="background: #4a9eff; height: 100%; width: 0%; transition: width 0.3s; border-radius: 4px;"></div>
    </div>
    <div class="bt-ocr-text" style="font-size: 12px; color: #aaa; margin-top: 6px;">准备中...</div>
  `;
  document.body.appendChild(progressEl);
}

function updateOCRProgress(percent: number): void {
  const bar = progressEl?.querySelector('.bt-ocr-bar');
  const text = progressEl?.querySelector('.bt-ocr-text');
  if (bar) (bar as HTMLElement).style.width = `${percent}%`;
  if (text) text.textContent = `识别中... ${percent}%`;
}

function removeOCRProgress(): void {
  progressEl?.remove();
  progressEl = null;
}

// ---------- 图片 OCR ----------
export interface OCRResult {
  text: string;
  confidence: number;
  words: Array<{
    text: string;
    bbox: { x0: number; y0: number; x1: number; y1: number };
    confidence: number;
  }>;
}

/**
 * 识别图片中的文字（前端 Tesseract.js）
 */
export async function ocrImage(imageSource: string | HTMLImageElement | HTMLCanvasElement): Promise<OCRResult> {
  await loadTesseract();
  const worker = await getTesseractWorker();
  if (!worker) throw new Error('Tesseract.js 未加载');

  const result = await worker.recognize(imageSource);
  const data = result.data;

  return {
    text: data.text.trim(),
    confidence: data.confidence,
    words: (data.words || []).map((w: any) => ({
      text: w.text,
      bbox: w.bbox,
      confidence: w.confidence,
    })),
  };
}

/**
 * 识别图片中的文字（Butler 后端 OCR，精度更高）
 */
export async function ocrImageViaButler(base64: string): Promise<OCRResult> {
  const resp = await sendMessage({
    type: 'TRANSLATE_IMAGE',
    base64,
  });

  if (resp.type === 'IMAGE_TRANSLATE_RESULT') {
    return {
      text: resp.original,
      confidence: 0.9,
      words: [],
    };
  }
  throw new Error('Butler OCR 失败');
}

// ---------- 图片翻译（OCR + 翻译 + 覆盖） ----------

/**
 * 翻译单张图片，返回翻译后的 Canvas
 */
export async function translateImage(
  img: HTMLImageElement,
  config: TranslateConfig,
  mode: 'overlay' | 'replace' | 'side' = 'overlay'
): Promise<HTMLElement> {
  injectStyles();
  injectImageStyles();
  showOCRProgress();

  try {
    // 1. OCR 识别
    const ocr = await ocrImage(img);
    removeOCRProgress();

    if (!ocr.text || ocr.text.length < 2) {
      return createResultContainer(img, '未识别到文字', '', mode);
    }

    // 2. 翻译
    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts: [ocr.text],
      to: config.targetLang,
    });

    if (resp.type !== 'TRANSLATE_RESULT') {
      throw new Error('翻译失败');
    }

    const translated = resp.results[0]?.translated || '';

    // 3. 构建结果
    return createTranslatedImage(img, ocr, translated, mode);

  } catch (err) {
    removeOCRProgress();
    throw err;
  }
}

/**
 * 翻译图片中的文字并在原图上覆盖翻译
 */
function createTranslatedImage(
  img: HTMLImageElement,
  ocr: OCRResult,
  translated: string,
  mode: 'overlay' | 'replace' | 'side'
): HTMLElement {
  const container = document.createElement('div');
  container.className = 'bt-img-translate-container';
  container.style.cssText = `
    display: inline-block;
    position: relative;
    line-height: 0;
  `;

  if (mode === 'side') {
    // 并排模式：原图 + 译文
    container.style.cssText += `display: flex; gap: 12px; align-items: flex-start;`;
    const imgClone = img.cloneNode(true) as HTMLImageElement;
    imgClone.style.maxWidth = '50%';
    container.appendChild(imgClone);

    const textDiv = document.createElement('div');
    textDiv.className = 'bt-img-side-text';
    textDiv.style.cssText = `
      flex: 1;
      padding: 12px;
      background: #f8f9fa;
      border-radius: 8px;
      font-size: 14px;
      line-height: 1.6;
      color: #333;
      white-space: pre-wrap;
      font-family: -apple-system, sans-serif;
    `;
    textDiv.textContent = translated;
    container.appendChild(textDiv);
    return container;
  }

  // overlay / replace 模式
  const wrapper = document.createElement('div');
  wrapper.style.cssText = `
    position: relative;
    display: inline-block;
    line-height: 0;
  `;

  // 原图
  const imgClone = img.cloneNode(true) as HTMLImageElement;
  imgClone.style.display = 'block';
  wrapper.appendChild(imgClone);

  if (mode === 'overlay' && ocr.words.length > 0) {
    // 逐词覆盖
    const imgRect = img.getBoundingClientRect();
    const scaleX = img.naturalWidth ? img.clientWidth / img.naturalWidth : 1;
    const scaleY = img.naturalHeight ? img.clientHeight / img.naturalHeight : 1;

    for (const word of ocr.words) {
      if (word.text.trim().length < 2 || word.confidence < 50) continue;

      // 查找该词的翻译（简单匹配：按顺序）
      const translatedWord = translated; // 整段翻译，不做逐词

      const overlay = document.createElement('div');
      overlay.className = 'bt-img-word-overlay';
      overlay.style.cssText = `
        position: absolute;
        left: ${word.bbox.x0 * scaleX}px;
        top: ${word.bbox.y0 * scaleY}px;
        width: ${(word.bbox.x1 - word.bbox.x0) * scaleX}px;
        background: rgba(255, 255, 255, 0.85);
        color: #4a9eff;
        font-size: ${Math.max(10, (word.bbox.y1 - word.bbox.y0) * scaleY * 0.6)}px;
        line-height: 1.2;
        padding: 1px 2px;
        border-radius: 2px;
        pointer-events: none;
        font-family: sans-serif;
        word-break: break-all;
        overflow: hidden;
      `;
      overlay.textContent = word.text; // 原文词（逐词翻译需额外 API 调用）
      wrapper.appendChild(overlay);
    }
  }

  // 整段翻译覆盖在底部
  const bottomOverlay = document.createElement('div');
  bottomOverlay.className = 'bt-img-full-overlay';
  bottomOverlay.style.cssText = `
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background: linear-gradient(0deg, rgba(0,0,0,0.7) 0%, transparent 100%);
    color: #fff;
    padding: 16px 12px 10px;
    font-size: 13px;
    line-height: 1.5;
    font-family: -apple-system, sans-serif;
    pointer-events: none;
    ${mode === 'replace' ? 'padding: 100% 12px 10px;' : ''}
  `;
  bottomOverlay.textContent = translated;
  wrapper.appendChild(bottomOverlay);

  container.appendChild(wrapper);
  return container;
}

function createResultContainer(img: HTMLImageElement, original: string, translated: string, mode: string): HTMLElement {
  const container = document.createElement('div');
  container.className = 'bt-img-translate-container';
  container.appendChild(img.cloneNode(true));
  return container;
}

// ---------- 批量翻译文档中的图片 ----------

/**
 * 翻译文档（PDF/HTML）中所有图片
 */
export async function translateDocumentImages(
  container: HTMLElement,
  config: TranslateConfig
): Promise<number> {
  const images = container.querySelectorAll('img');
  let translatedCount = 0;

  for (const img of images) {
    // 跳过太小的图片（图标、装饰）
    if (img.clientWidth < 80 || img.clientHeight < 60) continue;
    // 跳过已翻译的
    if (img.closest('.bt-img-translate-container')) continue;

    try {
      const result = await translateImage(img as HTMLImageElement, config, 'side');
      img.parentNode?.insertBefore(result, img);
      img.style.display = 'none';
      translatedCount++;
    } catch (err) {
      console.warn('[ButlerTranslate] Image translation failed:', err);
    }
  }

  return translatedCount;
}

/**
 * 翻译 PDF 页面中的图片
 */
export async function translatePDFPageImages(
  pageEl: HTMLElement,
  config: TranslateConfig
): Promise<number> {
  // PDF.js 渲染的图片在 .canvasWrapper canvas 中
  const canvases = pageEl.querySelectorAll('canvas');
  let count = 0;

  for (const canvas of canvases) {
    if (canvas.width < 80 || canvas.height < 60) continue;

    try {
      showOCRProgress();
      const ocr = await ocrImage(canvas);
      removeOCRProgress();

      if (ocr.text.length >= 2) {
        const resp = await sendMessage({
          type: 'TRANSLATE',
          texts: [ocr.text],
          to: config.targetLang,
        });

        if (resp.type === 'TRANSLATE_RESULT') {
          const translated = resp.results[0]?.translated;
          if (translated) {
            const overlay = document.createElement('div');
            overlay.className = 'bt-pdf-img-translated';
            overlay.style.cssText = `
              position: absolute;
              bottom: 4px;
              left: 4px;
              right: 4px;
              background: rgba(0, 0, 0, 0.75);
              color: #ffe066;
              padding: 6px 10px;
              border-radius: 6px;
              font-size: 12px;
              line-height: 1.4;
              z-index: 10;
              pointer-events: none;
            `;
            overlay.textContent = translated;

            const wrapper = canvas.parentElement;
            if (wrapper) {
              wrapper.style.position = 'relative';
              wrapper.appendChild(overlay);
            }
            count++;
          }
        }
      }
    } catch (err) {
      removeOCRProgress();
      console.warn('[ButlerTranslate] PDF image OCR failed:', err);
    }
  }

  return count;
}

// ---------- 右键翻译图片 ----------

/**
 * 初始化右键菜单：翻译此图片
 */
export function initImageContextMenu(config: TranslateConfig): void {
  document.addEventListener('contextmenu', (e) => {
    const target = e.target as HTMLElement;
    if (target.tagName === 'IMG') {
      // 通过 background 创建右键菜单项
      chrome.runtime.sendMessage({
        type: 'REGISTER_CONTEXT_MENU',
        id: 'translate-image',
        title: '翻译此图片',
        contexts: ['image'],
      });
    }
  });
}

// ---------- 样式 ----------
function injectImageStyles(): void {
  if (document.getElementById('butler-image-styles')) return;
  const style = document.createElement('style');
  style.id = 'butler-image-styles';
  style.textContent = `
    .bt-img-translate-container {
      display: inline-block;
      position: relative;
      line-height: 0;
      max-width: 100%;
    }
    .bt-img-translate-container img {
      max-width: 100%;
      height: auto;
    }
    .bt-img-word-overlay {
      transition: opacity 0.15s;
    }
    .bt-img-translate-container:hover .bt-img-word-overlay {
      opacity: 1;
    }
  `;
  document.head.appendChild(style);
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
