/* ============================================================
   漫画/图片翻译 v1 — 气泡检测 → OCR → 文字回填
   ------------------------------------------------------------
   流程：
   1. 气泡检测：白色/浅色区域连通域分析（utils/bubble-detect.ts）
   2. OCR：复用 image-translate.ts 的 ocrImage()（本地 tesseract）
   3. 文字回填：描边字体 + 自动换行 + 竖排支持（目标日漫竖排）
   ⚠️ 本版本【不做 inpaint】，只做文字覆盖（半透明底 + 描边字），
   原图不被改写。气泡检测失败时退化为整图翻译（side 模式），不静默失败。
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { detectLanguageQuick } from '../../utils/languages';
import { detectBubbles, buildLightMask, BubbleBox } from '../../utils/bubble-detect';
import { ocrImage, translateImage } from './image-translate';
import { injectStyles } from '../styles/styles';

const MAX_CANVAS_SIDE = 1600;

/* ---------- 状态提示 ---------- */
let toastEl: HTMLDivElement | null = null;

function showComicToast(text: string): void {
  if (!toastEl) {
    toastEl = document.createElement('div');
    toastEl.style.cssText = `
      position: fixed; top: 24px; left: 50%; transform: translateX(-50%);
      z-index: 2147483647; background: rgba(28,32,40,0.92); color: #fff;
      padding: 12px 22px; border-radius: 10px; font-size: 14px;
      font-family: -apple-system, 'Segoe UI', sans-serif;
    `;
    document.body.appendChild(toastEl);
  }
  toastEl.textContent = text;
}

function hideComicToast(): void {
  toastEl?.remove();
  toastEl = null;
}

/* ---------- 图像 → canvas（带 CORS 检测） ---------- */

function imageToCanvas(img: HTMLImageElement): HTMLCanvasElement | null {
  const scale = Math.min(1, MAX_CANVAS_SIDE / Math.max(img.naturalWidth || img.width, img.naturalHeight || img.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round((img.naturalWidth || img.width) * scale));
  canvas.height = Math.max(1, Math.round((img.naturalHeight || img.height) * scale));
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) return null;
  try {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    // 跨域图片会污染 canvas，getImageData 抛 SecurityError
    ctx.getImageData(0, 0, 1, 1);
    return canvas;
  } catch {
    return null; // 跨域污染：调用方退化为整图翻译
  }
}

/* ---------- 文字回填（描边字体 + 自动换行 + 竖排） ---------- */

/** 取气泡内代表色（取 bbox 四角附近的众数色，近似底色） */
function sampleBackground(ctx: CanvasRenderingContext2D, box: BubbleBox): string {
  const pts: [number, number][] = [
    [box.x + 3, box.y + 3],
    [box.x + box.w - 4, box.y + 3],
    [box.x + 3, box.y + box.h - 4],
    [box.x + box.w - 4, box.y + box.h - 4],
  ];
  let r = 255, g = 255, b = 255, n = 0;
  for (const [x, y] of pts) {
    try {
      const d = ctx.getImageData(x, y, 1, 1).data;
      r += d[0]; g += d[1]; b += d[2]; n++;
    } catch {
      /* 忽略 */
    }
  }
  const c = Math.max(n, 1);
  return `rgb(${Math.round(r / c)}, ${Math.round(g / c)}, ${Math.round(b / c)})`;
}

/** 水平自动换行（CJK 可任意断行，拉丁按词断行） */
function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const hasCjk = /[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]/.test(text);
  const units = hasCjk ? Array.from(text) : text.split(/(\s+)/);
  const lines: string[] = [];
  let line = '';
  for (const u of units) {
    const test = line + u;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = u.trim() ? u : '';
    } else {
      line = test;
    }
  }
  if (line.trim()) lines.push(line);
  return lines;
}

/** 横排回填：自动换行 + 描边字体 */
function drawHorizontalText(
  ctx: CanvasRenderingContext2D,
  text: string,
  box: BubbleBox
): void {
  const pad = 4;
  const maxW = box.w - pad * 2;
  const maxH = box.h - pad * 2;

  // 自适应字号：从大到小试到装得下
  let fontSize = Math.min(42, Math.max(11, Math.floor(box.h / 3)));
  let lines: string[] = [];
  for (let i = 0; i < 6; i++) {
    ctx.font = `${fontSize}px "Noto Sans SC", "PingFang SC", sans-serif`;
    lines = wrapText(ctx, text, maxW);
    const lineHeight = fontSize * 1.35;
    if (lines.length * lineHeight <= maxH || fontSize <= 11) break;
    fontSize = Math.max(11, Math.floor(fontSize * 0.85));
  }

  const lineHeight = fontSize * 1.35;
  const startY = box.y + pad + (maxH - lines.length * lineHeight) / 2 + fontSize;

  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';
  ctx.lineJoin = 'round';
  lines.forEach((line, i) => {
    const x = box.x + box.w / 2;
    const y = startY + i * lineHeight;
    ctx.lineWidth = Math.max(2, fontSize / 6);
    ctx.strokeStyle = 'rgba(255,255,255,0.95)';
    ctx.strokeText(line, x, y);
    ctx.fillStyle = '#1a1a1a';
    ctx.fillText(line, x, y);
  });
}

/** 竖排回填（日漫：从右到左分列，列内从上到下） */
function drawVerticalText(
  ctx: CanvasRenderingContext2D,
  text: string,
  box: BubbleBox
): void {
  const pad = 5;
  const maxW = box.w - pad * 2;
  const maxH = box.h - pad * 2;

  let fontSize = Math.min(36, Math.max(11, Math.floor(maxW / 3)));
  let cols: string[][] = [];
  let colWidth = 0;
  for (let i = 0; i < 6; i++) {
    ctx.font = `${fontSize}px "Noto Serif JP", "Yu Mincho", serif`;
    colWidth = fontSize * 1.25;
    const charsPerCol = Math.max(1, Math.floor(maxH / (fontSize * 1.08)));
    const chars = Array.from(text.replace(/\s+/g, ''));
    cols = [];
    for (let c = 0; c < chars.length; c += charsPerCol) {
      cols.push(chars.slice(c, c + charsPerCol));
    }
    if (cols.length * colWidth <= maxW || fontSize <= 11) break;
    fontSize = Math.max(11, Math.floor(fontSize * 0.85));
  }

  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.lineJoin = 'round';

  // 从右往左排
  const totalW = cols.length * colWidth;
  const startX = box.x + box.w - pad - totalW / 2;

  cols.forEach((col, ci) => {
    const x = startX + cols.length * colWidth - colWidth * (ci + 0.5);
    col.forEach((ch, ri) => {
      const y = box.y + pad + ri * fontSize * 1.08;
      ctx.lineWidth = Math.max(2, fontSize / 6);
      ctx.strokeStyle = 'rgba(255,255,255,0.95)';
      ctx.strokeText(ch, x, y);
      ctx.fillStyle = '#1a1a1a';
      ctx.fillText(ch, x, y);
    });
  });
}

/* ---------- 主流程 ---------- */

/**
 * 漫画图片翻译（文字回填到原图副本上，不改写原图）。
 * @returns 插入页面的容器元素
 */
export async function translateComicImage(
  img: HTMLImageElement,
  config: TranslateConfig
): Promise<HTMLElement> {
  injectStyles();

  let canvas: HTMLCanvasElement | null = null;
  try {
    showComicToast('🔍 检测气泡中...');
    canvas = imageToCanvas(img);
    if (!canvas) {
      // 跨域图片无法读取像素：明确提示并退化
      console.warn('[ButlerTranslate] 图片跨域无法读取像素，退化为整图翻译');
      return await degradeToWholeImage(img, config, '图片跨域无法读取像素，已退化为整图翻译');
    }

    const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
    const { width, height } = canvas;

    // 1. 气泡检测（白色/浅色区域连通域）
    const imageData = ctx.getImageData(0, 0, width, height);
    const mask = buildLightMask(imageData.data, width, height);
    const boxes = detectBubbles(mask, width, height, {
      minArea: Math.round(width * height * 0.002),
      minSize: Math.round(Math.min(width, height) * 0.03),
    });

    if (boxes.length === 0) {
      console.warn('[ButlerTranslate] 未检测到气泡，退化为整图翻译');
      return await degradeToWholeImage(img, config, '未检测到气泡，已退化为整图翻译');
    }

    // 2. OCR 每个气泡
    showComicToast(`🔍 OCR 识别 ${boxes.length} 个气泡...`);
    const ocrTexts: string[] = [];
    for (const box of boxes) {
      const crop = document.createElement('canvas');
      crop.width = box.w;
      crop.height = box.h;
      const cctx = crop.getContext('2d')!;
      cctx.drawImage(canvas, box.x, box.y, box.w, box.h, 0, 0, box.w, box.h);
      try {
        const ocr = await ocrImage(crop);
        ocrTexts.push((ocr.text || '').trim());
      } catch (err) {
        console.warn('[ButlerTranslate] 气泡 OCR 失败:', err);
        ocrTexts.push('');
      }
    }

    // 3. 批量翻译（空文本保留空）
    showComicToast('🌐 翻译中...');
    const toTranslate = ocrTexts.map((t, i) => t).filter(t => t.length >= 2);
    let translations: string[] = [];
    if (toTranslate.length > 0) {
      const resp = await sendMessage({ type: 'TRANSLATE', texts: toTranslate, to: config.targetLang });
      if (resp.type === 'TRANSLATE_RESULT') {
        translations = resp.results.map(r => r.translated);
      } else {
        translations = [...toTranslate];
      }
    }

    // 4. 文字回填（描边字体 + 自动换行 + 竖排）
    showComicToast('✍️ 文字回填中...');
    let ti = 0;
    boxes.forEach((box, i) => {
      const original = ocrTexts[i];
      if (original.length < 2) return;
      const translated = translations[ti++] || original;

      // 半透明底（只做文字覆盖，不做 inpaint）
      const bg = sampleBackground(ctx, box);
      ctx.save();
      ctx.globalAlpha = 0.82;
      ctx.fillStyle = bg;
      ctx.fillRect(box.x + 1, box.y + 1, box.w - 2, box.h - 2);
      ctx.restore();

      // 竖排判定：气泡纵向 或 原文/译文为日文、中文
      const vertical = box.h > box.w * 1.15
        || detectLanguageQuick(original) === 'ja';
      if (vertical) drawVerticalText(ctx, translated, box);
      else drawHorizontalText(ctx, translated, box);
    });

    // 5. 展示：原图位置插入回填后的 canvas（原图隐藏但不删除）
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'display:inline-block; line-height:0; position:relative;';
    wrapper.appendChild(canvas);
    canvas.style.maxWidth = '100%';
    img.style.display = 'none';
    img.parentElement?.insertBefore(wrapper, img);

    hideComicToast();
    return wrapper;
  } catch (err) {
    hideComicToast();
    console.warn('[ButlerTranslate] 漫画翻译失败，退化为整图翻译:', err);
    return degradeToWholeImage(img, config, `漫画翻译失败（${err}），已退化为整图翻译`);
  }
}

/** 退化：整图翻译（side 模式），并给出明确原因 */
async function degradeToWholeImage(
  img: HTMLImageElement,
  config: TranslateConfig,
  reason: string
): Promise<HTMLElement> {
  showComicToast(reason);
  const result = await translateImage(img, config, 'side');
  img.parentElement?.insertBefore(result, img);
  img.style.display = 'none';
  setTimeout(hideComicToast, 4000);
  return result;
}
